"""MemoryNode — store conversation turn in session memory."""

from __future__ import annotations

import structlog

from src.agent.state import AgentState
from src.session import session_store

logger = structlog.get_logger()


def memory_node(state: AgentState) -> AgentState:
    """Append user message and assistant response to session history."""
    session_id = state.get("session_id", "")
    user_message = state.get("message", "")
    # Use final_response if set (e.g. from BLOCK), otherwise llm_response
    assistant_response = state.get("final_response", "") or state.get("llm_response", "")

    if session_id and user_message:
        session_store.append(session_id, "user", user_message)

    if session_id and assistant_response:
        session_store.append(session_id, "assistant", assistant_response)

    logger.info(
        "memory_node",
        session_id=session_id,
        history_len=len(session_store.get_history(session_id)),
    )

    return state
