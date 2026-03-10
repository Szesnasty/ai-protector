"""Traces & incidents router (Agent Wizard — spec 32d/e).

Endpoints:
  POST   /agents/:id/traces/record      — record a trace (uses TraceRecorder)
  GET    /agents/:id/traces              — list traces (paginated + filtered)
  GET    /agents/:id/traces/stats        — aggregated stats
  GET    /agents/:id/incidents           — list incidents
  PATCH  /agents/:id/incidents/:iid      — update incident status
"""

from __future__ import annotations

import uuid
from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.wizard.models import (
    Agent,
    AgentIncident,
    AgentTrace,
    IncidentCategory,
    IncidentSeverity,
    IncidentStatus,
    RolloutMode,
    TraceDecision,
    TraceGate,
)
from src.wizard.schemas import (
    IncidentListResponse,
    IncidentRead,
    IncidentStatsBreakdown,
    IncidentUpdate,
    TraceCreate,
    TraceListResponse,
    TraceRead,
    TraceStatsResponse,
)
from src.wizard.services.trace_recorder import TraceRecorder

logger = structlog.get_logger()

router = APIRouter(prefix="/agents/{agent_id}", tags=["traces"])


# ── Helpers ──────────────────────────────────────────────────────────


async def _get_agent_or_404(agent_id: uuid.UUID, db: AsyncSession) -> Agent:
    agent = await db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


# ═══════════════════════════════════════════════════════════════════════
# 32d — Record trace
# ═══════════════════════════════════════════════════════════════════════


