"""POST /v1/scan — scan-only firewall endpoint (no LLM call).

Runs the pre-LLM pipeline (parse → intent → rules → scanners → decision)
and returns the firewall verdict without forwarding to any LLM provider.

This is the recommended endpoint for agent integrations: the agent calls
/v1/scan to get ALLOW/BLOCK, then makes its own direct LLM call only when
the request is allowed — eliminating the redundant LLM round-trip that the
full /v1/chat/completions endpoint would otherwise perform.
"""

from __future__ import annotations

import time
import uuid

import structlog
from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from src.config import get_settings
from src.pipeline.runner import run_pre_llm_pipeline
from src.schemas.chat import ChatCompletionRequest
from src.services.request_logger import log_request_from_state

logger = structlog.get_logger()

router = APIRouter(tags=["scan"])


@router.post("/v1/scan")
async def scan(
    body: ChatCompletionRequest,
    request: Request,
    x_client_id: str | None = Header(default=None),
    x_policy: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> JSONResponse:
    """Run firewall pipeline and return decision — no LLM call."""
    correlation_id = request.headers.get("x-correlation-id", uuid.uuid4().hex)
    request_id = f"scan-{correlation_id[:24]}"
    start = time.perf_counter()

    messages = [m.model_dump(exclude_none=True) for m in body.messages]
    policy = x_policy or get_settings().default_policy
    settings = get_settings()

    log = logger.bind(
        request_id=request_id,
        model=body.model,
        client_id=x_client_id,
        policy=policy,
        message_count=len(messages),
    )
    log.info("scan_request")

    result = await run_pre_llm_pipeline(
        request_id=request_id,
        client_id=x_client_id,
        policy_name=policy,
        model=body.model,
        messages=messages,
        temperature=body.temperature or settings.default_temperature,
        max_tokens=body.max_tokens,
        stream=False,
        api_key=x_api_key,
    )

    latency_ms = int((time.perf_counter() - start) * 1000)

    decision = result.get("decision", "ALLOW")
    status_code = 403 if decision == "BLOCK" else 200

    # Log to Postgres (the pre-LLM pipeline has no logging node)
    result["latency_ms"] = latency_ms
    try:
        await log_request_from_state(dict(result))
    except Exception as exc:
        logger.error("scan_audit_log_failed", error_type=type(exc).__name__)

    payload = {
        "decision": decision,
        "risk_score": result.get("risk_score", 0.0),
        "risk_flags": result.get("risk_flags", {}),
        "intent": result.get("intent", ""),
        "blocked_reason": result.get("blocked_reason"),
        "scanner_results": result.get("scanner_results"),
        "node_timings": result.get("node_timings"),
    }

    headers = {
        "x-decision": str(decision),
        "x-intent": str(result.get("intent", "")),
        "x-risk-score": f"{result.get('risk_score', 0):.2f}",
    }

    log.info(
        "scan_response",
        decision=decision,
        intent=result.get("intent"),
        risk_score=result.get("risk_score"),
        latency_ms=latency_ms,
    )

    return JSONResponse(
        status_code=status_code,
        content=payload,
        headers=headers,
    )
