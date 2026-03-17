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
import structlog  # noqa: E402
from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from protection import get_config, reset_config  # noqa: E402
from graph import get_graph, reset_graph  # noqa: E402

logger = structlog.get_logger()
app = FastAPI(title="Test Agent — LangGraph", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

PROXY_URL = os.environ.get("PROXY_URL", "http://localhost:8000")


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


@app.post("/load-config")
async def load_config(req: LoadConfigRequest):
    """Load security config from proxy-service integration kit."""
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


@app.post("/chat")
async def chat(req: ChatRequest):
    """Run a message through the LangGraph security pipeline."""
    if not get_config().loaded:
        raise HTTPException(400, "No config loaded. Call POST /load-config first.")

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
        "requires_confirmation": result.get("requires_confirmation", False),
        "tool": result.get("tool"),
        "tool_args": result.get("tool_args"),
        "gate_log": result.get("gate_log", []),
        "graph_nodes_visited": _extract_nodes(result),
    }


def _extract_nodes(result: dict) -> list[str]:
    """List which graph nodes were visited (from gate_log)."""
    return [entry.get("gate", "unknown") for entry in result.get("gate_log", [])]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8004)
