"""SSE streaming helper for LiteLLM responses."""

from __future__ import annotations

import time
from collections.abc import AsyncGenerator
from typing import Any

import structlog

from src.schemas.chat import (
    ChatCompletionChunk,
    ChatCompletionChunkChoice,
    ChatCompletionChunkDelta,
)
from src.services.request_logger import log_request

logger = structlog.get_logger()


async def sse_stream(
    response: AsyncGenerator[Any, None],
    request_id: str,
    model: str,
    *,
    client_id: str | None = None,
    policy_name: str = "balanced",
    messages: list[dict] | None = None,
    start_time: float | None = None,
    intent: str | None = None,
    risk_flags: dict | None = None,
    risk_score: float = 0.0,
    decision: str = "ALLOW",
    blocked_reason: str | None = None,
    scanner_results: dict | None = None,
    node_timings: dict | None = None,
) -> AsyncGenerator[str, None]:
    """Convert LiteLLM streaming response to SSE-formatted chunks.

    Yields ``data: {json}\\n\\n`` per token, ending with ``data: [DONE]\\n\\n``.
    After the stream completes, writes audit log to Postgres.
    """
    created = int(time.time())
    token_count = 0
    logged = False

    async def _audit_log() -> None:
        """Write audit row — called from finally to guarantee delivery."""
        nonlocal logged
        if logged:
            return
        logged = True
        latency_ms = int((time.perf_counter() - start_time) * 1000) if start_time else 0
        logger.info(
            "stream_complete", request_id=request_id, model=model, approx_tokens=token_count, latency_ms=latency_ms
        )
        try:
            await log_request(
                client_id=client_id,
                policy_name=policy_name,
                model=model,
                messages=messages or [],
                decision=decision,
                blocked_reason=blocked_reason,
                intent=intent,
                risk_flags=risk_flags,
                risk_score=risk_score,
                latency_ms=latency_ms,
                tokens_out=token_count,
                scanner_results=scanner_results,
                node_timings=node_timings,
            )
        except Exception:
            logger.exception("stream_audit_log_failed")

    try:
        async for chunk in response:
            choice = chunk.choices[0] if chunk.choices else None
            if choice is None:
                continue

            delta = choice.delta
            content = getattr(delta, "content", None)
            if content:
                token_count += 1

            sse_chunk = ChatCompletionChunk(
                id=request_id,
                created=created,
                model=model,
                choices=[
                    ChatCompletionChunkChoice(
                        index=0,
                        delta=ChatCompletionChunkDelta(
                            role=getattr(delta, "role", None),
                            content=content,
                        ),
                        finish_reason=getattr(choice, "finish_reason", None),
                    )
                ],
            )
            yield f"data: {sse_chunk.model_dump_json()}\n\n"

        yield "data: [DONE]\n\n"

        # ── Audit log to Postgres (normal completion) ─────────────
        await _audit_log()
    except GeneratorExit:
        # Client disconnected — still guarantee audit log
        await _audit_log()
        raise
    except Exception:
        await _audit_log()
        raise


async def sse_stream_direct(
    response: AsyncGenerator[Any, None],
    request_id: str,
    model: str,
) -> AsyncGenerator[str, None]:
    """Minimal SSE streamer for direct (unprotected) endpoint.

    No audit logging, no pipeline metadata — raw LLM stream only.
    """
    created = int(time.time())

    async for chunk in response:
        choice = chunk.choices[0] if chunk.choices else None
        if choice is None:
            continue

        delta = choice.delta
        content = getattr(delta, "content", None)

        sse_chunk = ChatCompletionChunk(
            id=request_id,
            created=created,
            model=model,
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta=ChatCompletionChunkDelta(
                        role=getattr(delta, "role", None),
                        content=content,
                    ),
                    finish_reason=getattr(choice, "finish_reason", None),
                )
            ],
        )
        yield f"data: {sse_chunk.model_dump_json()}\n\n"

    yield "data: [DONE]\n\n"
