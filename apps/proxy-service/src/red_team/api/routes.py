"""Red Team API — FastAPI router.

Thin routes that delegate to :class:`BenchmarkService`.
No business logic here.
"""

from __future__ import annotations

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
from src.red_team.progress.emitter import ProgressEmitter

router = APIRouter(prefix="/benchmark", tags=["Red Team Benchmark"])

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

    # TODO: launch engine.execute_run() as background task (Phase 1 integration)
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
    return [RunSummary.model_validate(r) for r in runs]


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
    """Return full details for a benchmark run."""
    run = await svc.get_run(run_id)
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
    results = await svc.list_scenarios(run_id, limit=limit, offset=offset, passed=passed, category=category)
    return [ScenarioResultResponse.model_validate(r) for r in results]


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
    return ScenarioResultResponse.model_validate(result)


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
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if body.auth_header:
        headers["Authorization"] = body.auth_header

    try:
        start = time.monotonic()
        async with _httpx.AsyncClient() as client:
            resp = await client.post(
                body.endpoint_url,
                json={"message": "hello"},
                headers=headers,
                timeout=body.timeout_s,
            )
        latency_ms = int((time.monotonic() - start) * 1000)

        content_type = resp.headers.get("content-type", "")

        if resp.status_code == 401 or resp.status_code == 403:
            return TestConnectionResponse(
                status="error",
                status_code=resp.status_code,
                latency_ms=latency_ms,
                content_type=content_type,
                error=f"HTTP {resp.status_code}",
            )

        return TestConnectionResponse(
            status="ok",
            status_code=resp.status_code,
            latency_ms=latency_ms,
            content_type=content_type,
        )
    except _httpx.TimeoutException:
        return TestConnectionResponse(status="error", error="Timeout")
    except _httpx.ConnectError:
        return TestConnectionResponse(status="error", error="Connection refused")
    except Exception as exc:
        error_msg = str(exc)
        if "ssl" in error_msg.lower() or "certificate" in error_msg.lower():
            return TestConnectionResponse(status="error", error="SSL error")
        return TestConnectionResponse(status="error", error=error_msg[:200])


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
