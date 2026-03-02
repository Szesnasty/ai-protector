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
) -> AsyncGenerator[str, None]:
    """Convert LiteLLM streaming response to SSE-formatted chunks.

    Yields ``data: {json}\\n\\n`` per token, ending with ``data: [DONE]\\n\\n``.
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

    logger.info("stream_complete", request_id=request_id, model=model, approx_tokens=token_count)
