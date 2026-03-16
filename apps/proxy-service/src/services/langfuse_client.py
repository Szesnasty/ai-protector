"""Langfuse client singleton for tracing pipeline requests.

Provides a cached ``Langfuse`` client and helper functions to create traces
and spans for each pipeline stage.  All errors are swallowed so tracing
never blocks the request/response path.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import structlog

from src.config import get_settings

logger = structlog.get_logger()


@lru_cache
def get_langfuse():  # noqa: ANN201
    """Return a cached ``Langfuse`` client, or ``None`` if init fails."""
    settings = get_settings()
    if not settings.enable_langfuse:
        logger.info("langfuse_disabled")
        return None

    try:
        from langfuse import Langfuse

        client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
        logger.info("langfuse_client_ready", host=settings.langfuse_host)
        return client
    except Exception:
        logger.warning("langfuse_init_failed")
        return None


def reset_langfuse() -> None:
    """Clear the cached client (for testing)."""
    get_langfuse.cache_clear()


async def create_trace(
    *,
    trace_id: str,
    name: str = "ai-protector-request",
    input_data: dict[str, Any] | None = None,
    output_data: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    tags: list[str] | None = None,
    user_id: str | None = None,
    session_id: str | None = None,
) -> Any | None:
    """Create a Langfuse trace with pipeline data.

    Returns the trace object or ``None``.  All errors are swallowed.
    """
    client = get_langfuse()
    if client is None:
        return None

    try:
        trace = client.trace(
            id=trace_id,
            name=name,
            input=input_data,
            output=output_data,
            metadata=metadata,
            tags=tags or [],
            user_id=user_id,
            session_id=session_id,
        )
        return trace
    except Exception as exc:
        logger.error("langfuse_trace_failed", trace_id=trace_id, error_type=type(exc).__name__)
        return None


async def add_pipeline_spans(
    trace: Any,
    node_timings: dict[str, float],
) -> None:
    """Add one span per pipeline node to an existing trace.

    Errors on individual spans are swallowed.
    """
    if trace is None:
        return

    for node_name, duration_ms in node_timings.items():
        try:
            trace.span(
                name=node_name,
                metadata={"duration_ms": duration_ms},
            )
        except Exception:
            logger.warning("langfuse_span_failed", node=node_name)
