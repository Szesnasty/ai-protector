"""POST /agent/chat — agent chat endpoint."""

from __future__ import annotations

import time

import structlog
from fastapi import APIRouter, Header

from src.agent.graph import get_agent_graph
from src.config import get_settings
from src.schemas import (
    AgentChatRequest,
    AgentChatResponse,
    AgentTrace,
    FirewallDecision,
    ToolCallInfo,
)

logger = structlog.get_logger()
router = APIRouter(tags=["agent"])


@router.post("/agent/chat", response_model=AgentChatResponse)
async def agent_chat(
    body: AgentChatRequest,
    x_api_key: str | None = Header(default=None),
) -> AgentChatResponse:
    """Run the agent graph and return structured response."""
    settings = get_settings()
    start = time.perf_counter()

    # Build initial state
    initial_state = {
        "session_id": body.session_id,
        "user_role": body.user_role,
        "message": body.message,
        "policy": body.policy or settings.default_policy,
        "model": body.model or settings.default_model,
        "api_key": x_api_key,
    }

    # Run the agent graph
    graph = get_agent_graph()
    result = await graph.ainvoke(initial_state)

    elapsed_ms = int((time.perf_counter() - start) * 1000)

    # Build response
    tool_calls_info = [
        ToolCallInfo(
            tool=tc["tool"],
            args=tc.get("args", {}),
            result_preview=tc.get("result", "")[:200],
            allowed=tc.get("allowed", True),
        )
        for tc in result.get("tool_calls", [])
    ]

    fw = result.get("firewall_decision", {})

    response = AgentChatResponse(
        response=result.get("final_response", "No response generated."),
        session_id=body.session_id,
        tools_called=tool_calls_info,
        agent_trace=AgentTrace(
            intent=result.get("intent", "unknown"),
            user_role=body.user_role,
            allowed_tools=result.get("allowed_tools", []),
            iterations=result.get("iterations", 0),
            latency_ms=elapsed_ms,
        ),
        firewall_decision=FirewallDecision(
            decision=fw.get("decision", "UNKNOWN"),
            risk_score=fw.get("risk_score", 0.0),
            intent=fw.get("intent", ""),
            risk_flags=fw.get("risk_flags", {}),
            blocked_reason=fw.get("blocked_reason"),
        ),
        trace=result.get("trace", {}),
    )

    logger.info(
        "agent_chat",
        session_id=body.session_id,
        role=body.user_role,
        intent=result.get("intent"),
        tools=len(tool_calls_info),
        decision=fw.get("decision"),
        latency_ms=elapsed_ms,
    )

    return response
