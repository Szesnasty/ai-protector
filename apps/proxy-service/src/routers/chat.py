"""POST /v1/chat/completions — OpenAI-compatible chat endpoint with pipeline."""

from __future__ import annotations

import asyncio
import time
import uuid

import structlog
from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse, StreamingResponse

from src.config import get_settings
from src.llm.client import llm_completion
from src.llm.streaming import sse_stream
from src.pipeline.runner import run_pipeline, run_pre_llm_pipeline
from src.pipeline.state import PipelineState
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


def _pipeline_headers(state: PipelineState) -> dict[str, str]:
    """Build response headers from pipeline state."""
    return {
        "x-decision": str(state.get("decision", "")),
        "x-intent": str(state.get("intent", "")),
        "x-risk-score": f"{state.get('risk_score', 0):.2f}",
    }


def _block_response(state: PipelineState) -> JSONResponse:
    """Return 403 JSONResponse for BLOCK decisions."""
    return JSONResponse(
        status_code=403,
        content={
            "error": {
                "message": state.get("blocked_reason", "Request blocked"),
                "type": "policy_violation",
                "code": "blocked",
            },
            "decision": state.get("decision"),
            "risk_score": state.get("risk_score", 0),
            "risk_flags": state.get("risk_flags", {}),
            "intent": state.get("intent"),
        },
        headers=_pipeline_headers(state),
    )


def _build_chat_response(
    state: PipelineState,
    request_id: str,
    model: str,
) -> ChatCompletionResponse:
    """Extract ChatCompletionResponse from pipeline state's llm_response."""
    llm_resp = state["llm_response"]
    choice = llm_resp.choices[0]
    usage_info = getattr(llm_resp, "usage", None)

    return ChatCompletionResponse(
        id=request_id,
        created=int(time.time()),
        model=model,
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


@router.post(
    "/v1/chat/completions",
    response_model=ChatCompletionResponse,
    responses={
        403: {"description": "Request blocked by policy"},
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
) -> ChatCompletionResponse | JSONResponse | StreamingResponse:
    """OpenAI-compatible chat completions with firewall pipeline."""
    correlation_id = request.headers.get("x-correlation-id", uuid.uuid4().hex)
    request_id = f"chatcmpl-{correlation_id[:24]}"
    start = time.perf_counter()

    messages = [m.model_dump(exclude_none=True) for m in body.messages]
    policy = x_policy or get_settings().default_policy

    log = logger.bind(
        request_id=request_id,
        model=body.model,
        stream=body.stream,
        client_id=x_client_id,
        policy=policy,
        message_count=len(messages),
    )
    log.info("chat_request")

    if body.stream:
        # Run pre-LLM pipeline (parse→intent→rules→decision)
        pre_result = await run_pre_llm_pipeline(
            request_id=request_id,
            client_id=x_client_id,
            policy_name=policy,
            model=body.model,
            messages=messages,
            temperature=body.temperature or get_settings().default_temperature,
            max_tokens=body.max_tokens,
            stream=True,
        )

        if pre_result["decision"] == "BLOCK":
            latency_ms = int((time.perf_counter() - start) * 1000)
            asyncio.create_task(
                log_request(
                    client_id=x_client_id,
                    policy_name=policy,
                    model=body.model,
                    messages=messages,
                    decision="BLOCK",
                    blocked_reason=pre_result.get("blocked_reason"),
                    intent=pre_result.get("intent"),
                    risk_flags=pre_result.get("risk_flags"),
                    risk_score=pre_result.get("risk_score", 0.0),
                    latency_ms=latency_ms,
                )
            )
            return _block_response(pre_result)

        # ALLOW or MODIFY — stream from LLM
        stream_messages = pre_result.get("modified_messages") or messages
        llm_stream = await llm_completion(
            messages=stream_messages,
            model=body.model,
            stream=True,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
        )
        generator = sse_stream(
            response=llm_stream,
            request_id=request_id,
            model=body.model,
            client_id=x_client_id,
            policy_name=policy,
            messages=messages,
            start_time=start,
            intent=pre_result.get("intent"),
            risk_flags=pre_result.get("risk_flags"),
            risk_score=pre_result.get("risk_score", 0.0),
            decision=pre_result.get("decision", "ALLOW"),
        )
        return StreamingResponse(
            generator,
            media_type="text/event-stream",
            headers=_pipeline_headers(pre_result),
        )

    # ── Non-streaming ─────────────────────────────────────────────
    result = await run_pipeline(
        request_id=request_id,
        client_id=x_client_id,
        policy_name=policy,
        model=body.model,
        messages=messages,
        temperature=body.temperature or get_settings().default_temperature,
        max_tokens=body.max_tokens,
        stream=False,
    )

    latency_ms = int((time.perf_counter() - start) * 1000)

    if result["decision"] == "BLOCK":
        asyncio.create_task(
            log_request(
                client_id=x_client_id,
                policy_name=policy,
                model=body.model,
                messages=messages,
                decision="BLOCK",
                blocked_reason=result.get("blocked_reason"),
                intent=result.get("intent"),
                risk_flags=result.get("risk_flags"),
                risk_score=result.get("risk_score", 0.0),
                latency_ms=latency_ms,
            )
        )
        return _block_response(result)

    # ALLOW / MODIFY → build response
    response = _build_chat_response(result, request_id, body.model)

    log.info(
        "chat_response",
        decision=result.get("decision"),
        intent=result.get("intent"),
        risk_score=result.get("risk_score"),
        latency_ms=latency_ms,
    )

    asyncio.create_task(
        log_request(
            client_id=x_client_id,
            policy_name=policy,
            model=body.model,
            messages=messages,
            decision=result.get("decision", "ALLOW"),
            intent=result.get("intent"),
            risk_flags=result.get("risk_flags"),
            risk_score=result.get("risk_score", 0.0),
            latency_ms=latency_ms,
            tokens_in=result.get("tokens_in"),
            tokens_out=result.get("tokens_out"),
        )
    )

    return JSONResponse(
        content=response.model_dump(),
        headers=_pipeline_headers(result),
    )
