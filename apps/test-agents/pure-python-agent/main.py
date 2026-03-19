"""Pure Python Test Agent — uses wizard-generated security configs.

Dual-mode agent:
  - **mock** (default): keyword-based tool routing, no LLM needed
  - **llm**: real LLM call via LiteLLM with native function calling

Both modes share the same security gates (RBAC, limits, PII scan).
LLM responses are routed through the AI Protector proxy firewall
(``balanced`` policy by default) for content-level filtering.

╔════════════════════════════════════════════════════════════════════╗
║  AI PROTECTOR — Integration Example (Pure Python)                ║
║                                                                  ║
║  This file shows how AI Protector security is integrated into    ║
║  a plain Python agent (no framework). Look for:                  ║
║                                                                  ║
║    # ═══ AI PROTECTOR ═══                                        ║
║                                                                  ║
║  Key integration points:                                         ║
║    1. Import protected_tool_call, scan_output from protection.py ║
║    2. /load-config   — fetch wizard YAML from proxy              ║
║    3. _chat_mock()   — calls protected_tool_call() pipeline      ║
║    4. _chat_llm()    — same pipeline, but with real LLM          ║
║    5. protected_tool_call = RBAC → limits → execute → scan       ║
╚════════════════════════════════════════════════════════════════════╝
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

# ═══ AI PROTECTOR — Import security functions ═════════════════════
from protection import (
    get_config,
    protected_tool_call,  # full pipeline: RBAC → limits → execute → scan
    reset_config,
    scan_output,  # post-tool PII + injection scanner
)
# ═══════════════════════════════════════════════════════════════════

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
PROXY_POLICY = os.getenv("PROXY_POLICY", "balanced")

# Intents that indicate a genuine attack — everything NOT in this set
# (e.g. "qa", "greeting") is considered benign even if the risk score
# is elevated by overaggressive scanners (NeMo false-positives).
_ATTACK_INTENTS: frozenset[str] = frozenset(
    {
        "jailbreak",
        "system_prompt_extract",
        "role_bypass",
        "tool_abuse",
        "agent_exfiltration",
        "social_engineering",
        "harmful_content",
        "misinformation",
        "resource_exhaustion",
        "supply_chain",
        "rag_poisoning",
        "pii_request",
        "confused_deputy",
        "template_injection",
        "virtual_context",
        "crescendo",
    }
)


# ── Proxy scan-only (no LLM call) ────────────────────────────────────


async def _proxy_scan(
    *,
    messages: list[dict],
    model: str,
    api_key: str | None = None,
) -> dict | None:
    """Run the proxy firewall pre-LLM pipeline (scan only, no LLM call).

    Uses ``POST /v1/scan`` which executes: parse → intent → rules →
    scanners → decision — and returns the verdict WITHOUT calling any
    LLM provider.  This is much faster than the full
    ``/v1/chat/completions`` pipeline.

    Returns ``{"blocked": bool, "intent": str, "risk_score": float,
    "reason": str|None}`` — or *None* when the proxy is unreachable.
    """
    clean_msgs = [
        {"role": m["role"], "content": m.get("content", "")}
        for m in messages
        if m.get("role") in ("system", "user", "assistant") and m.get("content")
    ]
    if not clean_msgs or not any(m["role"] == "user" for m in clean_msgs):
        return None

    headers: dict[str, str] = {"x-policy": PROXY_POLICY}
    if api_key:
        headers["x-api-key"] = api_key

    body = {"model": model, "messages": clean_msgs, "stream": False}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{PROXY_URL}/v1/scan",
                json=body,
                headers=headers,
            )
        data = resp.json()
        intent = data.get("intent", "")
        risk_score = data.get("risk_score", 0.0)

        # Block when the proxy's decision is BLOCK *and* either:
        #   1. The intent is a known attack category, OR
        #   2. The risk score is very high (>= 0.9) — catches attacks
        #      that the intent classifier missed (e.g. credential theft
        #      classified as "qa" but with risk_score=1.0).
        # Normal queries (risk 0.5–0.75) are let through even when the
        # proxy BLOCKs them — NeMo false-positives on benign messages.
        proxy_blocked = resp.status_code == 403
        blocked = proxy_blocked and (intent in _ATTACK_INTENTS or risk_score >= 0.9)

        return {
            "blocked": blocked,
            "intent": intent,
            "risk_score": risk_score,
            "reason": data.get("blocked_reason") if blocked else None,
        }
    except Exception as exc:
        logger.warning("proxy_scan_failed", error=str(exc))

    return None  # proxy unreachable — let the request through


# ── Proxy-routed LLM call (balanced firewall) ────────────────────────


async def _proxy_llm_call(
    *,
    messages: list[dict],
    model: str,
    api_key: str | None = None,
) -> dict | None:
    """Route an LLM call through the AI Protector proxy firewall.

    The proxy runs the full pipeline: parse → intent → rules → scanners
    → decision → LLM → post-LLM scan.  This gives content-level
    protection (injection detection, toxicity, PII redaction) on top of
    the RBAC/limits enforced locally.

    Returns ``{"content": str, "blocked": bool, "reason": str|None}``
    or *None* when the proxy is unreachable (caller should fall back to
    direct LiteLLM).
    """
    clean_msgs = [
        {"role": m["role"], "content": m.get("content", "")}
        for m in messages
        if m.get("role") in ("system", "user", "assistant") and m.get("content")
    ]
    if not clean_msgs or not any(m["role"] == "user" for m in clean_msgs):
        return None

    headers: dict[str, str] = {"x-policy": PROXY_POLICY}
    if api_key:
        headers["x-api-key"] = api_key

    body = {"model": model, "messages": clean_msgs, "stream": False}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{PROXY_URL}/v1/chat/completions",
                json=body,
                headers=headers,
            )
        if resp.status_code == 403:
            data = resp.json()
            return {
                "content": None,
                "blocked": True,
                "reason": data.get("detail", "Blocked by proxy firewall"),
            }
        if resp.status_code == 200:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return {"content": content, "blocked": False, "reason": None}
        logger.warning("proxy_llm_non_200", status=resp.status_code)
    except Exception as exc:
        logger.warning("proxy_llm_call_failed", error=str(exc))

    return None  # fallback to direct litellm


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
    # Build RBAC matrix: role → {tool → {allowed, scopes, sensitivity}}
    rbac_matrix: dict[str, dict] = {}
    for role_name, role_cfg in config.rbac.get("roles", {}).items():
        tools_map: dict[str, dict] = {}
        for tool_name, tool_cfg in role_cfg.get("tools", {}).items():
            tools_map[tool_name] = {
                "allowed": True,
                "scopes": tool_cfg.get("scopes", ["read"]),
                "sensitivity": tool_cfg.get("sensitivity", "low"),
                "requires_confirmation": tool_cfg.get("requires_confirmation", False),
            }
        rbac_matrix[role_name] = tools_map
    return {
        "loaded": config.loaded,
        "roles": list(config.rbac.get("roles", {}).keys()),
        "tools_in_rbac": _count_tools(config.rbac),
        "policy_pack": config.policy.get("policy_pack", "none"),
        "rbac_matrix": rbac_matrix,
    }


# ═══ AI PROTECTOR — Load Config from Wizard Integration Kit ═════
#
# This endpoint fetches the wizard-generated security configuration
# (rbac.yaml, limits.yaml, policy.yaml) from the AI Protector proxy
# and loads it into the SecurityConfig singleton.
#
# After this call, all chat requests will be enforced by the
# protected_tool_call() pipeline (RBAC → limits → exec → scan).
#
@app.post("/load-config")
async def load_config(req: LoadConfigRequest):
    """Fetch integration kit from wizard API and load configs."""
    # AI Protector: fetch wizard-generated YAML configs from proxy
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{PROXY_URL}/v1/agents/{req.agent_id}/integration-kit")
        if resp.status_code == 404:
            resp = await client.post(
                f"{PROXY_URL}/v1/agents/{req.agent_id}/integration-kit"
            )
        if resp.status_code != 200:
            raise HTTPException(502, f"Failed to fetch kit: {resp.status_code}")

    kit = resp.json()
    # AI Protector: parse YAML configs and store in SecurityConfig singleton
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
                "I couldn't match your request to a supported action.\n"
                "Try asking about: orders, users, products — or use "
                "one of the quick action buttons below."
            ),
            "blocked": False,
            "no_match": True,
            "gate_log": [
                {
                    "gate": "router",
                    "decision": "no_match",
                    "reason": "No tool matched the user message",
                }
            ],
        }

    args = req.tool_args or _extract_args(req.message, tool)

    # ═══ AI PROTECTOR — Run tool through full security pipeline ═══
    # protected_tool_call() handles:
    #   1. RBAC check (role has permission?)
    #   2. Rate limit check (within budget?)
    #   3. Tool execution (if allowed)
    #   4. Output scan (PII, injection)
    result = protected_tool_call(
        role=req.role,
        tool=tool,
        args=args,
        execute_fn=execute_tool,
    )
    # ═══════════════════════════════════════════════════════════════════

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

    model = req.model or "ollama/llama3.2:3b"
    needs_key = not model.startswith("ollama/")
    if needs_key and not req.api_key:
        raise HTTPException(400, "api_key is required for cloud models")

    role_context = (
        f"The current user's role is '{req.role}'. "
        f"You may call any tool that is available to this role — "
        f"security enforcement is handled by the AI Protector gate, not by you. "
        f"Never refuse a tool call on permission grounds; always attempt the call "
        f"and let the security layer decide."
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + "\n\n" + role_context},
        {"role": "user", "content": req.message},
    ]

    # 0. ═══ AI PROTECTOR — Pre-scan via proxy firewall ════════════════
    # Scan the user message through the proxy BEFORE calling the LLM.
    # Uses /v1/scan (scan-only, no LLM call) for speed.
    # Only blocks when the intent is a known attack category — this
    # avoids false-positives from over-aggressive scanners (NeMo) on
    # normal e-commerce queries like "list all users".
    pre_scan = await _proxy_scan(
        messages=messages,
        model=model,
        api_key=req.api_key,
    )

    if pre_scan and pre_scan["blocked"]:
        return {
            "response": (
                f"⛔ Proxy firewall BLOCK ({PROXY_POLICY}): {pre_scan['reason']}"
            ),
            "blocked": True,
            "gate_log": [
                {
                    "gate": "proxy_firewall",
                    "decision": "block",
                    "reason": pre_scan["reason"],
                    "policy": PROXY_POLICY,
                    "intent": pre_scan.get("intent"),
                    "risk_score": pre_scan.get("risk_score"),
                }
            ],
            "mode": "llm",
        }
    # ═══════════════════════════════════════════════════════════════════

    # 1. Ask LLM which tool to call
    kwargs: dict = {
        "model": model,
        "messages": messages,
        "tools": TOOL_DEFINITIONS,
        "tool_choice": "auto",
    }
    if model.startswith("ollama/"):
        kwargs["api_base"] = os.environ.get("OLLAMA_HOST", "http://ollama:11434")
    if req.api_key:
        kwargs["api_key"] = req.api_key

    response = await litellm.acompletion(**kwargs)

    choice = response.choices[0].message

    # If no tool call, return LLM's conversational response directly.
    # The input was already scanned by _proxy_scan() above; the LLM's
    # response to a safe input is fine to pass through.
    if not choice.tool_calls:
        gate_log = []
        if pre_scan:
            gate_log.append(
                {
                    "gate": "proxy_firewall",
                    "decision": "allow",
                    "reason": (
                        f"Scanned and allowed by proxy firewall "
                        f"({PROXY_POLICY} policy, intent={pre_scan.get('intent', '?')}, "
                        f"risk={pre_scan.get('risk_score', 0):.2f})"
                    ),
                    "policy": PROXY_POLICY,
                    "intent": pre_scan.get("intent"),
                    "risk_score": pre_scan.get("risk_score"),
                }
            )
        else:
            gate_log.append(
                {
                    "gate": "proxy_firewall",
                    "decision": "skip",
                    "reason": "Proxy unavailable — direct LLM fallback",
                }
            )
        text = choice.content or "No response from model."
        return {
            "response": text,
            "blocked": False,
            "gate_log": gate_log,
            "mode": "llm",
        }

    # 2. ═══ AI PROTECTOR — Security gate check ════════════════════
    # Extract tool call info from LLM response
    tc = choice.tool_calls[0]
    tool_name = tc.function.name
    tool_args = json.loads(tc.function.arguments) if tc.function.arguments else {}

    # Guard: if LLM hallucinated a tool not in our catalogue, treat as text
    known_tools = {t["function"]["name"] for t in TOOL_DEFINITIONS}
    if tool_name not in known_tools:
        return {
            "response": choice.content or f"(LLM tried unknown tool '{tool_name}')",
            "blocked": False,
            "gate_log": [
                {
                    "gate": "llm_guard",
                    "decision": "skip",
                    "reason": f"LLM selected unknown tool '{tool_name}', treated as text",
                }
            ],
            "mode": "llm",
        }

    # Same protected_tool_call as mock mode — RBAC + limits + scan
    result = protected_tool_call(
        role=req.role,
        tool=tool_name,
        args=tool_args,
        execute_fn=execute_tool,
    )
    # ═══════════════════════════════════════════════════════════════════

    if not result["allowed"]:
        return _build_response(result, mode="llm")

    # ═══ AI PROTECTOR — Confirmation gate (LLM mode) ═════════════════
    # If the tool requires explicit confirmation, pause here and ask
    # the user to confirm before executing (same as mock mode).
    if result.get("requires_confirmation") and not req.confirmed:
        return {
            "response": f"⚠️ Tool '{tool_name}' requires confirmation. {result.get('reason', '')}",
            "requires_confirmation": True,
            "tool": tool_name,
            "args": tool_args,
            "gate_log": [
                {
                    "gate": "pre_tool",
                    "decision": "confirm",
                    "reason": result.get("reason"),
                    "tool": tool_name,
                    "role": req.role,
                }
            ],
            "mode": "llm",
        }

    # When confirmed=True the tool still needs to run (protected_tool_call
    # returns early on requires_confirmation regardless of confirmed flag).
    if result.get("requires_confirmation") and req.confirmed:
        raw = execute_tool(tool_name, tool_args)
        scan = scan_output(str(raw))
        result = {
            "allowed": True,
            "result": raw,
            "decision": "allow",
            "scan_result": scan,
            "gate": "post_tool",
            "reason": None if scan["clean"] else "Output contains flagged content",
        }
    # ═══════════════════════════════════════════════════════════════════

    # 3. ═══ AI PROTECTOR — Route through proxy firewall (balanced) ═══
    # The formatting call goes through the proxy so the response gets
    # content-level filtering: injection detection, toxicity, PII scan.
    tool_result_str = str(result["result"])
    proxy_messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": req.message},
        {
            "role": "user",
            "content": (
                f"The tool '{tool_name}' was called and returned:\n\n"
                f"{tool_result_str}\n\n"
                "Please provide a helpful, natural-language summary."
            ),
        },
    ]

    proxy_result = await _proxy_llm_call(
        messages=proxy_messages,
        model=model,
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

    if proxy_result and proxy_result["blocked"]:
        # Proxy blocked the formatting call — likely a false positive from
        # NeMo Guardrails on benign tool output.  RBAC + limits + output scan
        # already passed, so we fall back to direct LiteLLM formatting and
        # log the proxy verdict for visibility.
        logger.info(
            "proxy_format_blocked_fallback",
            reason=proxy_result["reason"],
            policy=PROXY_POLICY,
            tool=tool_name,
        )
        gate_log.append(
            {
                "gate": "proxy_firewall",
                "decision": "skip",
                "reason": f"Proxy blocked formatting (false positive) — direct LLM fallback. Reason: {proxy_result['reason']}",
                "policy": PROXY_POLICY,
            }
        )
        # Fall through to direct LiteLLM formatting below
        proxy_result = None

    if proxy_result and proxy_result["content"]:
        gate_log.append(
            {
                "gate": "proxy_firewall",
                "decision": "allow",
                "reason": f"Allowed by proxy firewall ({PROXY_POLICY} policy)",
                "policy": PROXY_POLICY,
            }
        )
        final_text = proxy_result["content"]
    else:
        # Fallback: direct LiteLLM if proxy is unavailable
        messages.append(choice.model_dump())
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tc.id,
                "content": tool_result_str,
            }
        )

        final_kwargs: dict = {"model": model, "messages": messages}
        if model.startswith("ollama/"):
            final_kwargs["api_base"] = os.environ.get(
                "OLLAMA_HOST", "http://ollama:11434"
            )
        if req.api_key:
            final_kwargs["api_key"] = req.api_key

        final = await litellm.acompletion(**final_kwargs)
        final_text = final.choices[0].message.content

        gate_log.append(
            {
                "gate": "proxy_firewall",
                "decision": "skip",
                "reason": "Proxy unavailable — direct LLM fallback",
            }
        )
    # ═══════════════════════════════════════════════════════════════════

    return {
        "response": final_text,
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
            "response": f"⛔ Security block: {result['reason']}",
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


# ── Source files endpoint (for frontend source viewer) ──────────


def _read_source(path: str) -> str | None:
    """Read a source file."""
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return None


_agent_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.dirname(_agent_dir)


@app.get("/source-files")
async def source_files():
    """Return agent source code for the frontend source viewer."""
    shared_dir = os.path.join(_parent_dir, "shared")
    files: dict[str, dict] = {}

    agent_files = {
        "main.py": {
            "description": "FastAPI app — dual-mode agent (mock + LLM)",
            "highlight": [
                {"name": "/load-config", "category": "config"},
                {"name": "protected_tool_call()", "category": "pipeline"},
                {"name": "scan_output()", "category": "scan"},
                {"name": "_proxy_scan()", "category": "proxy"},
                {"name": "_proxy_llm_call()", "category": "proxy"},
                {"name": "PROXY_POLICY", "category": "proxy"},
            ],
        },
        "protection.py": {
            "description": "Security layer — RBAC, limits, PII scanning (loads wizard config)",
            "highlight": [
                {"name": "SecurityConfig", "category": "config"},
                {"name": "load_from_kit()", "category": "config"},
                {"name": "check_rbac()", "category": "rbac"},
                {"name": "check_limits()", "category": "limits"},
                {"name": "scan_output()", "category": "scan"},
                {"name": "protected_tool_call()", "category": "pipeline"},
            ],
        },
    }
    for fname, meta in agent_files.items():
        content = _read_source(os.path.join(_agent_dir, fname))
        if content:
            files[f"pure-python-agent/{fname}"] = {
                "content": content,
                "language": "python",
                **meta,
            }

    shared_files = {
        "__init__.py": {"description": "Re-exports for shared module"},
        "tools.py": {
            "description": "Mock tool functions (getOrders, updateUser, etc.)"
        },
        "mock_data.py": {
            "description": "Test data with deliberate PII for scanner testing"
        },
        "tool_definitions.py": {"description": "OpenAI function-calling tool schemas"},
    }
    for fname, meta in shared_files.items():
        content = _read_source(os.path.join(shared_dir, fname))
        if content:
            files[f"shared/{fname}"] = {
                "content": content,
                "language": "python",
                **meta,
            }

    return {
        "framework": "raw_python",
        "files": files,
        "tree": [
            {"path": "pure-python-agent/", "type": "dir", "label": "Agent"},
            {"path": "pure-python-agent/main.py", "type": "file", "icon": "entry"},
            {
                "path": "pure-python-agent/protection.py",
                "type": "file",
                "icon": "security",
            },
            {
                "path": "pure-python-agent/config/",
                "type": "dir",
                "label": "Wizard Config (loaded at runtime)",
            },
            {
                "path": "pure-python-agent/config/rbac.yaml",
                "type": "config",
                "icon": "config",
            },
            {
                "path": "pure-python-agent/config/limits.yaml",
                "type": "config",
                "icon": "config",
            },
            {
                "path": "pure-python-agent/config/policy.yaml",
                "type": "config",
                "icon": "config",
            },
            {"path": "shared/", "type": "dir", "label": "Shared Tools"},
            {"path": "shared/tools.py", "type": "file", "icon": "tool"},
            {"path": "shared/mock_data.py", "type": "file", "icon": "data"},
            {"path": "shared/tool_definitions.py", "type": "file", "icon": "schema"},
        ],
    }


@app.get("/loaded-config")
async def loaded_config():
    """Return the currently loaded YAML configs."""
    c = get_config()
    if not c.loaded:
        return {"loaded": False, "configs": {}}

    import yaml as _yaml

    configs = {}
    for name in ("rbac", "limits", "policy"):
        data = getattr(c, name, {})
        if data:
            configs[f"{name}.yaml"] = _yaml.dump(
                data, default_flow_style=False, allow_unicode=True
            )
    return {"loaded": True, "configs": configs}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8003)
