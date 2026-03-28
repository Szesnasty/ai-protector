"""Model backend abstraction — GeminiDirect and ProtectedHTTP adapters."""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

import httpx
from google import genai
from google.genai import types as genai_types

from app.config import Settings
from app.models import BackendResult, ChatMessage, ToolCallRecord
from app.tools import TOOL_DEFINITIONS

logger = logging.getLogger(__name__)


class ModelBackend(ABC):
    """Internal interface for model calls."""

    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        messages: list[ChatMessage],
        *,
        response_mode: str = "text",
        tools_enabled: bool = False,
        json_schema: dict[str, Any] | None = None,
    ) -> BackendResult: ...

    @abstractmethod
    async def generate_stream(
        self,
        system_prompt: str,
        messages: list[ChatMessage],
        *,
        tools_enabled: bool = False,
    ) -> AsyncIterator[str]: ...


# ── Gemini Direct ──


class GeminiDirectBackend(ModelBackend):
    def __init__(self, settings: Settings) -> None:
        self._model = settings.gemini_model
        self._timeout = settings.model_timeout
        self._client = genai.Client(api_key=settings.gemini_api_key)

    def _build_contents(self, messages: list[ChatMessage]) -> list[genai_types.Content]:
        contents: list[genai_types.Content] = []
        for msg in messages:
            role = "model" if msg.role == "assistant" else "user"
            contents.append(
                genai_types.Content(
                    role=role, parts=[genai_types.Part(text=msg.content)]
                )
            )
        return contents

    def _build_config(
        self,
        system_prompt: str,
        *,
        response_mode: str,
        tools_enabled: bool,
        json_schema: dict[str, Any] | None,
    ) -> genai_types.GenerateContentConfig:
        config = genai_types.GenerateContentConfig(
            system_instruction=system_prompt,
        )
        if response_mode == "json" and json_schema:
            config.response_mime_type = "application/json"
            config.response_schema = json_schema
        if tools_enabled:
            tool_declarations = []
            for td in TOOL_DEFINITIONS:
                tool_declarations.append(
                    genai_types.FunctionDeclaration(
                        name=td["name"],
                        description=td["description"],
                        parameters=td["parameters"],
                    )
                )
            config.tools = [genai_types.Tool(function_declarations=tool_declarations)]
        return config

    async def generate(
        self,
        system_prompt: str,
        messages: list[ChatMessage],
        *,
        response_mode: str = "text",
        tools_enabled: bool = False,
        json_schema: dict[str, Any] | None = None,
    ) -> BackendResult:
        contents = self._build_contents(messages)
        config = self._build_config(
            system_prompt,
            response_mode=response_mode,
            tools_enabled=tools_enabled,
            json_schema=json_schema,
        )
        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=contents,
            config=config,
        )
        tool_calls: list[ToolCallRecord] = []
        text = ""
        if response.candidates:
            candidate = response.candidates[0]
            for part in candidate.content.parts:
                if part.text:
                    text += part.text
                if part.function_call:
                    fc = part.function_call
                    tool_calls.append(
                        ToolCallRecord(
                            name=fc.name, arguments=dict(fc.args) if fc.args else {}
                        )
                    )
        return BackendResult(text=text, tool_calls=tool_calls, model=self._model)

    async def generate_stream(
        self,
        system_prompt: str,
        messages: list[ChatMessage],
        *,
        tools_enabled: bool = False,
    ) -> AsyncIterator[str]:
        contents = self._build_contents(messages)
        config = self._build_config(
            system_prompt,
            response_mode="text",
            tools_enabled=tools_enabled,
            json_schema=None,
        )
        async for chunk in self._client.aio.models.generate_content_stream(
            model=self._model,
            contents=contents,
            config=config,
        ):
            if chunk.text:
                yield chunk.text


# ── Protected HTTP (OpenAI-compatible via AI Protector) ──


