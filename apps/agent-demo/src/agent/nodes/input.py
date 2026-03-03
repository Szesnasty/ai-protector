"""InputNode — validate input and load session history."""

from __future__ import annotations

import structlog

from src.agent.state import AgentState
from src.session import session_store

logger = structlog.get_logger()


def input_node(state: AgentState) -> AgentState:
    """Load session history and initialize state fields."""
    session_id = state["session_id"]
    chat_history = session_store.get_history(session_id)

    logger.info("input_node", session_id=session_id, history_len=len(chat_history))

    return {
        **state,
        "chat_history": chat_history,
        "tool_calls": state.get("tool_calls", []),
        "tool_plan": [],
        "iterations": 0,
        "errors": state.get("errors", []),
        "node_timings": state.get("node_timings", {}),
    }
