"""InputNode — validate input, sanitize user message and load session history."""

from __future__ import annotations

import structlog

from src.agent.limits.service import get_limits_service
from src.agent.security.sanitizer import sanitize_user_input
from src.agent.state import AgentState
from src.session import session_store

logger = structlog.get_logger()


def input_node(state: AgentState) -> AgentState:
    """Load session history, sanitize user input, check limits and initialize state."""
    session_id = state["session_id"]
    user_role = state.get("user_role", "customer")
    chat_history = session_store.get_history(session_id)

    # Sanitize user message at the earliest point (spec 05)
    raw_message = state.get("message", "")
    sanitized_message = sanitize_user_input(raw_message)

    # ── Limit checks at request entry (spec 06) ──────────
    limits_svc = get_limits_service()
    limit_check = limits_svc.check_request_entry(
        session_id=session_id,
        user_id=session_id,  # user_id ≈ session_id for now
        role=user_role,
    )

    usage = limits_svc.get_session_usage(session_id)

    logger.info(
        "input_node",
        session_id=session_id,
        history_len=len(chat_history),
        message_sanitized=raw_message != sanitized_message,
        limit_ok=limit_check.allowed,
    )

    base_state: dict = {
        **state,
        "message": sanitized_message,
        "chat_history": chat_history,
        "tool_calls": state.get("tool_calls", []),
        "tool_plan": [],
        "iterations": 0,
        "errors": state.get("errors", []),
        "node_timings": state.get("node_timings", {}),
        # Limits counters (spec 06)
        "session_tool_calls": usage["session_tool_calls"],
        "session_tokens_in": usage["session_tokens_in"],
        "session_tokens_out": usage["session_tokens_out"],
        "session_estimated_cost": usage["session_estimated_cost"],
        "session_turns": usage["session_turns"],
        "limit_exceeded": None,
    }

    if not limit_check.allowed:
        base_state["limit_exceeded"] = limit_check.limit_type
        base_state["final_response"] = limit_check.message

    return base_state
