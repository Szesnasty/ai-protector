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
) -> AsyncGenerator[str, None]:
    """Convert LiteLLM streaming response to SSE-formatted chunks.

    Yields ``data: {json}\\n\\n`` per token, ending with ``data: [DONE]\\n\\n``.
    After the stream completes, fires a background request-log task.
    """
    created = int(time.time())
    token_count = 0

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

    latency_ms = int((time.perf_counter() - start_time) * 1000) if start_time else 0
    logger.info("stream_complete", request_id=request_id, model=model, approx_tokens=token_count, latency_ms=latency_ms)
