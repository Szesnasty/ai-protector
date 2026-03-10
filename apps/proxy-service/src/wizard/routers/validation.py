"""Validation router (Agent Wizard — spec 30c)."""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.wizard.models import Agent, ValidationRun
from src.wizard.services.validation_runner import run_validation

logger = structlog.get_logger()

router = APIRouter(prefix="/agents/{agent_id}", tags=["validation"])


# ── Request / Response schemas ───────────────────────────────────────


class ValidateRequest(BaseModel):
    """Request body for POST /agents/:id/validate."""

    pack: str = Field(default="basic", description="Test pack name")


class TestResultSchema(BaseModel):
    """Per-test result in validation response."""

    name: str
    category: str
    expected: str
    actual: str
    passed: bool
    duration_ms: float
    recommendation: str | None = None
    version: str = "1.0.0"


class CategoryBreakdownSchema(BaseModel):
    passed: int
    total: int


class ValidationResponse(BaseModel):
    """Full validation run response."""

    agent_id: str
    pack: str
    pack_version: str
    score: int
    total: int
    passed: int
    failed: int
    categories: dict[str, CategoryBreakdownSchema]
    tests: list[TestResultSchema]
    run_at: str
    duration_ms: float


class ValidationRunRead(BaseModel):
    """Read view of a stored validation run."""

    id: uuid.UUID
    agent_id: uuid.UUID
    pack: str
    pack_version: str
    score: int
    total: int
    passed: int
    failed: int
    duration_ms: float
    results: dict
    created_at: str


# ── Helpers ──────────────────────────────────────────────────────────


async def _get_agent_or_404(agent_id: uuid.UUID, db: AsyncSession) -> Agent:
    agent = await db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


# ── Endpoints ────────────────────────────────────────────────────────


@router.post("/validate", status_code=200, response_model=ValidationResponse)
async def validate_agent(
    agent_id: uuid.UUID,
    body: ValidateRequest | None = None,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> ValidationResponse:
    """Run validation suite against an agent's generated config."""
    await _get_agent_or_404(agent_id, db)

    pack_name = body.pack if body else "basic"

    try:
        result = await run_validation(agent_id, db, pack=pack_name)
    except ValueError as exc:
        msg = str(exc)
        if "Unknown test pack" in msg:
            raise HTTPException(status_code=422, detail=msg) from None
        if "not found" in msg:
            raise HTTPException(status_code=404, detail=msg) from None
        raise HTTPException(status_code=400, detail=msg) from None

    # Store run in DB
    run = ValidationRun(
        agent_id=agent_id,
        pack=result.pack,
        pack_version=result.pack_version,
        score=result.score,
        total=result.total,
        passed=result.passed,
        failed=result.failed,
        duration_ms=result.duration_ms,
        results={
            "categories": result.categories,
            "tests": result.tests,
            "run_at": result.run_at,
        },
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    logger.info(
        "validation_run_completed",
        agent_id=str(agent_id),
        pack=pack_name,
        score=result.score,
        total=result.total,
    )

    return ValidationResponse(
        agent_id=result.agent_id,
        pack=result.pack,
        pack_version=result.pack_version,
        score=result.score,
        total=result.total,
        passed=result.passed,
        failed=result.failed,
        categories={
            k: CategoryBreakdownSchema(passed=v["passed"], total=v["total"]) for k, v in result.categories.items()
        },
        tests=[TestResultSchema(**t) for t in result.tests],
        run_at=result.run_at,
        duration_ms=result.duration_ms,
    )


@router.get("/validations")
async def list_validations(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> list[ValidationRunRead]:
    """Return history of validation runs for an agent (most recent first)."""
    await _get_agent_or_404(agent_id, db)

    result = await db.execute(
        select(ValidationRun).where(ValidationRun.agent_id == agent_id).order_by(ValidationRun.created_at.desc())
    )
    runs = result.scalars().all()

    return [
        ValidationRunRead(
            id=run.id,
            agent_id=run.agent_id,
            pack=run.pack,
            pack_version=run.pack_version,
            score=run.score,
            total=run.total,
            passed=run.passed,
            failed=run.failed,
            duration_ms=run.duration_ms,
            results=run.results,
            created_at=run.created_at.isoformat() if run.created_at else "",
        )
        for run in runs
    ]
