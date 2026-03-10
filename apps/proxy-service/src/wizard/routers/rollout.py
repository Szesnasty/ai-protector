"""Rollout modes router (Agent Wizard — spec 31).

Endpoints:
  PATCH  /agents/:id/rollout           — promote / demote rollout mode
  GET    /agents/:id/rollout/readiness  — promotion readiness check
  GET    /agents/:id/rollout/events     — promotion event history
  POST   /agents/:id/gate/evaluate      — evaluate a gate in current mode
  GET    /agents/:id/traces             — list gate decision traces
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.wizard.models import (
    Agent,
    GateAction,
    GateDecision,
    PromotionEvent,
    RolloutMode,
    ValidationRun,
)
from src.wizard.schemas import (
    GateDecisionRead,
    GateEvalRequest,
    GateEvalResponse,
    PromotionEventRead,
    ReadinessResponse,
    ReadinessStats,
    RolloutPromoteRequest,
    RolloutPromoteResponse,
)
from src.wizard.services.gate import evaluate_gate

logger = structlog.get_logger()

router = APIRouter(prefix="/agents/{agent_id}", tags=["rollout"])


# ── Helpers ──────────────────────────────────────────────────────────


async def _get_agent_or_404(agent_id: uuid.UUID, db: AsyncSession) -> Agent:
    agent = await db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


# ── Transition rules ────────────────────────────────────────────────

# Allowed transitions: (from, to) → True
_ALLOWED_TRANSITIONS: set[tuple[RolloutMode, RolloutMode]] = {
    # Upgrades
    (RolloutMode.OBSERVE, RolloutMode.WARN),
    (RolloutMode.WARN, RolloutMode.ENFORCE),
    # Downgrades — always allowed
    (RolloutMode.ENFORCE, RolloutMode.WARN),
    (RolloutMode.ENFORCE, RolloutMode.OBSERVE),
    (RolloutMode.WARN, RolloutMode.OBSERVE),
}


# ═══════════════════════════════════════════════════════════════════════
# 31c — Promotion API
# ═══════════════════════════════════════════════════════════════════════


@router.patch("/rollout", status_code=200, response_model=RolloutPromoteResponse)
async def promote_rollout(
    agent_id: uuid.UUID,
    body: RolloutPromoteRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> RolloutPromoteResponse:
    """Promote or demote the rollout mode for an agent."""
    agent = await _get_agent_or_404(agent_id, db)
    current = agent.rollout_mode
    requested = body.mode

    # No-op: same mode
    if current == requested:
        return RolloutPromoteResponse(
            id=agent.id,
            name=agent.name,
            rollout_mode=current,
            previous_mode=current,
        )

    # Validate transition
    if (current, requested) not in _ALLOWED_TRANSITIONS:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "promotion_blocked",
                "reason": (
                    f"Cannot promote directly from {current.value} to {requested.value}. Promote to warn first."
                    if current == RolloutMode.OBSERVE and requested == RolloutMode.ENFORCE
                    else f"Invalid transition from {current.value} to {requested.value}."
                ),
                "current_mode": current.value,
                "requested_mode": requested.value,
            },
        )

    # Promotion guard: observe→warn requires any validation run
    if current == RolloutMode.OBSERVE and requested == RolloutMode.WARN:
        latest = await _get_latest_validation(agent_id, db)
        if latest is None:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "promotion_blocked",
                    "reason": "No validation run found. Run validation before promoting to warn.",
                    "current_mode": current.value,
                    "requested_mode": requested.value,
                },
            )

    # Promotion guard: warn→enforce requires 100% validation
    if current == RolloutMode.WARN and requested == RolloutMode.ENFORCE:
        latest = await _get_latest_validation(agent_id, db)
        if latest is None:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "promotion_blocked",
                    "reason": "No validation run found. Run validation before promoting to enforce.",
                    "current_mode": current.value,
                    "requested_mode": requested.value,
                },
            )
        if latest.passed != latest.total:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "promotion_blocked",
                    "reason": (
                        f"Latest validation score is {latest.passed}/{latest.total}. "
                        "All tests must pass to promote to enforce."
                    ),
                    "current_mode": current.value,
                    "requested_mode": requested.value,
                    "latest_score": {"passed": latest.passed, "total": latest.total},
                },
            )

    # Apply transition
    previous = agent.rollout_mode
    agent.rollout_mode = requested
    db.add(agent)

    # Record event
    event = PromotionEvent(
        agent_id=agent_id,
        from_mode=previous,
        to_mode=requested,
        user="system",  # placeholder until auth is wired
    )
    db.add(event)

    await db.commit()
    await db.refresh(agent)

    logger.info(
        "rollout_mode_changed",
        agent_id=str(agent_id),
        from_mode=previous.value,
        to_mode=requested.value,
    )

    return RolloutPromoteResponse(
        id=agent.id,
        name=agent.name,
        rollout_mode=agent.rollout_mode,
        previous_mode=previous,
    )


# ═══════════════════════════════════════════════════════════════════════
# 31e — Readiness check
# ═══════════════════════════════════════════════════════════════════════


@router.get("/rollout/readiness", response_model=ReadinessResponse)
async def rollout_readiness(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> ReadinessResponse:
    """Check if the agent is ready to be promoted."""
    agent = await _get_agent_or_404(agent_id, db)
    current = agent.rollout_mode

    can_promote_to: list[RolloutMode] = []
    blockers: list[str] = []

    latest = await _get_latest_validation(agent_id, db)

    if current == RolloutMode.OBSERVE:
        if latest is not None:
            can_promote_to.append(RolloutMode.WARN)
        else:
            blockers.append("No validation run found")

    elif current == RolloutMode.WARN:
        if latest is not None and latest.passed == latest.total:
            can_promote_to.append(RolloutMode.ENFORCE)
        elif latest is not None:
            blockers.append(f"Validation score {latest.passed}/{latest.total}")
        else:
            blockers.append("No validation run found")

    # elif ENFORCE: already at highest — nothing to promote to

    # Trace stats
    traces_count = await _count_traces(agent_id, current, db)
    would_blocked = await _count_would_blocked(agent_id, current, db)

    latest_val_dict = None
    if latest is not None:
        latest_val_dict = {
            "passed": latest.passed,
            "total": latest.total,
            "run_at": latest.created_at.isoformat() if latest.created_at else "",
        }

    return ReadinessResponse(
        current_mode=current,
        can_promote_to=can_promote_to,
        blockers=blockers,
        stats=ReadinessStats(
            traces_in_current_mode=traces_count,
            would_have_blocked=would_blocked,
            latest_validation=latest_val_dict,
        ),
    )


# ═══════════════════════════════════════════════════════════════════════
# 31c — Promotion event history
# ═══════════════════════════════════════════════════════════════════════


@router.get("/rollout/events", response_model=list[PromotionEventRead])
async def list_promotion_events(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> list[PromotionEventRead]:
    """Return promotion event history (most recent first)."""
    await _get_agent_or_404(agent_id, db)

    result = await db.execute(
        select(PromotionEvent).where(PromotionEvent.agent_id == agent_id).order_by(PromotionEvent.created_at.desc())
    )
    events = result.scalars().all()
    return [
        PromotionEventRead(
            id=e.id,
            agent_id=e.agent_id,
            from_mode=e.from_mode,
            to_mode=e.to_mode,
            user=e.user,
            created_at=e.created_at,
        )
        for e in events
    ]


# ═══════════════════════════════════════════════════════════════════════
# 31b — Gate evaluation
# ═══════════════════════════════════════════════════════════════════════


@router.post("/gate/evaluate", status_code=200, response_model=GateEvalResponse)
async def evaluate_gate_endpoint(
    agent_id: uuid.UUID,
    body: GateEvalRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> GateEvalResponse:
    """Evaluate a gate check in the agent's current rollout mode."""
    agent = await _get_agent_or_404(agent_id, db)

    # Simulate a deny decision for the gate type
    from src.wizard.services.gate import _GATE_DENY_ACTIONS

    raw_decision = _GATE_DENY_ACTIONS.get(body.gate_type, GateAction.DENY)

    trace = evaluate_gate(
        gate_type=body.gate_type,
        raw_decision=raw_decision,
        rollout_mode=agent.rollout_mode,
        agent_id=agent_id,
        context=body.context,
    )

    db.add(trace)
    await db.commit()
    await db.refresh(trace)

    return GateEvalResponse(
        decision=trace.decision,
        effective_action=trace.effective_action,
        rollout_mode=trace.rollout_mode,
        enforced=trace.enforced,
        warning=trace.warning,
    )


