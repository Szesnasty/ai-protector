"""Pure Python Test Agent — uses wizard-generated security configs.

Dual-mode agent:
  - **mock** (default): keyword-based tool routing, no LLM needed
  - **llm**: real LLM call via LiteLLM with native function calling

Both modes share the same security gates (RBAC, limits, PII scan).
"""

from __future__ import annotations

import json
import os
import re
from typing import Literal

import httpx
import structlog
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from protection import (
    get_config,
    protected_tool_call,
    reset_config,
    scan_output,
)

# shared tools — copied into container at build time
from shared.tool_definitions import SYSTEM_PROMPT, TOOL_DEFINITIONS
from shared.tools import execute_tool

logger = structlog.get_logger()

app = FastAPI(title="Test Agent — Pure Python", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

PROXY_URL = os.getenv("PROXY_URL", "http://localhost:8000")


# ── Request / response schemas ────────────────────────────────────────


class ChatRequest(BaseModel):
    message: str
    role: str = "user"
    tool: str | None = None
    tool_args: dict | None = None
    confirmed: bool = False
    mode: Literal["mock", "llm"] = "mock"
    model: str = "gpt-4o-mini"
    api_key: str | None = None


class LoadConfigRequest(BaseModel):
    agent_id: str


# ── Endpoints ─────────────────────────────────────────────────────────


@app.get("/health")
async def health():
    config = get_config()
    return {"status": "ok", "config_loaded": config.loaded}


@app.get("/config-status")
async def config_status():
    config = get_config()
    return {
        "loaded": config.loaded,
        "roles": list(config.rbac.get("roles", {}).keys()),
        "tools_in_rbac": _count_tools(config.rbac),
        "policy_pack": config.policy.get("policy_pack", "none"),
    }


@app.post("/load-config")
async def load_config(req: LoadConfigRequest):
    """Fetch integration kit from wizard API and load configs."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{PROXY_URL}/v1/agents/{req.agent_id}/integration-kit")
        if resp.status_code == 404:
            resp = await client.post(
                f"{PROXY_URL}/v1/agents/{req.agent_id}/integration-kit"
            )
        if resp.status_code != 200:
            raise HTTPException(502, f"Failed to fetch kit: {resp.status_code}")

    kit = resp.json()
    get_config().load_from_kit(kit)
    logger.info("config_loaded", agent_id=req.agent_id, framework=kit.get("framework"))
    return {
        "loaded": True,
        "framework": kit.get("framework"),
        "files": list(kit.get("files", {}).keys()),
    }


@app.post("/reset-config")
async def reset_config_endpoint():
    """Reset loaded config (for testing)."""
    reset_config()
    return {"reset": True}


@app.post("/chat")
async def chat(req: ChatRequest):
    """Process a chat message with security enforcement."""
    config = get_config()
    if not config.loaded:
        raise HTTPException(400, "No config loaded. Call POST /load-config first.")

    if req.mode == "llm":
        return await _chat_llm(req)
    return _chat_mock(req)


# ── Mock mode (keyword routing) ──────────────────────────────────────


def _chat_mock(req: ChatRequest) -> dict:
    """Mock mode: keyword-route → security gates → execute."""
    tool = req.tool or _route_to_tool(req.message)
    if not tool:
        return {
            "response": (
                "I couldn't determine which tool to use. "
                "Try: getOrders, getUsers, searchProducts, updateOrder, updateUser"
            ),
            "gate_log": [],
        }

    args = req.tool_args or _extract_args(req.message, tool)

    result = protected_tool_call(
        role=req.role,
        tool=tool,
        args=args,
        execute_fn=execute_tool,
    )

    # Handle confirmation flow
    if result.get("requires_confirmation") and not req.confirmed:
        return {
            "response": f"⚠️ Tool '{tool}' requires confirmation. Reason: {result['reason']}",
            "requires_confirmation": True,
            "tool": tool,
            "args": args,
            "gate_log": [
                {"gate": "pre_tool", "decision": "confirm", "reason": result["reason"]}
            ],
        }

    if result.get("requires_confirmation") and req.confirmed:
        raw = execute_tool(tool, args)
        scan = scan_output(str(raw))
        result = {
            "allowed": True,
            "result": raw,
            "decision": "allow",
            "scan_result": scan,
            "gate": "post_tool",
            "reason": None if scan["clean"] else "Output contains flagged content",
        }

    return _build_response(result)


# ── LLM mode (real model call via LiteLLM) ───────────────────────────


async def _chat_llm(req: ChatRequest) -> dict:
    """LLM mode: model → tool_calls → security gates → execute → model."""
    try:
        import litellm
    except ImportError as exc:
        raise HTTPException(501, "litellm not installed") from exc

    if not req.api_key:
        raise HTTPException(400, "api_key is required in LLM mode")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": req.message},
    ]

    # 1. Ask LLM which tool to call
    response = await litellm.acompletion(
        model=req.model,
        messages=messages,
        tools=TOOL_DEFINITIONS,
        tool_choice="auto",
        api_key=req.api_key,
    )

    choice = response.choices[0].message

    # If no tool call, return text directly
    if not choice.tool_calls:
        return {
            "response": choice.content or "No response from model.",
            "blocked": False,
            "gate_log": [],
            "mode": "llm",
        }

    # 2. Process the first tool call through security gates
    tc = choice.tool_calls[0]
    tool_name = tc.function.name
    tool_args = json.loads(tc.function.arguments) if tc.function.arguments else {}

    result = protected_tool_call(
        role=req.role,
        tool=tool_name,
        args=tool_args,
        execute_fn=execute_tool,
    )

    if not result["allowed"]:
        return _build_response(result, mode="llm")

    # 3. Send tool result back to LLM for natural-language formatting
    messages.append(choice.model_dump())
    messages.append(
        {
            "role": "tool",
            "tool_call_id": tc.id,
            "content": str(result["result"]),
        }
    )

    final = await litellm.acompletion(
        model=req.model,
        messages=messages,
        api_key=req.api_key,
    )

    gate_log = [
        {
            "gate": result.get("gate", "post_tool"),
            "decision": result.get("decision", "allow"),
            "reason": result.get("reason"),
            "scan_findings": (
                result.get("scan_result", {}).get("findings", [])
                if result.get("scan_result")
                else []
            ),
        }
    ]

    return {
        "response": final.choices[0].message.content,
        "blocked": False,
        "gate_log": gate_log,
        "mode": "llm",
        "tool_called": tool_name,
    }


# ── Helpers ───────────────────────────────────────────────────────────


def _build_response(result: dict, *, mode: str = "mock") -> dict:
    """Build a standardised chat response from a protection result."""
    gate_log = [
        {
            "gate": result.get("gate", "unknown"),
            "decision": result.get("decision", "unknown"),
            "reason": result.get("reason"),
            "scan_findings": (
                result.get("scan_result", {}).get("findings", [])
                if result.get("scan_result")
                else []
            ),
        }
    ]

    if not result.get("allowed", True):
        return {
            "response": f"❌ BLOCKED: {result['reason']}",
            "blocked": True,
            "gate_log": gate_log,
            "mode": mode,
        }

    return {
        "response": result["result"],
        "blocked": False,
        "gate_log": gate_log,
        "mode": mode,
    }


def _route_to_tool(message: str) -> str | None:
    """Simple keyword-based tool routing."""
    msg = message.lower()
    if any(w in msg for w in ["order", "orders", "zamówien"]):
        if any(w in msg for w in ["update", "change", "modify", "set", "zmień"]):
            return "updateOrder"
        return "getOrders"
    if any(w in msg for w in ["user", "users", "użytkown"]):
        if any(w in msg for w in ["update", "change", "modify", "set", "zmień"]):
            return "updateUser"
        return "getUsers"
    if any(w in msg for w in ["product", "search", "find", "szukaj"]):
        return "searchProducts"
    return None


def _extract_args(message: str, tool: str) -> dict:
    """Extract basic args from message (simplified)."""
    args: dict = {}
    if tool == "updateOrder":
        m = re.search(r"(ORD-\d+)", message, re.IGNORECASE)
        if m:
            args["order_id"] = m.group(1)
        for status in ["shipped", "delivered", "cancelled", "processing", "pending"]:
            if status in message.lower():
                args["status"] = status
                break
    elif tool == "updateUser":
        m = re.search(r"(USR-\d+)", message, re.IGNORECASE)
        if m:
            args["user_id"] = m.group(1)
    elif tool == "searchProducts":
        m = re.search(
            r"(?:search|find|szukaj)\s+(?:for\s+)?(.+)", message, re.IGNORECASE
        )
        if m:
            args["query"] = m.group(1).strip()
    return args


def _count_tools(rbac: dict) -> int:
    tools: set[str] = set()
    for role_cfg in rbac.get("roles", {}).values():
        tools.update(role_cfg.get("tools", {}).keys())
    return len(tools)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8003)
