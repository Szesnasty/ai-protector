"""MemoryNode — store conversation turn in session memory & finalize trace."""

from __future__ import annotations

import structlog

from src.agent.state import AgentState
from src.agent.trace.accumulator import TraceAccumulator
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

    # Trace finalize (spec 07)
    trace = TraceAccumulator(state.get("trace"))
    trace.finalize(
        final_response=assistant_response,
        errors=state.get("errors"),
        node_timings=state.get("node_timings"),
        counters_override={
            "estimated_cost": state.get("session_estimated_cost", 0.0),
        },
    )

    logger.info(
        "memory_node",
        session_id=session_id,
        history_len=len(session_store.get_history(session_id)),
    )

    return {
        **state,
        "trace": trace.data,
    }
