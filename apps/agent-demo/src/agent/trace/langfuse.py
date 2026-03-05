"""Optional Langfuse integration for agent traces (spec 07 Phase 3).

Sends finalized traces to Langfuse as structured observations.
Gracefully skips if Langfuse SDK is not installed or not configured.

Configuration (environment variables):
  LANGFUSE_PUBLIC_KEY  — Langfuse project public key
  LANGFUSE_SECRET_KEY  — Langfuse project secret key
  LANGFUSE_HOST        — Langfuse server URL (default: http://localhost:3000)
  AGENT_LANGFUSE_ENABLED — "true" to enable (default: "false")
"""

from __future__ import annotations

import os
from typing import Any

import structlog

logger = structlog.get_logger()

_langfuse_client: Any = None
_langfuse_available: bool | None = None


def _is_enabled() -> bool:
    """Check if Langfuse integration is enabled via env."""
    return os.environ.get("AGENT_LANGFUSE_ENABLED", "false").lower() in ("true", "1", "yes")


def _get_client() -> Any:
    """Lazily initialise the Langfuse client. Returns None if unavailable."""
    global _langfuse_client, _langfuse_available

    if _langfuse_available is False:
        return None

    if _langfuse_client is not None:
        return _langfuse_client

    if not _is_enabled():
        _langfuse_available = False
        return None

    try:
        from langfuse import Langfuse  # type: ignore[import-untyped]

        _langfuse_client = Langfuse(
            public_key=os.environ.get("LANGFUSE_PUBLIC_KEY", ""),
            secret_key=os.environ.get("LANGFUSE_SECRET_KEY", ""),
            host=os.environ.get("LANGFUSE_HOST", "http://localhost:3000"),
        )
        _langfuse_available = True
        logger.info("langfuse_agent_connected")
        return _langfuse_client
    except Exception as e:
        _langfuse_available = False
        logger.info("langfuse_agent_unavailable", reason=str(e))
        return None


def send_trace_to_langfuse(trace: dict[str, Any]) -> bool:
    """Send a finalized agent trace to Langfuse.

    Creates a Langfuse trace with a span per iteration (containing
    observations for each sub-step).

    Returns True if sent successfully, False otherwise.
    """
    client = _get_client()
    if client is None:
        return False

    try:
        trace_id = trace.get("trace_id", "")
        session_id = trace.get("session_id", "")

        # Create top-level Langfuse trace
        lf_trace = client.trace(
            id=trace_id,
            name="agent-request",
            session_id=session_id,
            metadata={
                "user_role": trace.get("user_role"),
                "policy": trace.get("policy"),
                "model": trace.get("model"),
                "intent": trace.get("intent"),
                "intent_confidence": trace.get("intent_confidence"),
                "total_duration_ms": trace.get("total_duration_ms"),
                "limits_hit": trace.get("limits_hit"),
            },
            input=trace.get("user_message", ""),
            output=trace.get("final_response", ""),
            tags=_build_tags(trace),
        )

        # Create a span per iteration
        for iteration in trace.get("iterations", []):
            it_num = iteration.get("iteration", 0)
            span = lf_trace.span(
                name=f"iteration-{it_num}",
                metadata={"iteration": it_num},
            )

            # Pre-tool decisions as observations
            for dec in iteration.get("pre_tool_decisions", []):
                span.event(
                    name=f"pre-tool-{dec.get('tool', 'unknown')}",
                    metadata=dec,
                    level="WARNING" if dec.get("decision") == "BLOCK" else "DEFAULT",
                )

            # Tool executions
            for exe in iteration.get("tool_executions", []):
                span.event(
                    name=f"tool-{exe.get('tool', 'unknown')}",
                    metadata={
                        "args": exe.get("args"),
                        "duration_ms": exe.get("duration_ms"),
                        "result_length": exe.get("result_length"),
                    },
                )

            # Post-tool decisions
            for post in iteration.get("post_tool_decisions", []):
                span.event(
                    name=f"post-tool-{post.get('tool', 'unknown')}",
                    metadata=post,
                    level="WARNING" if post.get("decision") in ("REDACT", "BLOCK") else "DEFAULT",
                )

            # LLM call
            llm_call = iteration.get("llm_call")
            if llm_call:
                span.generation(
                    name="llm-call",
                    model=trace.get("model", ""),
                    usage={
                        "input": llm_call.get("tokens_in", 0),
                        "output": llm_call.get("tokens_out", 0),
                    },
                    metadata={"duration_ms": llm_call.get("duration_ms", 0)},
                )

            # Firewall decision
            fw = iteration.get("firewall_decision")
            if fw:
                span.event(
                    name="firewall-decision",
                    metadata=fw,
                    level="ERROR" if fw.get("decision") == "BLOCK" else "DEFAULT",
                )

            span.end()

        # Flush (non-blocking batch send)
        client.flush()
        logger.info("langfuse_trace_sent", trace_id=trace_id)
        return True

    except Exception as e:
        logger.warning("langfuse_send_failed", error=str(e), trace_id=trace.get("trace_id"))
        return False


def _build_tags(trace: dict[str, Any]) -> list[str]:
    """Build Langfuse tags from trace metadata."""
    tags = []
    if trace.get("user_role"):
        tags.append(f"role:{trace['user_role']}")
    if trace.get("intent"):
        tags.append(f"intent:{trace['intent']}")

    counters = trace.get("counters", {})
    if counters.get("tool_calls_blocked", 0) > 0:
        tags.append("has-blocks")
    if trace.get("limits_hit"):
        tags.append("limit-hit")
    if trace.get("errors"):
        tags.append("has-errors")

    return tags
