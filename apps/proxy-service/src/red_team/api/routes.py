"""Red Team API — FastAPI router.

Thin routes that delegate to :class:`BenchmarkService`.
No business logic here.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import AsyncGenerator

import httpx as _httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.red_team.api import (
    CompareResponse,
    CreateRunRequest,
    ErrorResponse,
    PackInfoResponse,
    RunCreatedResponse,
    RunDetailResponse,
    RunSummary,
    ScenarioResultResponse,
    TestConnectionRequest,
    TestConnectionResponse,
)
from src.red_team.api.service import BenchmarkService
from src.red_team.engine.worker import run_benchmark_background
from src.red_team.net import rewrite_localhost_for_docker, validate_url
from src.red_team.packs import load_pack
from src.red_team.progress.emitter import ProgressEmitter

router = APIRouter(prefix="/benchmark", tags=["Red Team Benchmark"])


def _enrich_scenario(resp: ScenarioResultResponse, pack_name: str) -> ScenarioResultResponse:
    """Look up scenario metadata from the pack YAML and inject title/description/why/fix."""
    try:
        pack = load_pack(pack_name)
        for s in pack.scenarios:
            if s.id == resp.scenario_id:
                resp.title = s.title
                resp.description = getattr(s, "description", None) or None
                resp.why_it_passes = getattr(s, "why_it_passes", None) or None
                raw_hints = getattr(s, "fix_hints", None) or []
                resp.fix_hints = list(raw_hints)
                break
    except Exception:
        pass  # Enrichment is best-effort
    return resp


# Singleton progress emitter shared across requests
_progress_emitter = ProgressEmitter()


def _get_service(
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> BenchmarkService:
    return BenchmarkService(db)


# ---------------------------------------------------------------------------
# POST /v1/benchmark/runs — create & start
# ---------------------------------------------------------------------------


@router.post(
    "/runs",
    response_model=RunCreatedResponse,
    status_code=201,
    responses={409: {"model": ErrorResponse}},
)
async def create_run(
    body: CreateRunRequest,
    svc: BenchmarkService = Depends(_get_service),  # noqa: B008
) -> RunCreatedResponse:
    """Create and schedule a new benchmark run."""
    from src.red_team.engine.run_engine import ConcurrencyConflictError

    try:
        run = await svc.create_run(
            target_type=body.target_type,
            target_config=body.target_config,
            pack=body.pack,
            policy=body.policy,
            source_run_id=body.source_run_id,
            idempotency_key=body.idempotency_key,
        )
    except ConcurrencyConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    # Launch engine execution as a background task
    asyncio.create_task(run_benchmark_background(run.id, _progress_emitter))

    return RunCreatedResponse(
        id=run.id,
        status=run.status,
        pack=run.pack,
        total_in_pack=run.total_in_pack,
        total_applicable=run.total_applicable,
    )


# ---------------------------------------------------------------------------
# GET /v1/benchmark/runs — list
# ---------------------------------------------------------------------------


@router.get("/runs", response_model=list[RunSummary])
async def list_runs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    target_type: str | None = Query(None),
    svc: BenchmarkService = Depends(_get_service),  # noqa: B008
) -> list[RunSummary]:
    """List benchmark runs, newest first."""
    runs = await svc.list_runs(limit=limit, offset=offset, target_type=target_type)
    result: list[RunSummary] = []
    for r in runs:
        summary = RunSummary.model_validate(r)
        cfg = r.target_config or {}
        summary.target_label = cfg.get("target_name") or cfg.get("endpoint_url") or ""
        result.append(summary)
    return result


# ---------------------------------------------------------------------------
# GET /v1/benchmark/runs/:id — detail
# ---------------------------------------------------------------------------


@router.get(
    "/runs/{run_id}",
    response_model=RunDetailResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_run(
    run_id: uuid.UUID,
    svc: BenchmarkService = Depends(_get_service),  # noqa: B008
) -> RunDetailResponse:
    """Return full details for a benchmark run (auth secrets masked)."""
    run = await svc.get_run_safe(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return RunDetailResponse.model_validate(run)


# ---------------------------------------------------------------------------
# GET /v1/benchmark/runs/:id/scenarios — scenario results
# ---------------------------------------------------------------------------


@router.get(
    "/runs/{run_id}/scenarios",
    response_model=list[ScenarioResultResponse],
    responses={404: {"model": ErrorResponse}},
)
async def list_scenarios(
    run_id: uuid.UUID,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    passed: bool | None = Query(None),
    category: str | None = Query(None),
    svc: BenchmarkService = Depends(_get_service),  # noqa: B008
) -> list[ScenarioResultResponse]:
    """List scenario results for a specific run."""
    # Get pack name for enrichment
    run = await svc.get_run_safe(run_id)
    pack_name = run.pack if run else ""

    results = await svc.list_scenarios(run_id, limit=limit, offset=offset, passed=passed, category=category)
    return [_enrich_scenario(ScenarioResultResponse.model_validate(r), pack_name) for r in results]


# ---------------------------------------------------------------------------
# GET /v1/benchmark/runs/:id/scenarios/:sid — single scenario
# ---------------------------------------------------------------------------


@router.get(
    "/runs/{run_id}/scenarios/{scenario_id}",
    response_model=ScenarioResultResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_scenario(
    run_id: uuid.UUID,
    scenario_id: str,
    svc: BenchmarkService = Depends(_get_service),  # noqa: B008
) -> ScenarioResultResponse:
    """Return full detail for a single scenario result."""
    result = await svc.get_scenario(run_id, scenario_id)
    if not result:
        raise HTTPException(status_code=404, detail="Scenario result not found")

    # Get pack name for enrichment
    run = await svc.get_run_safe(run_id)
    pack_name = run.pack if run else ""

    return _enrich_scenario(ScenarioResultResponse.model_validate(result), pack_name)


# ---------------------------------------------------------------------------
# DELETE /v1/benchmark/runs/:id — cancel or delete
# ---------------------------------------------------------------------------


@router.delete(
    "/runs/{run_id}",
    status_code=204,
    responses={404: {"model": ErrorResponse}},
)
async def delete_run(
    run_id: uuid.UUID,
    svc: BenchmarkService = Depends(_get_service),  # noqa: B008
) -> None:
    """Cancel a running run or delete a finished one."""
    found = await svc.delete_run(run_id)
    if not found:
        raise HTTPException(status_code=404, detail="Run not found")


# ---------------------------------------------------------------------------
# GET /v1/benchmark/runs/:id/progress — SSE stream
# ---------------------------------------------------------------------------


@router.get("/runs/{run_id}/progress")
async def run_progress(run_id: uuid.UUID) -> StreamingResponse:
    """SSE stream of benchmark progress events."""

    async def _event_generator() -> AsyncGenerator[str, None]:
        async for event in _progress_emitter.subscribe(run_id):
            yield event

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# POST /v1/benchmark/test-connection — connectivity check
# ---------------------------------------------------------------------------


@router.post("/test-connection", response_model=TestConnectionResponse)
async def test_connection(body: TestConnectionRequest) -> TestConnectionResponse:
    """Ping a target endpoint to verify reachability.

    Auth header is used for this request only; it is NOT persisted.
    """
    raw_url = rewrite_localhost_for_docker(body.endpoint_url)
    safe_url = validate_url(raw_url)
    if safe_url is None:
        return TestConnectionResponse(
            status="error",
            error="Endpoint URL is not allowed (invalid scheme or internal address)",
            error_code="invalid_endpoint_url",
        )
    headers: dict[str, str] = {"Content-Type": "application/json"}
    # Support both legacy auth_header and new custom_headers
    if body.custom_headers:
        headers.update(body.custom_headers)
    elif body.auth_header:
        headers["Authorization"] = body.auth_header

    # Use custom body if provided, otherwise default chat payload
    request_body = (
        body.custom_body if body.custom_body is not None else {"messages": [{"role": "user", "content": "hello"}]}
    )

    def _snippet(text: str, max_len: int = 500) -> str:
        """Return first *max_len* chars of *text* for diagnostics."""
        return text[:max_len] if len(text) > max_len else text

    try:
        start = time.monotonic()
        async with _httpx.AsyncClient() as client:
            resp = await client.post(
                safe_url,
                json=request_body,
                headers=headers,
                timeout=body.timeout_s,
            )
        latency_ms = int((time.monotonic() - start) * 1000)

        content_type = resp.headers.get("content-type", "")
        resp_text = resp.text

        rewritten = raw_url != body.endpoint_url

        if resp.status_code == 401 or resp.status_code == 403:
            return TestConnectionResponse(
                status="error",
                status_code=resp.status_code,
                latency_ms=latency_ms,
                content_type=content_type,
                error=f"HTTP {resp.status_code}",
                error_code="auth_invalid",
                resolved_url=safe_url if rewritten else None,
                body_snippet=_snippet(resp_text),
            )

        if resp.status_code >= 500:
            return TestConnectionResponse(
                status="error",
                status_code=resp.status_code,
                latency_ms=latency_ms,
                content_type=content_type,
                error=f"Server error (HTTP {resp.status_code})",
                error_code="server_error",
                resolved_url=safe_url if rewritten else None,
                body_snippet=_snippet(resp_text),
            )

        if resp.status_code >= 400 and resp.status_code != 422:
            return TestConnectionResponse(
                status="error",
                status_code=resp.status_code,
                latency_ms=latency_ms,
                content_type=content_type,
                error=f"Client error (HTTP {resp.status_code})",
                error_code="client_error",
                resolved_url=safe_url if rewritten else None,
                body_snippet=_snippet(resp_text),
            )

        # Auto-detect text paths in JSON responses
        detected_paths: list[str] | None = None
        if content_type and "json" in content_type:
            try:
                import json as _json

                from src.red_team.engine.json_text_extractor import detect_text_paths

                parsed = _json.loads(resp_text)
                detected_paths = detect_text_paths(parsed) or None
            except Exception:
                pass

        return TestConnectionResponse(
            status="ok",
            status_code=resp.status_code,
            latency_ms=latency_ms,
            content_type=content_type,
            resolved_url=safe_url if rewritten else None,
            response_body=_snippet(resp_text, 2000),
            detected_text_paths=detected_paths,
        )
    except _httpx.TimeoutException:
        return TestConnectionResponse(status="error", error="Timeout", error_code="timeout")
    except _httpx.ConnectError:
        return TestConnectionResponse(
            status="error",
            error="Connection refused",
            error_code="connection_failed",
            resolved_url=safe_url if raw_url != body.endpoint_url else None,
        )
    except Exception as exc:
        error_msg = str(exc)
        if "ssl" in error_msg.lower() or "certificate" in error_msg.lower():
            return TestConnectionResponse(status="error", error="SSL error", error_code="ssl_error")
        return TestConnectionResponse(status="error", error=error_msg[:200], error_code="internal_error")


# ---------------------------------------------------------------------------
# GET /v1/benchmark/packs — list available packs
# ---------------------------------------------------------------------------


@router.get("/packs", response_model=list[PackInfoResponse])
async def list_packs() -> list[PackInfoResponse]:
    """Return available attack packs with metadata."""
    packs = BenchmarkService.list_packs()
    return [
        PackInfoResponse(
            name=p.name,
            display_name=p.display_name,
            description=p.description,
            version=p.version,
            scenario_count=p.scenario_count,
            applicable_to=p.applicable_to,
        )
        for p in packs
    ]


# ---------------------------------------------------------------------------
# GET /v1/benchmark/compare — diff two runs
# ---------------------------------------------------------------------------


@router.get(
    "/compare",
    response_model=CompareResponse,
    responses={404: {"model": ErrorResponse}},
)
async def compare_runs(
    a: uuid.UUID = Query(..., description="Run A (before)"),
    b: uuid.UUID = Query(..., description="Run B (after)"),
    svc: BenchmarkService = Depends(_get_service),  # noqa: B008
) -> CompareResponse:
    """Compare two benchmark runs — score delta + fixed/new failures."""
    result = await svc.compare_runs(a, b)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return CompareResponse(
        run_a_id=a,
        run_b_id=b,
        score_delta=result["score_delta"],
        weighted_delta=result["weighted_delta"],
        warning=result.get("warning"),
        run_a=RunSummary.model_validate(result["run_a"]),
        run_b=RunSummary.model_validate(result["run_b"]),
        fixed_failures=result["fixed_failures"],
        new_failures=result["new_failures"],
    )
