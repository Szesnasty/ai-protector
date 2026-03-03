"""LoggingNode — audit log to Postgres + Langfuse trace.

Runs as the **last** node in all pipeline paths (ALLOW, MODIFY, BLOCK).
Errors are swallowed so logging never blocks the response.
"""

from __future__ import annotations

import structlog

from src.pipeline.nodes import timed_node
from src.pipeline.state import PipelineState
from src.services.langfuse_client import add_pipeline_spans, create_trace
from src.services.request_logger import log_request_from_state

logger = structlog.get_logger()


@timed_node("logging")
async def logging_node(state: PipelineState) -> PipelineState:
    """Write audit record to Postgres and send Langfuse trace.

    Errors are swallowed — logging must never block the response.
    """
    # 1. Postgres audit log
    try:
        await log_request_from_state(dict(state))
    except Exception:
        logger.exception("logging_node_postgres_failed")

    # 2. Langfuse trace
    try:
        trace = await create_trace(
            trace_id=state.get("request_id", ""),
            input_data={
                "messages": state.get("sanitized_messages") or state.get("messages", []),
                "model": state.get("model", ""),
                "policy": state.get("policy_name", ""),
            },
            output_data={
                "decision": state.get("decision", ""),
                "risk_score": state.get("risk_score", 0.0),
                "response_preview": _safe_response_preview(state),
            },
            metadata={
                "intent": state.get("intent"),
                "risk_flags": state.get("risk_flags", {}),
                "scanner_results_summary": _scanner_summary(state),
                "output_filter_results": state.get("output_filter_results", {}),
                "node_timings": state.get("node_timings", {}),
            },
            tags=_build_tags(state),
            user_id=state.get("client_id"),
        )

        await add_pipeline_spans(
            trace,
            state.get("node_timings", {}),
        )
    except Exception:
        logger.exception("logging_node_langfuse_failed")

    # Logging does NOT modify state
    return state


def _safe_response_preview(state: PipelineState, max_len: int = 500) -> str | None:
    """Extract first N chars of LLM response for trace."""
    resp = state.get("llm_response")
    if not resp:
        return None
    try:
        content = resp["choices"][0]["message"]["content"]
        return content[:max_len] if content else None
    except (KeyError, IndexError, TypeError):
        return None


def _scanner_summary(state: PipelineState) -> dict:
    """Compact scanner results for Langfuse metadata."""
    results = state.get("scanner_results", {})
    summary: dict = {}
    for scanner_name, data in results.items():
        if isinstance(data, dict):
            summary[scanner_name] = {
                k: v
                for k, v in data.items()
                if k in ("is_valid", "score", "pii_action", "entity_count", "pii_count")
            }
    return summary


def _build_tags(state: PipelineState) -> list[str]:
    """Build Langfuse tags from state."""
    tags = [f"decision:{state.get('decision', 'unknown')}"]
    if state.get("policy_name"):
        tags.append(f"policy:{state['policy_name']}")
    if state.get("intent"):
        tags.append(f"intent:{state['intent']}")
    if state.get("output_filtered"):
        tags.append("output_filtered")
    return tags