# ═══════════════════════════════════════════════════════════════════════
# 31d — Traces query
# ═══════════════════════════════════════════════════════════════════════


@router.get("/traces", response_model=list[GateDecisionRead])
async def list_traces(
    agent_id: uuid.UUID,
    rollout_mode: RolloutMode | None = None,
    enforced: bool | None = None,
    decision: GateAction | None = None,
    limit: int = Query(100, ge=1, le=1000),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> list[GateDecisionRead]:
    """Query gate decision traces with optional filters."""
    await _get_agent_or_404(agent_id, db)

    stmt = select(GateDecision).where(GateDecision.agent_id == agent_id)

    if rollout_mode is not None:
        stmt = stmt.where(GateDecision.rollout_mode == rollout_mode)
    if enforced is not None:
        stmt = stmt.where(GateDecision.enforced == enforced)
    if decision is not None:
        stmt = stmt.where(GateDecision.decision == decision)

    stmt = stmt.order_by(GateDecision.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    traces = result.scalars().all()

    return [
        GateDecisionRead(
            id=t.id,
            agent_id=t.agent_id,
            gate_type=t.gate_type,
            decision=t.decision,
            effective_action=t.effective_action,
            rollout_mode=t.rollout_mode,
            enforced=t.enforced,
            warning=t.warning,
            context=t.context,
            created_at=t.created_at,
        )
        for t in traces
    ]


# ── Private helpers ──────────────────────────────────────────────────


async def _get_latest_validation(agent_id: uuid.UUID, db: AsyncSession) -> ValidationRun | None:
    result = await db.execute(
        select(ValidationRun)
        .where(ValidationRun.agent_id == agent_id)
        .order_by(ValidationRun.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _count_traces(agent_id: uuid.UUID, mode: RolloutMode, db: AsyncSession) -> int:
    result = await db.execute(
        select(func.count()).where(
            and_(
                GateDecision.agent_id == agent_id,
                GateDecision.rollout_mode == mode,
            )
        )
    )
    return result.scalar_one()


async def _count_would_blocked(agent_id: uuid.UUID, mode: RolloutMode, db: AsyncSession) -> int:
    """Count traces where decision is DENY/BLOCK/REDACT but not enforced."""
    result = await db.execute(
        select(func.count()).where(
            and_(
                GateDecision.agent_id == agent_id,
                GateDecision.rollout_mode == mode,
                GateDecision.enforced == False,  # noqa: E712
                GateDecision.decision.in_(
                    [
                        GateAction.DENY,
                        GateAction.BLOCK,
                        GateAction.REDACT,
                    ]
                ),
            )
        )
    )
    return result.scalar_one()
