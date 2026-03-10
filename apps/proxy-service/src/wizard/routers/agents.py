"""CRUD router for agent registration (Agent Wizard — spec 26)."""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.wizard.models import Agent, AgentStatus, RiskLevel
from src.wizard.schemas import AgentCreate, AgentListResponse, AgentRead, AgentUpdate
from src.wizard.services.risk import apply_risk_classification

logger = structlog.get_logger()

router = APIRouter(prefix="/agents", tags=["agents"])

# ── Capability fields that trigger risk re-computation ───────────────────
_RISK_FIELDS = frozenset(
    {
        "is_public_facing",
        "has_tools",
        "has_write_actions",
        "touches_pii",
        "handles_secrets",
        "calls_external_apis",
    }
)


@router.post("", response_model=AgentRead, status_code=201)
async def create_agent(
    body: AgentCreate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> AgentRead:
    """Register a new agent."""
    # Check name uniqueness
    existing = await db.execute(select(Agent).where(Agent.name == body.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Agent '{body.name}' already exists")

    agent = Agent(**body.model_dump())
    apply_risk_classification(agent)

    db.add(agent)
    await db.commit()
    await db.refresh(agent)

    logger.info("agent_created", agent_id=str(agent.id), name=agent.name, risk=agent.risk_level)
    return agent


@router.get("", response_model=AgentListResponse)
async def list_agents(
    page: int = Query(1, ge=1),  # noqa: B008
    per_page: int = Query(20, ge=1, le=100),  # noqa: B008
    status: AgentStatus | None = None,
    risk_level: RiskLevel | None = None,
    team: str | None = None,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> AgentListResponse:
    """List agents with pagination and filtering."""
    stmt = select(Agent)

    # Filters
    if status is not None:
        stmt = stmt.where(Agent.status == status)
    else:
        # Default: exclude archived
        stmt = stmt.where(Agent.status != AgentStatus.ARCHIVED)
    if risk_level is not None:
        stmt = stmt.where(Agent.risk_level == risk_level)
    if team is not None:
        stmt = stmt.where(Agent.team == team)

    # Count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    # Order: reference agents first, then by name
    stmt = stmt.order_by(Agent.is_reference.desc(), Agent.name)

    # Paginate
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(stmt)
    agents = result.scalars().all()

    return AgentListResponse(items=agents, total=total, page=page, per_page=per_page)


@router.get("/{agent_id}", response_model=AgentRead)
async def get_agent(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> AgentRead:
    """Get a single agent by ID."""
    agent = await db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.patch("/{agent_id}", response_model=AgentRead)
async def update_agent(
    agent_id: uuid.UUID,
    body: AgentUpdate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> AgentRead:
    """Update an agent. Re-computes risk if capability fields change."""
    agent = await db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Check name uniqueness if name is being changed
    update_data = body.model_dump(exclude_unset=True)
    if "name" in update_data and update_data["name"] != agent.name:
        existing = await db.execute(select(Agent).where(Agent.name == update_data["name"]))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail=f"Agent '{update_data['name']}' already exists")

    # Apply updates
    risk_changed = False
    for field, value in update_data.items():
        setattr(agent, field, value)
        if field in _RISK_FIELDS:
            risk_changed = True

    # Re-classify if capability flags changed
    if risk_changed:
        apply_risk_classification(agent)

    await db.commit()
    await db.refresh(agent)

    logger.info("agent_updated", agent_id=str(agent.id), risk_changed=risk_changed)
    return agent


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> None:
    """Soft-delete an agent (set status=archived)."""
    agent = await db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    if agent.is_reference:
        raise HTTPException(status_code=403, detail="Cannot delete reference agent")

    agent.status = AgentStatus.ARCHIVED
    await db.commit()

    logger.info("agent_archived", agent_id=str(agent.id), name=agent.name)
