"""POST /v1/chat/completions — OpenAI-compatible chat endpoint."""

from __future__ import annotations

import asyncio
import time
import uuid

import structlog
from fastapi import APIRouter, Header, Request
from fastapi.responses import StreamingResponse

from src.config import get_settings
from src.llm.client import llm_completion
from src.llm.streaming import sse_stream
from src.schemas.chat import (
    ChatChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    Usage,
)
from src.services.request_logger import log_request

logger = structlog.get_logger()

router = APIRouter(tags=["chat"])


@router.post(
    "/v1/chat/completions",
    response_model=ChatCompletionResponse,
    responses={
        502: {"description": "LLM provider unavailable"},
        504: {"description": "LLM request timed out"},
        404: {"description": "Model not found"},
    },
)
async def chat_completions(
    body: ChatCompletionRequest,
    request: Request,
    x_client_id: str | None = Header(default=None),
    x_policy: str | None = Header(default=None),
) -> ChatCompletionResponse | StreamingResponse:
    """OpenAI-compatible chat completions (streaming & non-streaming)."""
    request_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    start = time.perf_counter()

    messages = [m.model_dump(exclude_none=True) for m in body.messages]

    log = logger.bind(
        request_id=request_id,
        model=body.model,
        stream=body.stream,
        client_id=x_client_id,
        policy=x_policy,
        message_count=len(messages),
    )
    log.info("chat_request")

    policy = x_policy or get_settings().default_policy

    if body.stream:
        response = await llm_completion(
            messages=messages,
            model=body.model,
            stream=True,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
        )
        generator = sse_stream(
            response=response,
            request_id=request_id,
            model=body.model,
            client_id=x_client_id,
            policy_name=policy,
            messages=messages,
            start_time=start,
        )
        return StreamingResponse(generator, media_type="text/event-stream")

    # Non-streaming
    response = await llm_completion(
        messages=messages,
        model=body.model,
        stream=False,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
    )

    latency_ms = int((time.perf_counter() - start) * 1000)

    # Transform LiteLLM response → our schema
    choice = response.choices[0]
    usage_info = getattr(response, "usage", None)

    result = ChatCompletionResponse(
        id=request_id,
        created=int(time.time()),
        model=body.model,
        choices=[
            ChatChoice(
                index=0,
                message=ChatMessage(
                    role=choice.message.role,
                    content=choice.message.content or "",
                ),
                finish_reason=getattr(choice, "finish_reason", "stop"),
            )
        ],
        usage=Usage(
            prompt_tokens=getattr(usage_info, "prompt_tokens", 0),
            completion_tokens=getattr(usage_info, "completion_tokens", 0),
            total_tokens=getattr(usage_info, "total_tokens", 0),
        )
        if usage_info
        else None,
    )

    log.info(
        "chat_response",
        latency_ms=latency_ms,
        finish_reason=choice.finish_reason,
        prompt_tokens=getattr(usage_info, "prompt_tokens", None),
        completion_tokens=getattr(usage_info, "completion_tokens", None),
    )

    # Fire-and-forget request logging
    asyncio.create_task(
        log_request(
            client_id=x_client_id,
            policy_name=policy,
            model=body.model,
            messages=messages,
            decision="ALLOW",
            latency_ms=latency_ms,
            tokens_in=getattr(usage_info, "prompt_tokens", None),
            tokens_out=getattr(usage_info, "completion_tokens", None),
        )
    )

    return result
