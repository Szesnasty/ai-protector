"""Core chat orchestration: handles conversation flow, retrieval, tools, tracing."""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any

from app.config import Settings
from app.gemini_client import ModelBackend
from app.models import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    StructuredAnswer,
    TraceRecord,
    TraceRef,
)
from app.prompts import build_system_prompt
from app.retrieval import format_context, retrieve
from app.storage import ConversationStore, TraceStore
from app.tools import execute_tool

logger = logging.getLogger(__name__)

# Structured output JSON schema for Gemini
_STRUCTURED_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "requires_follow_up": {"type": "boolean"},
        "risk_flags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["answer", "requires_follow_up", "risk_flags"],
}


class ChatService:
    def __init__(
        self,
        settings: Settings,
        backend: ModelBackend,
        conversations: ConversationStore,
        traces: TraceStore,
    ) -> None:
        self._settings = settings
        self._backend = backend
        self._conversations = conversations
        self._traces = traces

    async def handle_chat(self, req: ChatRequest) -> ChatResponse:
        request_id = str(uuid.uuid4())
        conversation_id = req.conversation_id or str(uuid.uuid4())

        # Resolve feature flags: request overrides default if provided
        use_retrieval = (
            req.use_retrieval
            if req.use_retrieval is not None
            else self._settings.enable_retrieval
        )
        use_tools = (
            req.use_tools if req.use_tools is not None else self._settings.enable_tools
        )

        # Build system prompt with optional canary
        system_prompt, canary_id, canary_token = build_system_prompt(
            enable_canary=self._settings.enable_canary
        )

        # Load/create conversation and append incoming messages
        conv = self._conversations.get_or_create(conversation_id)
        self._conversations.append_messages(conversation_id, req.messages)

        # Retrieval augmentation
        retrieval_docs: list[str] = []
        if use_retrieval and req.messages:
            last_user_msg = next(
                (m.content for m in reversed(req.messages) if m.role == "user"), ""
            )
            if last_user_msg:
                docs = retrieve(last_user_msg, top_k=3)
                retrieval_docs = [d.id for d in docs]
                context = format_context(docs)
                if context:
                    system_prompt += "\n\n" + context

        # Prepare trace
        trace = TraceRecord(
            request_id=request_id,
            app_mode=self._settings.app_mode,
            conversation_id=conversation_id,
            scenario_id=req.metadata.scenario_id if req.metadata else None,
            retrieval_used=bool(retrieval_docs),
            retrieval_docs=retrieval_docs,
            tools_enabled=use_tools,
            response_mode=req.response_mode,
            canary_id=canary_id,
            canary_token=canary_token,
            streamed=False,
            model=self._settings.gemini_model,
        )

        try:
            # Determine JSON schema for structured output
            json_schema = _STRUCTURED_SCHEMA if req.response_mode == "json" else None

            # Call model
            result = await self._backend.generate(
                system_prompt,
                conv.messages,
                response_mode=req.response_mode,
                tools_enabled=use_tools,
                json_schema=json_schema,
            )

            # Handle tool calls (single round)
            if result.tool_calls and use_tools:
                for tc in result.tool_calls:
                    tool_result = execute_tool(tc.name, tc.arguments)
                    tc.result = tool_result
                trace.tool_calls = result.tool_calls

                # Append tool result and generate final response
                tool_msg = ChatMessage(
                    role="tool",
                    content=str(tool_result),
                )
                conv_messages = list(conv.messages) + [tool_msg]
                result = await self._backend.generate(
                    system_prompt,
                    conv_messages,
                    response_mode=req.response_mode,
                    tools_enabled=False,
                    json_schema=json_schema,
                )

            # Validate structured output
            structured_output = None
            if req.response_mode == "json" and result.text:
                try:
                    import json as _json

                    parsed = _json.loads(result.text)
                    validated = StructuredAnswer(**parsed)
                    structured_output = validated.model_dump()
                    trace.structured_output_valid = True
                except Exception as e:
                    trace.structured_output_valid = False
                    trace.structured_output_error = str(e)

            # Persist assistant message
            self._conversations.append_messages(
                conversation_id,
                [ChatMessage(role="assistant", content=result.text)],
            )

            # Build citations from retrieval docs
            citations: list[dict[str, Any]] = []
            if retrieval_docs:
                for doc_id in retrieval_docs:
                    citations.append({"doc_id": doc_id})

            trace.response_length = len(result.text)
            trace.model = result.model or self._settings.gemini_model
            self._traces.put(trace)

            return ChatResponse(
                id=request_id,
                conversation_id=conversation_id,
                variant=self._settings.app_mode,
                model=trace.model,
                output_text=result.text,
                structured_output=structured_output,
                tool_calls=[tc.model_dump() for tc in result.tool_calls],
                citations=citations,
                system_canary_enabled=self._settings.enable_canary,
                trace=TraceRef(
                    request_id=request_id,
                    streamed=False,
                    used_retrieval=bool(retrieval_docs),
                    used_tools=bool(result.tool_calls),
                ),
            )

        except Exception as e:
            trace.error_type = type(e).__name__
            trace.error_message = str(e)
            self._traces.put(trace)
            raise

    async def handle_stream(self, req: ChatRequest) -> AsyncIterator[str]:
        """Yield SSE-formatted events for a streaming chat request."""
        import json as _json

        request_id = str(uuid.uuid4())
        conversation_id = req.conversation_id or str(uuid.uuid4())

        use_retrieval = (
            req.use_retrieval
            if req.use_retrieval is not None
            else self._settings.enable_retrieval
        )
        use_tools = (
            req.use_tools if req.use_tools is not None else self._settings.enable_tools
        )

        system_prompt, canary_id, canary_token = build_system_prompt(
            enable_canary=self._settings.enable_canary
        )

        conv = self._conversations.get_or_create(conversation_id)
        self._conversations.append_messages(conversation_id, req.messages)

        retrieval_docs: list[str] = []
        if use_retrieval and req.messages:
            last_user_msg = next(
                (m.content for m in reversed(req.messages) if m.role == "user"), ""
            )
            if last_user_msg:
                docs = retrieve(last_user_msg, top_k=3)
                retrieval_docs = [d.id for d in docs]
                context = format_context(docs)
                if context:
                    system_prompt += "\n\n" + context

        trace = TraceRecord(
            request_id=request_id,
            app_mode=self._settings.app_mode,
            conversation_id=conversation_id,
            scenario_id=req.metadata.scenario_id if req.metadata else None,
            retrieval_used=bool(retrieval_docs),
            retrieval_docs=retrieval_docs,
            tools_enabled=use_tools,
            response_mode="text",
            canary_id=canary_id,
            canary_token=canary_token,
            streamed=True,
            model=self._settings.gemini_model,
        )

        full_text = ""
        try:
            async for chunk in self._backend.generate_stream(
                system_prompt, conv.messages, tools_enabled=use_tools
            ):
                full_text += chunk
                yield f"event: delta\ndata: {_json.dumps({'text': chunk})}\n\n"

            # Persist assistant message
            self._conversations.append_messages(
                conversation_id,
                [ChatMessage(role="assistant", content=full_text)],
            )

            trace.response_length = len(full_text)
            self._traces.put(trace)

            completed = {
                "text": full_text,
                "conversation_id": conversation_id,
                "request_id": request_id,
                "variant": self._settings.app_mode,
                "model": self._settings.gemini_model,
            }
            yield f"event: completed\ndata: {_json.dumps(completed)}\n\n"

            trace_summary = {
                "request_id": request_id,
                "conversation_id": conversation_id,
                "streamed": True,
                "used_retrieval": bool(retrieval_docs),
                "used_tools": use_tools,
            }
            yield f"event: trace\ndata: {_json.dumps(trace_summary)}\n\n"

        except Exception as e:
            trace.error_type = type(e).__name__
            trace.error_message = str(e)
            self._traces.put(trace)
            error_data = {"error": type(e).__name__, "detail": str(e)}
            yield f"event: error\ndata: {_json.dumps(error_data)}\n\n"