@router.post("/traces/record", status_code=201, response_model=TraceRead)
async def record_trace(
    agent_id: uuid.UUID,
    body: TraceCreate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> TraceRead:
    """Record a gate evaluation trace for an agent."""
    await _get_agent_or_404(agent_id, db)

    recorder = TraceRecorder(db)
    trace = await recorder.record(
        agent_id=agent_id,
        session_id=body.session_id,
        gate=body.gate,
        tool_name=body.tool_name,
        role=body.role,
        decision=body.decision,
        reason=body.reason,
        category=body.category,
        rollout_mode=body.rollout_mode,
        enforced=body.enforced,
        latency_ms=body.latency_ms,
        details=body.details,
    )

    return _trace_to_read(trace)


# ═══════════════════════════════════════════════════════════════════════
# 32d — List traces (paginated + filtered)
# ═══════════════════════════════════════════════════════════════════════


@router.get("/traces/list", response_model=TraceListResponse)
async def list_agent_traces(
    agent_id: uuid.UUID,
    page: int = Query(1, ge=1),  # noqa: B008
    per_page: int = Query(50, ge=1, le=200),  # noqa: B008
    gate: TraceGate | None = None,
    decision: TraceDecision | None = None,
    category: str | None = None,
    rollout_mode: RolloutMode | None = None,
    session_id: str | None = None,
    from_dt: datetime | None = Query(None, alias="from"),  # noqa: B008
    to_dt: datetime | None = Query(None, alias="to"),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> TraceListResponse:
    """List agent traces with optional filters and pagination."""
    await _get_agent_or_404(agent_id, db)

    stmt = select(AgentTrace).where(AgentTrace.agent_id == agent_id)

    if gate is not None:
        stmt = stmt.where(AgentTrace.gate == gate)
    if decision is not None:
        stmt = stmt.where(AgentTrace.decision == decision)
    if category is not None:
        stmt = stmt.where(AgentTrace.category == category)
    if rollout_mode is not None:
        stmt = stmt.where(AgentTrace.rollout_mode == rollout_mode)
    if session_id is not None:
        stmt = stmt.where(AgentTrace.session_id == session_id)
    if from_dt is not None:
        stmt = stmt.where(AgentTrace.timestamp >= from_dt)
    if to_dt is not None:
        stmt = stmt.where(AgentTrace.timestamp <= to_dt)

    # Count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    # Order + paginate
    stmt = stmt.order_by(AgentTrace.timestamp.desc())
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(stmt)
    traces = result.scalars().all()

    return TraceListResponse(
        items=[_trace_to_read(t) for t in traces],
        total=total,
        page=page,
        per_page=per_page,
    )


# ═══════════════════════════════════════════════════════════════════════
# 32e — Trace statistics
# ═══════════════════════════════════════════════════════════════════════


@router.get("/traces/stats", response_model=TraceStatsResponse)
async def trace_stats(
    agent_id: uuid.UUID,
    from_dt: datetime | None = Query(None, alias="from"),  # noqa: B008
    to_dt: datetime | None = Query(None, alias="to"),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> TraceStatsResponse:
    """Aggregated trace statistics for an agent."""
    await _get_agent_or_404(agent_id, db)

    base = select(AgentTrace).where(AgentTrace.agent_id == agent_id)
    if from_dt is not None:
        base = base.where(AgentTrace.timestamp >= from_dt)
    if to_dt is not None:
        base = base.where(AgentTrace.timestamp <= to_dt)

    sub = base.subquery()

    # Total evaluations
    total = (await db.execute(select(func.count()).select_from(sub))).scalar_one()

    # Avg latency
    avg_lat = (await db.execute(select(func.avg(sub.c.latency_ms)))).scalar_one() or 0.0

    # By decision
    by_decision: dict[str, int] = {}
    rows = (await db.execute(select(sub.c.decision, func.count()).group_by(sub.c.decision))).all()
    for row in rows:
        by_decision[row[0]] = row[1]

    # By category
    by_category: dict[str, int] = {}
    rows = (await db.execute(select(sub.c.category, func.count()).group_by(sub.c.category))).all()
    for row in rows:
        by_category[row[0]] = row[1]

    # By gate
    by_gate: dict[str, int] = {}
    rows = (await db.execute(select(sub.c.gate, func.count()).group_by(sub.c.gate))).all()
    for row in rows:
        by_gate[row[0]] = row[1]

    # Incident breakdown
    inc_base = select(AgentIncident).where(AgentIncident.agent_id == agent_id)
    inc_sub = inc_base.subquery()
    inc_rows = (await db.execute(select(inc_sub.c.status, func.count()).group_by(inc_sub.c.status))).all()
    inc_counts = {r[0]: r[1] for r in inc_rows}

    return TraceStatsResponse(
        total_evaluations=total,
        by_decision=by_decision,
        by_category=by_category,
        by_gate=by_gate,
        avg_latency_ms=round(float(avg_lat), 2),
        incidents=IncidentStatsBreakdown(
            open=inc_counts.get("open", 0),
            acknowledged=inc_counts.get("acknowledged", 0),
            resolved=inc_counts.get("resolved", 0),
            false_positive=inc_counts.get("false_positive", 0),
        ),
    )


# ═══════════════════════════════════════════════════════════════════════
# 32d — Incidents
# ═══════════════════════════════════════════════════════════════════════


@router.get("/incidents", response_model=IncidentListResponse)
async def list_incidents(
    agent_id: uuid.UUID,
    status: IncidentStatus | None = None,
    severity: IncidentSeverity | None = None,
    category: IncidentCategory | None = None,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> IncidentListResponse:
    """List incidents for an agent with optional filters."""
    await _get_agent_or_404(agent_id, db)

    stmt = select(AgentIncident).where(AgentIncident.agent_id == agent_id)

    if status is not None:
        stmt = stmt.where(AgentIncident.status == status)
    if severity is not None:
        stmt = stmt.where(AgentIncident.severity == severity)
    if category is not None:
        stmt = stmt.where(AgentIncident.category == category)

    stmt = stmt.order_by(AgentIncident.last_seen.desc())
    result = await db.execute(stmt)
    incidents = result.scalars().all()

    total_stmt = select(func.count()).select_from(
        select(AgentIncident).where(AgentIncident.agent_id == agent_id).subquery()
    )
    if status is not None or severity is not None or category is not None:
        total = len(incidents)
    else:
        total = (await db.execute(total_stmt)).scalar_one()

    return IncidentListResponse(
        items=[_incident_to_read(i) for i in incidents],
        total=total,
    )


@router.patch("/incidents/{incident_id}", response_model=IncidentRead)
async def update_incident(
    agent_id: uuid.UUID,
    incident_id: uuid.UUID,
    body: IncidentUpdate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> IncidentRead:
    """Update incident status."""
    await _get_agent_or_404(agent_id, db)

    incident = await db.get(AgentIncident, incident_id)
    if incident is None or incident.agent_id != agent_id:
        raise HTTPException(status_code=404, detail="Incident not found")

    incident.status = body.status
    db.add(incident)
    await db.commit()
    await db.refresh(incident)

    return _incident_to_read(incident)


# ── Converters ───────────────────────────────────────────────────────


def _trace_to_read(trace: AgentTrace) -> TraceRead:
    return TraceRead(
        id=trace.id,
        agent_id=trace.agent_id,
        session_id=trace.session_id,
        timestamp=trace.timestamp,
        gate=trace.gate,
        tool_name=trace.tool_name,
        role=trace.role,
        decision=trace.decision,
        reason=trace.reason,
        category=trace.category,
        rollout_mode=trace.rollout_mode,
        enforced=trace.enforced,
        latency_ms=trace.latency_ms,
        details=trace.details,
        incident_id=trace.incident_id,
    )


def _incident_to_read(incident: AgentIncident) -> IncidentRead:
    return IncidentRead(
        id=incident.id,
        agent_id=incident.agent_id,
        severity=incident.severity,
        category=incident.category,
        title=incident.title,
        status=incident.status,
        first_seen=incident.first_seen,
        last_seen=incident.last_seen,
        trace_count=incident.trace_count,
        details=incident.details,
    )
