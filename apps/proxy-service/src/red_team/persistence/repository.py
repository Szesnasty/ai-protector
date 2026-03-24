"""Repository layer for Red Team benchmark persistence.

Thin CRUD + queries — no business logic.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.red_team.persistence.models import BenchmarkRun, BenchmarkScenarioResult

# ---------------------------------------------------------------------------
# Count result
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RunCounts:
    """Aggregated counts for a run's scenario results."""

    passed: int
    failed: int
    skipped: int
    total: int


# ---------------------------------------------------------------------------
# BenchmarkRun repository
# ---------------------------------------------------------------------------


class BenchmarkRunRepository:
    """Data access layer for BenchmarkRun."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, run: BenchmarkRun) -> BenchmarkRun:
        self._session.add(run)
        await self._session.flush()
        return run

    async def get(self, run_id: uuid.UUID) -> BenchmarkRun | None:
        return await self._session.get(BenchmarkRun, run_id)

    async def list_runs(
        self,
        limit: int = 50,
        offset: int = 0,
        target_type: str | None = None,
    ) -> list[BenchmarkRun]:
        stmt = select(BenchmarkRun).order_by(BenchmarkRun.created_at.desc())
        if target_type:
            stmt = stmt.where(BenchmarkRun.target_type == target_type)
        stmt = stmt.limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update_status(
        self,
        run_id: uuid.UUID,
        status: str,
        scores: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        run = await self._session.get(BenchmarkRun, run_id)
        if run is None:
            return
        run.status = status
        if scores:
            for key, val in scores.items():
                setattr(run, key, val)
        for key, val in kwargs.items():
            setattr(run, key, val)

    async def find_running_for_target(self, target_fingerprint: str) -> BenchmarkRun | None:
        stmt = (
            select(BenchmarkRun)
            .where(BenchmarkRun.target_fingerprint == target_fingerprint)
            .where(BenchmarkRun.status.in_(["created", "running"]))
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_idempotency_key(self, key: uuid.UUID) -> BenchmarkRun | None:
        stmt = select(BenchmarkRun).where(BenchmarkRun.idempotency_key == key).limit(1)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def cancel_stale_runs(self) -> int:
        """Mark all 'created' / 'running' runs as 'cancelled'.

        Called at startup to clean up runs orphaned by a previous crash
        or container restart.  Returns the number of affected rows.
        """
        now = datetime.now(UTC)
        stmt = (
            update(BenchmarkRun)
            .where(BenchmarkRun.status.in_(["created", "running"]))
            .values(status="cancelled", completed_at=now, error="Cancelled: stale after restart")
        )
        result = await self._session.execute(stmt)
        return result.rowcount  # type: ignore[return-value]

    async def delete(self, run_id: uuid.UUID) -> None:
        run = await self.get(run_id)
        if run:
            await self._session.delete(run)


# ---------------------------------------------------------------------------
# BenchmarkScenarioResult repository
# ---------------------------------------------------------------------------


class BenchmarkScenarioResultRepository:
    """Data access layer for BenchmarkScenarioResult."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, result: BenchmarkScenarioResult) -> None:
        self._session.add(result)
        await self._session.flush()

    async def create_batch(self, results: list[BenchmarkScenarioResult]) -> None:
        self._session.add_all(results)
        await self._session.flush()

    async def list_by_run(
        self,
        run_id: uuid.UUID,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[BenchmarkScenarioResult]:
        stmt = (
            select(BenchmarkScenarioResult)
            .where(BenchmarkScenarioResult.run_id == run_id)
            .order_by(BenchmarkScenarioResult.created_at)
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_scenario(
        self,
        run_id: uuid.UUID,
        scenario_id: str,
    ) -> BenchmarkScenarioResult | None:
        stmt = (
            select(BenchmarkScenarioResult)
            .where(BenchmarkScenarioResult.run_id == run_id)
            .where(BenchmarkScenarioResult.scenario_id == scenario_id)
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def count_by_run(self, run_id: uuid.UUID) -> RunCounts:
        base = select(func.count()).where(BenchmarkScenarioResult.run_id == run_id)

        total_q = await self._session.execute(base.select_from(BenchmarkScenarioResult))
        passed_q = await self._session.execute(
            base.select_from(BenchmarkScenarioResult).where(BenchmarkScenarioResult.passed.is_(True))
        )
        failed_q = await self._session.execute(
            base.select_from(BenchmarkScenarioResult).where(BenchmarkScenarioResult.passed.is_(False))
        )
        skipped_q = await self._session.execute(
            base.select_from(BenchmarkScenarioResult).where(BenchmarkScenarioResult.skipped.is_(True))
        )

        return RunCounts(
            passed=passed_q.scalar_one(),
            failed=failed_q.scalar_one(),
            skipped=skipped_q.scalar_one(),
            total=total_q.scalar_one(),
        )


# ---------------------------------------------------------------------------
# Retention cleanup
# ---------------------------------------------------------------------------


async def purge_expired_responses(session: AsyncSession) -> int:
    """Null out raw response data where retained_until < now().

    Returns the number of rows affected.
    """
    now = datetime.now(UTC)
    stmt = (
        update(BenchmarkScenarioResult)
        .where(BenchmarkScenarioResult.raw_response_retained_until.isnot(None))
        .where(BenchmarkScenarioResult.raw_response_retained_until < now)
        .where(BenchmarkScenarioResult.pipeline_result.isnot(None))
        .values(pipeline_result=None)
    )
    result = await session.execute(stmt)
    return result.rowcount
