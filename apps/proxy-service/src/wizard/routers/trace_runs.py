"""Structured agent trace runs router (spec tracing).

Endpoints:
  POST  /agents/{id}/traces/ingest          — ingest a full trace from an agent
  GET   /agents/{id}/traces/runs             — list trace summaries (paginated)
  GET   /agents/{id}/traces/runs/{trace_id}  — full trace detail
"""

from __future__ import annotations

import uuid
from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.wizard.models import Agent, AgentTraceRun
from src.wizard.schemas import (
    TraceRunCreate,
    TraceRunDetail,
    TraceRunListResponse,
    TraceRunSummary,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/agents/{agent_id}", tags=["trace-runs"])

MAX_PAYLOAD_BYTES = 512 * 1024  # 512 KB cap on iterations JSONB


# ── Helpers ──────────────────────────────────────────────────────────


async def _get_agent_or_404(agent_id: uuid.UUID, db: AsyncSession) -> Agent:
    agent = await db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


def _row_to_summary(row: AgentTraceRun) -> TraceRunSummary:
    counters = row.counters or {}
    iterations = row.iterations or []

    firewall_blocked = any((it.get("firewall_decision") or {}).get("decision") == "BLOCK" for it in iterations)

    return TraceRunSummary(
        trace_id=row.trace_id,
        agent_id=row.agent_id,
        session_id=row.session_id,
        timestamp=row.timestamp,
        user_role=row.user_role,
        model=row.model,
        intent=row.intent,
        total_duration_ms=row.total_duration_ms,
        iterations_count=counters.get("iterations", len(iterations)),
        tool_calls_count=counters.get("tool_calls", 0),
        tool_calls_blocked=counters.get("tool_calls_blocked", 0),
        firewall_blocked=firewall_blocked,
        tokens_in=counters.get("tokens_in", 0),
        tokens_out=counters.get("tokens_out", 0),
        has_errors=len(row.errors or []) > 0,
        limits_hit=row.limits_hit,
    )


def _row_to_detail(row: AgentTraceRun) -> TraceRunDetail:
    details = row.details or {}
    return TraceRunDetail(
        trace_id=row.trace_id,
        agent_id=row.agent_id,
        session_id=row.session_id,
        timestamp=row.timestamp,
        user_role=row.user_role,
        model=row.model,
        intent=row.intent,
        intent_confidence=details.get("intent_confidence", 0.0),
        total_duration_ms=row.total_duration_ms,
        counters=row.counters or {},
        iterations=row.iterations or [],
        errors=row.errors or [],
        limits_hit=row.limits_hit,
        user_message=details.get("user_message"),
        final_response=details.get("final_response"),
        policy=details.get("policy"),
        node_timings=details.get("node_timings"),
    )


# ═══════════════════════════════════════════════════════════════════════
# Ingest
# ═══════════════════════════════════════════════════════════════════════


@router.post("/traces/ingest", status_code=201, response_model=TraceRunSummary)
async def ingest_trace_run(
    agent_id: uuid.UUID,
    body: TraceRunCreate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> TraceRunSummary:
    """Ingest a full structured agent trace."""
    await _get_agent_or_404(agent_id, db)

    # Size guard
    import json as _json

    payload_size = len(_json.dumps(body.iterations, default=str).encode())
    if payload_size > MAX_PAYLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"iterations payload too large ({payload_size} bytes, max {MAX_PAYLOAD_BYTES})",
        )

    # Pack overflow fields into details JSONB
    details: dict = {}
    if body.user_message is not None:
        details["user_message"] = body.user_message
    if body.final_response is not None:
        details["final_response"] = body.final_response
    if body.policy is not None:
        details["policy"] = body.policy
    if body.node_timings is not None:
        details["node_timings"] = body.node_timings
    if body.intent_confidence:
        details["intent_confidence"] = body.intent_confidence

    row = AgentTraceRun(
        agent_id=agent_id,
        trace_id=body.trace_id,
        session_id=body.session_id,
        timestamp=body.timestamp or datetime.utcnow(),
        user_role=body.user_role,
        model=body.model,
        intent=body.intent,
        total_duration_ms=body.total_duration_ms,
        counters=body.counters,
        iterations=body.iterations,
        errors=body.errors,
        limits_hit=body.limits_hit,
        details=details or None,
    )

    db.add(row)
    await db.commit()
    await db.refresh(row)

    logger.info(
        "trace_run_ingested",
        trace_id=body.trace_id,
        agent_id=str(agent_id),
        session_id=body.session_id,
    )
    return _row_to_summary(row)


# ═══════════════════════════════════════════════════════════════════════
# List
# ═══════════════════════════════════════════════════════════════════════


@router.get("/traces/runs", response_model=TraceRunListResponse)
async def list_trace_runs(
    agent_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=200),  # noqa: B008
    offset: int = Query(0, ge=0),  # noqa: B008
    session_id: str | None = None,
    user_role: str | None = None,
    has_blocks: bool | None = None,
    date_from: datetime | None = Query(None, alias="from"),  # noqa: B008
    date_to: datetime | None = Query(None, alias="to"),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> TraceRunListResponse:
    """List structured trace runs for an agent (paginated + filtered)."""
    await _get_agent_or_404(agent_id, db)

    stmt = select(AgentTraceRun).where(AgentTraceRun.agent_id == agent_id)
    count_stmt = select(func.count()).select_from(AgentTraceRun).where(AgentTraceRun.agent_id == agent_id)

    if session_id:
        stmt = stmt.where(AgentTraceRun.session_id == session_id)
        count_stmt = count_stmt.where(AgentTraceRun.session_id == session_id)
    if user_role:
        stmt = stmt.where(AgentTraceRun.user_role == user_role)
        count_stmt = count_stmt.where(AgentTraceRun.user_role == user_role)
    if date_from:
        stmt = stmt.where(AgentTraceRun.timestamp >= date_from)
        count_stmt = count_stmt.where(AgentTraceRun.timestamp >= date_from)
    if date_to:
        stmt = stmt.where(AgentTraceRun.timestamp <= date_to)
        count_stmt = count_stmt.where(AgentTraceRun.timestamp <= date_to)

    # has_blocks filter requires checking counters JSONB
    if has_blocks is not None:
        if has_blocks:
            stmt = stmt.where(AgentTraceRun.counters["tool_calls_blocked"].as_integer() > 0)
            count_stmt = count_stmt.where(AgentTraceRun.counters["tool_calls_blocked"].as_integer() > 0)
        else:
            stmt = stmt.where(
                (AgentTraceRun.counters["tool_calls_blocked"].as_integer() == 0)
                | (AgentTraceRun.counters["tool_calls_blocked"] == None)  # noqa: E711
            )
            count_stmt = count_stmt.where(
                (AgentTraceRun.counters["tool_calls_blocked"].as_integer() == 0)
                | (AgentTraceRun.counters["tool_calls_blocked"] == None)  # noqa: E711
            )

    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = stmt.order_by(AgentTraceRun.timestamp.desc())
    stmt = stmt.offset(offset).limit(limit)

    rows = (await db.execute(stmt)).scalars().all()

    return TraceRunListResponse(
        items=[_row_to_summary(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


# ═══════════════════════════════════════════════════════════════════════
# Detail
# ═══════════════════════════════════════════════════════════════════════


@router.get("/traces/runs/{trace_id}", response_model=TraceRunDetail)
async def get_trace_run(
    agent_id: uuid.UUID,
    trace_id: str,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> TraceRunDetail:
    """Get full structured trace detail by trace_id."""
    await _get_agent_or_404(agent_id, db)

    stmt = select(AgentTraceRun).where(
        AgentTraceRun.agent_id == agent_id,
        AgentTraceRun.trace_id == trace_id,
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Trace run '{trace_id}' not found")

    return _row_to_detail(row)
