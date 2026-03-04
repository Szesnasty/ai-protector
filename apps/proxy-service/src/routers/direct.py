"""POST /v1/chat/direct — bypass endpoint for Compare demo.

Forwards requests directly to the LLM with ZERO pipeline scanning,
no policy enforcement, no audit logging.  Exists solely so the Compare
Playground can show the difference between protected and unprotected
requests side-by-side.

Controlled by ``ENABLE_DIRECT_ENDPOINT`` env flag (default True in dev).
"""

from __future__ import annotations

import time
import uuid

import structlog
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from src.config import get_settings
from src.llm.client import llm_completion
from src.llm.streaming import sse_stream_direct
from src.schemas.chat import (
    ChatChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    Usage,
)

logger = structlog.get_logger()

router = APIRouter(tags=["chat-direct"])

DIRECT_HEADERS = {
    "x-decision": "DIRECT",
    "x-pipeline": "none",
    "x-risk-score": "0.00",
}


@router.post(
    "/v1/chat/direct",
    response_model=ChatCompletionResponse,
    responses={
        403: {"description": "Direct endpoint disabled"},
        502: {"description": "LLM provider unavailable"},
    },
)
async def chat_direct(
    body: ChatCompletionRequest,
    request: Request,
    x_api_key: str | None = Header(default=None),
) -> ChatCompletionResponse | StreamingResponse:
    """Send prompt directly to LLM — NO scanning, NO policy, NO audit log.

    For Compare demo only.  Shows what happens without AI Protector.
    """
    settings = get_settings()

    if not settings.enable_direct_endpoint:
        raise HTTPException(status_code=403, detail="Direct endpoint disabled")

    correlation_id = request.headers.get("x-correlation-id", uuid.uuid4().hex)
    request_id = f"direct-{correlation_id[:24]}"
    api_key = x_api_key

    messages = [m.model_dump(exclude_none=True) for m in body.messages]

    log = logger.bind(
        request_id=request_id,
        model=body.model,
        stream=body.stream,
        endpoint="direct",
    )
    log.info("direct_request")

    start = time.perf_counter()

    if body.stream:
        llm_stream = await llm_completion(
            messages=messages,
            model=body.model,
            stream=True,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
            api_key=api_key,
        )
        return StreamingResponse(
            sse_stream_direct(llm_stream, request_id, body.model),
            media_type="text/event-stream",
            headers=DIRECT_HEADERS,
        )

    # Non-streaming
    response = await llm_completion(
        messages=messages,
        model=body.model,
        stream=False,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
        api_key=api_key,
    )

    latency_ms = int((time.perf_counter() - start) * 1000)

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

    log.info("direct_response", latency_ms=latency_ms)

    return JSONResponse(
        content=result.model_dump(),
        headers=DIRECT_HEADERS,
    )
