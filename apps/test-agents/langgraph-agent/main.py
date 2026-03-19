"""LangGraph Test Agent — uses wizard-generated security gates in a real graph."""

from __future__ import annotations

import sys
import os

# Ensure shared tools and langgraph-agent are importable
_agent_dir = os.path.dirname(os.path.abspath(__file__))
_parent = os.path.dirname(_agent_dir)
if _agent_dir not in sys.path:
    sys.path.insert(0, _agent_dir)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

import httpx  # noqa: E402
import json  # noqa: E402
import structlog  # noqa: E402
from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel  # noqa: E402

# ═══ AI PROTECTOR — Import security config + graph ═════════════════
from protection import get_config, reset_config  # noqa: E402
from graph import get_graph, reset_graph  # noqa: E402
# ═══════════════════════════════════════════════════════════════════

logger = structlog.get_logger()
app = FastAPI(title="Test Agent — LangGraph", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

PROXY_URL = os.environ.get("PROXY_URL", "http://localhost:8000")
PROXY_POLICY = os.environ.get("PROXY_POLICY", "balanced")

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
    → decision → LLM → post-LLM scan.  Returns
    ``{"content": str, "blocked": bool, "reason": str|None}``
    or *None* when the proxy is unreachable (caller falls back to
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


# ── Request models ──────────────────────────────────────────────


class ChatRequest(BaseModel):
    message: str
    role: str = "user"
    tool: str | None = None
    tool_args: dict | None = None
    confirmed: bool = False
    # LLM mode fields
    mode: str = "mock"  # "mock" or "llm"
    model: str | None = None
    api_key: str | None = None


class LoadConfigRequest(BaseModel):
    agent_id: str


# ── Endpoints ───────────────────────────────────────────────────


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "config_loaded": get_config().loaded,
        "framework": "langgraph",
    }


@app.get("/config-status")
async def config_status():
    c = get_config()
    roles = list(c.rbac.get("roles", {}).keys())
    tools: set[str] = set()
    for role_cfg in c.rbac.get("roles", {}).values():
        tools.update(role_cfg.get("tools", {}).keys())
    return {
        "loaded": c.loaded,
        "roles": roles,
        "tools": sorted(tools),
        "policy_pack": c.policy.get("policy_pack", "none"),
    }


# ═══ AI PROTECTOR — Load Config from Wizard Integration Kit ═════
#
# This endpoint fetches the wizard-generated security configuration
# (rbac.yaml, limits.yaml, policy.yaml) from the AI Protector proxy
# and loads it into the SecurityConfig singleton.
#
# After this call, all chat requests will be enforced by:
#   - PreToolGate (RBAC + rate limits)
#   - PostToolGate (PII + injection scanning)
#
@app.post("/load-config")
async def load_config(req: LoadConfigRequest):
    """Load security config from proxy-service integration kit."""
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
    # AI Protector: force graph recompilation with new security config
    reset_graph()
    logger.info("config_loaded", agent_id=req.agent_id, framework="langgraph")
    return {
        "loaded": True,
        "framework": "langgraph",
        "files": list(kit.get("files", {}).keys()),
    }


@app.post("/reset-config")
async def do_reset_config():
    """Reset config and graph (for testing)."""
    reset_config()
    reset_graph()
    return {"reset": True}


# ═══ AI PROTECTOR — Run Chat Through Security Pipeline ═════════
#
# The graph.invoke() call runs:
#   route_tool → pre_tool_gate → tool_executor → post_tool_gate → response
# Security gates are embedded in the graph itself (see graph.py)
#
@app.post("/chat")
async def chat(req: ChatRequest):
    """Run a message through the LangGraph security pipeline."""
    if not get_config().loaded:
        raise HTTPException(400, "No config loaded. Call POST /load-config first.")

    if req.mode == "llm":
        return await _chat_llm(req)
    return _chat_mock(req)


def _chat_mock(req: ChatRequest) -> dict:
    """Mock mode: keyword routing → graph with security gates."""
    compiled = get_graph()
    initial_state = {
        "message": req.message,
        "role": req.role,
        "tool": req.tool,
        "tool_args": req.tool_args,
        "confirmed": req.confirmed,
    }

    result = compiled.invoke(initial_state)

    return {
        "response": result.get("final_response", "No response"),
        "blocked": result.get("blocked", False),
        "no_match": result.get("no_match", False),
        "requires_confirmation": result.get("requires_confirmation", False),
        "tool": result.get("tool"),
        "tool_args": result.get("tool_args"),
        "gate_log": result.get("gate_log", []),
        "graph_nodes_visited": _extract_nodes(result),
        "mode": "mock",
    }


async def _chat_llm(req: ChatRequest) -> dict:
    """LLM mode: model selects tool → graph runs security gates → format response."""
    try:
        import litellm
    except ImportError as exc:
        raise HTTPException(501, "litellm not installed") from exc

    from shared.tool_definitions import SYSTEM_PROMPT, TOOL_DEFINITIONS

    model = req.model or "ollama/llama3.2:3b"
    needs_key = not model.startswith("ollama/")
    if needs_key and not req.api_key:
        raise HTTPException(400, "api_key is required for cloud models")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
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
            "no_match": False,
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
    choice = response.choices[0].message  # type: ignore[union-attr]

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
                        f"Input scanned via '{PROXY_POLICY}' policy "
                        f"(intent={pre_scan.get('intent', '?')}, "
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
            "no_match": False,
            "gate_log": gate_log,
            "mode": "llm",
        }

    # 2. Extract tool call → run through graph security gates
    tc = choice.tool_calls[0]
    tool_name = tc.function.name
    tool_args = json.loads(tc.function.arguments) if tc.function.arguments else {}

    # Guard: if LLM hallucinated a tool not in our catalogue, treat as text
    known_tools = {t["function"]["name"] for t in TOOL_DEFINITIONS}
    if tool_name not in known_tools:
        return {
            "response": choice.content or f"(LLM tried unknown tool '{tool_name}')",
            "blocked": False,
            "no_match": False,
            "gate_log": [
                {
                    "gate": "llm_guard",
                    "decision": "skip",
                    "reason": f"LLM selected unknown tool '{tool_name}', treated as text",
                }
            ],
            "mode": "llm",
        }

    compiled = get_graph()
    initial_state = {
        "message": req.message,
        "role": req.role,
        "tool": tool_name,
        "tool_args": tool_args,
        "confirmed": req.confirmed,
    }

    result = compiled.invoke(initial_state)

    # If blocked or requires confirmation, return gate result
    if result.get("blocked") or result.get("requires_confirmation"):
        return {
            "response": result.get("final_response", "No response"),
            "blocked": result.get("blocked", False),
            "no_match": False,
            "requires_confirmation": result.get("requires_confirmation", False),
            "tool": result.get("tool"),
            "tool_args": result.get("tool_args"),
            "gate_log": result.get("gate_log", []),
            "graph_nodes_visited": _extract_nodes(result),
            "mode": "llm",
        }

    # 3. ═══ AI PROTECTOR — Route through proxy firewall (balanced) ═══
    # The formatting call goes through the proxy for content-level
    # filtering: injection detection, toxicity, PII scan.
    tool_result_str = str(result.get("final_response", ""))
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

    existing_gate_log = result.get("gate_log", [])

    if proxy_result and proxy_result["blocked"]:
        existing_gate_log.append(
            {
                "gate": "proxy_firewall",
                "decision": "block",
                "reason": proxy_result["reason"],
                "policy": PROXY_POLICY,
            }
        )
        return {
            "response": f"⛔ Proxy firewall BLOCK ({PROXY_POLICY}): {proxy_result['reason']}",
            "blocked": True,
            "no_match": False,
            "requires_confirmation": False,
            "tool": result.get("tool"),
            "tool_args": result.get("tool_args"),
            "gate_log": existing_gate_log,
            "graph_nodes_visited": _extract_nodes(result),
            "mode": "llm",
        }

    if proxy_result and proxy_result["content"]:
        existing_gate_log.append(
            {
                "gate": "proxy_firewall",
                "decision": "allow",
                "reason": f"Routed through '{PROXY_POLICY}' policy",
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

        format_kwargs: dict = {"model": model, "messages": messages}
        if model.startswith("ollama/"):
            format_kwargs["api_base"] = os.environ.get(
                "OLLAMA_HOST", "http://ollama:11434"
            )
        if req.api_key:
            format_kwargs["api_key"] = req.api_key

        final = await litellm.acompletion(**format_kwargs)
        final_text = final.choices[0].message.content or tool_result_str  # type: ignore[union-attr]

        existing_gate_log.append(
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
        "no_match": False,
        "requires_confirmation": False,
        "tool": result.get("tool"),
        "tool_args": result.get("tool_args"),
        "gate_log": existing_gate_log,
        "graph_nodes_visited": _extract_nodes(result),
        "mode": "llm",
    }


def _extract_nodes(result: dict) -> list[str]:
    """List which graph nodes were visited (from gate_log)."""
    return [entry.get("gate", "unknown") for entry in result.get("gate_log", [])]


# ── Source files endpoint (for frontend source viewer) ──────────


def _read_source(path: str) -> str | None:
    """Read a source file relative to the agent or shared directory."""
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return None


@app.get("/source-files")
async def source_files():
    """Return agent source code for the frontend source viewer."""
    shared_dir = os.path.join(_parent, "shared")
    files: dict[str, dict] = {}

    # Agent files
    agent_files = {
        "main.py": {
            "description": "FastAPI app — endpoints, config loading",
            "highlight": [
                {"name": "/load-config", "category": "config"},
                {"name": "protected_tool_call()", "category": "pipeline"},
                {"name": "_proxy_scan()", "category": "proxy"},
                {"name": "_proxy_llm_call()", "category": "proxy"},
                {"name": "PROXY_POLICY", "category": "proxy"},
            ],
        },
        "graph.py": {
            "description": "LangGraph StateGraph — security gates wired into the graph",
            "highlight": [
                {"name": "PreToolGate", "category": "pipeline"},
                {"name": "PostToolGate", "category": "scan"},
                {"name": "pre_tool_gate", "category": "pipeline"},
                {"name": "post_tool_gate", "category": "scan"},
                {"name": "build_graph()", "category": "pipeline"},
            ],
        },
        "protection.py": {
            "description": "Security layer — RBAC, limits, PII scanning (loads wizard config)",
            "highlight": [
                {"name": "SecurityConfig", "category": "config"},
                {"name": "load_from_kit()", "category": "config"},
                {"name": "RBACService", "category": "rbac"},
                {"name": "LimitsService", "category": "limits"},
                {"name": "PreToolGate", "category": "pipeline"},
                {"name": "PostToolGate", "category": "scan"},
            ],
        },
    }
    for fname, meta in agent_files.items():
        content = _read_source(os.path.join(_agent_dir, fname))
        if content:
            files[f"langgraph-agent/{fname}"] = {
                "content": content,
                "language": "python",
                **meta,
            }

    # Shared files
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
        "framework": "langgraph",
        "files": files,
        "tree": [
            {"path": "langgraph-agent/", "type": "dir", "label": "Agent"},
            {"path": "langgraph-agent/main.py", "type": "file", "icon": "entry"},
            {"path": "langgraph-agent/graph.py", "type": "file", "icon": "security"},
            {
                "path": "langgraph-agent/protection.py",
                "type": "file",
                "icon": "security",
            },
            {
                "path": "langgraph-agent/config/",
                "type": "dir",
                "label": "Wizard Config (loaded at runtime)",
            },
            {
                "path": "langgraph-agent/config/rbac.yaml",
                "type": "config",
                "icon": "config",
            },
            {
                "path": "langgraph-agent/config/limits.yaml",
                "type": "config",
                "icon": "config",
            },
            {
                "path": "langgraph-agent/config/policy.yaml",
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

    uvicorn.run(app, host="0.0.0.0", port=8004)
