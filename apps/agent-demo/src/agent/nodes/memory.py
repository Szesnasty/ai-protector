"""MemoryNode — store conversation turn in session memory & finalize trace."""

from __future__ import annotations

import httpx
import structlog

from src.agent.state import AgentState
from src.agent.trace.accumulator import TraceAccumulator
from src.agent.trace.langfuse import send_trace_to_langfuse
from src.agent.trace.store import get_trace_store
from src.config import get_settings
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

    # Persist trace (Phase 2) and Langfuse (Phase 3)
    trace_dict = trace.to_dict()

    # Centralized: flush to proxy-service if agent_id is configured
    settings = get_settings()
    if settings.agent_id:
        _flush_trace_to_proxy(trace_dict, settings)
    else:
        # Fallback: in-memory store (legacy)
        get_trace_store().save(trace_dict)

    send_trace_to_langfuse(trace_dict)

    logger.info(
        "memory_node",
        session_id=session_id,
        history_len=len(session_store.get_history(session_id)),
    )

    return {
        **state,
        "trace": trace.data,
    }


def _flush_trace_to_proxy(trace_dict: dict, settings) -> None:
    """POST trace to proxy-service centralized trace store (fire-and-forget)."""
    proxy_base = settings.proxy_base_url.rstrip("/")
    # proxy_base_url is like http://localhost:8000/v1 — we need /v1/agents/{id}/traces/ingest
    url = f"{proxy_base}/agents/{settings.agent_id}/traces/ingest"
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, json=trace_dict)
        if resp.status_code == 201:
            logger.info("trace_flushed_to_proxy", trace_id=trace_dict.get("trace_id"))
        else:
            logger.warning(
                "trace_flush_failed",
                status=resp.status_code,
                body=resp.text[:200],
                trace_id=trace_dict.get("trace_id"),
            )
    except Exception as exc:
        logger.warning(
            "trace_flush_error",
            error=str(exc)[:200],
            trace_id=trace_dict.get("trace_id"),
        )
        # Fallback to in-memory store on flush failure
        get_trace_store().save(trace_dict)