class ProtectedHTTPBackend(ModelBackend):
    def __init__(self, settings: Settings) -> None:
        base = settings.ai_protector_base_url.rstrip("/")
        self._url = f"{base}/v1/chat/completions"
        self._api_key = settings.ai_protector_api_key
        self._model = settings.gemini_model
        self._timeout = settings.model_timeout

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _build_oai_messages(
        self, system_prompt: str, messages: list[ChatMessage]
    ) -> list[dict[str, str]]:
        oai_msgs: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        for m in messages:
            oai_msgs.append({"role": m.role, "content": m.content})
        return oai_msgs

    async def generate(
        self,
        system_prompt: str,
        messages: list[ChatMessage],
        *,
        response_mode: str = "text",
        tools_enabled: bool = False,
        json_schema: dict[str, Any] | None = None,
    ) -> BackendResult:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": self._build_oai_messages(system_prompt, messages),
            "stream": False,
        }
        if response_mode == "json":
            payload["response_format"] = {"type": "json_object"}
        if tools_enabled:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": td["name"],
                        "description": td["description"],
                        "parameters": td["parameters"],
                    },
                }
                for td in TOOL_DEFINITIONS
            ]
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(self._url, headers=self._headers(), json=payload)

            # Handle proxy-level block (403 from AI Protector)
            if resp.status_code == 403:
                try:
                    err_data = resp.json()
                    reason = err_data.get("error", {}).get(
                        "message", "Request blocked by policy"
                    )
                except Exception:
                    reason = "Request blocked by policy"
                return BackendResult(
                    text=f"I cannot process this request — it was blocked by our security policy. {reason}",
                    tool_calls=[],
                    model=self._model,
                    blocked=True,
                    proxy_block_headers={
                        "x-decision": resp.headers.get("x-decision", "BLOCK"),
                        "x-risk-score": resp.headers.get("x-risk-score", ""),
                        "x-intent": resp.headers.get("x-intent", ""),
                    },
                )

            resp.raise_for_status()
            data = resp.json()

        tool_calls: list[ToolCallRecord] = []
        text = ""
        choice = data.get("choices", [{}])[0]
        msg = choice.get("message", {})
        text = msg.get("content", "") or ""
        for tc in msg.get("tool_calls", []):
            fn = tc.get("function", {})
            args = fn.get("arguments", "{}")
            try:
                parsed_args = json.loads(args) if isinstance(args, str) else args
            except json.JSONDecodeError:
                parsed_args = {"_raw": args}
            tool_calls.append(
                ToolCallRecord(name=fn.get("name", ""), arguments=parsed_args)
            )

        return BackendResult(
            text=text, tool_calls=tool_calls, model=data.get("model", self._model)
        )

    async def generate_stream(
        self,
        system_prompt: str,
        messages: list[ChatMessage],
        *,
        tools_enabled: bool = False,
    ) -> AsyncIterator[str]:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": self._build_oai_messages(system_prompt, messages),
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            async with client.stream(
                "POST", self._url, headers=self._headers(), json=payload
            ) as resp:
                # Handle proxy-level block (403 from AI Protector)
                if resp.status_code == 403:
                    body = await resp.aread()
                    try:
                        err_data = json.loads(body)
                        reason = err_data.get("error", {}).get(
                            "message", "Request blocked by policy"
                        )
                    except Exception:
                        reason = "Request blocked by policy"
                    yield f"I cannot process this request — it was blocked by our security policy. {reason}"
                    return

                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[len("data: ") :]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue


def create_backend(settings: Settings) -> ModelBackend:
    if settings.app_mode == "protected":
        if not settings.ai_protector_base_url:
            raise ValueError(
                "APP_MODE=protected requires AI_PROTECTOR_BASE_URL to be set"
            )
        return ProtectedHTTPBackend(settings)
    if not settings.gemini_api_key:
        raise ValueError("GEMINI_API_KEY is required for raw mode")
    return GeminiDirectBackend(settings)
