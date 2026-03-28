"""Red Team API — service layer bridging routes ↔ engine/repositories.

All business logic resides in the engine / repository layers.
This service is a thin adapter that:
- Wires repository instances to DB sessions
- Orchestrates create + background-execute
- Maps DB models → response schemas
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.red_team.engine.run_engine import (
    ConcurrencyConflictError,
    compute_target_fingerprint,
)
from src.red_team.packs import PackInfo, list_packs
from src.red_team.persistence.models import BenchmarkRun, BenchmarkScenarioResult
from src.red_team.persistence.repository import (
    BenchmarkRunRepository,
    BenchmarkScenarioResultRepository,
)


def strip_auth_from_config(config: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of *config* with auth_secret_ref masked."""
    if not config:
        return config
    out = dict(config)
    if "auth_secret_ref" in out:
        out["auth_secret_ref"] = "***"
    return out


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class BenchmarkService:
    """Thin service bridging API routes to engine + repositories."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._run_repo = BenchmarkRunRepository(session)
        self._result_repo = BenchmarkScenarioResultRepository(session)

    # -- Create run -----------------------------------------------------

    async def create_run(
        self,
        target_type: str,
        target_config: dict[str, Any],
        pack: str,
        policy: str | None = None,
        source_run_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> BenchmarkRun:
        """Create a new benchmark run record (DB-level).

        Checks concurrency guard (409 if same target already running).
        If ``target_config`` contains ``auth_header`` it is encrypted
        and stored as ``auth_secret_ref``; the plaintext is removed.
        Returns the ORM record; background execution is handled by the caller.
        """
        # Encrypt auth header before storing
        config = dict(target_config)  # shallow copy
        # Encrypt sensitive headers before persisting
        custom_headers = config.pop("custom_headers", None)
        auth_header = config.pop("auth_header", None)
        headers_to_encrypt: dict[str, str] = {}
        if custom_headers and isinstance(custom_headers, dict):
            headers_to_encrypt.update(custom_headers)
        elif auth_header:
            # Legacy single auth_header — convert to custom_headers format
            headers_to_encrypt["Authorization"] = auth_header
        if headers_to_encrypt:
            import json as _json

            from src.red_team.secrets.store import EncryptedColumnSecretStore

            store = EncryptedColumnSecretStore()
            config["auth_secret_ref"] = await store.store(
                "auth", _json.dumps(headers_to_encrypt), ttl_hours=24
            )

        fingerprint = compute_target_fingerprint(target_type, config)

        # Concurrency guard
        active = await self._run_repo.find_running_for_target(fingerprint)
        if active:
            raise ConcurrencyConflictError(f"Benchmark already running for target {fingerprint}")

        # Resolve pack metadata for counting
        from src.red_team.packs import TargetConfig as PackTargetConfig
        from src.red_team.packs import filter_pack, load_pack

        agent_type = config.get("agent_type", "chatbot_api")
        safe_mode = config.get("safe_mode", False)
        pack_obj = load_pack(pack)
        target_cfg = PackTargetConfig(agent_type=agent_type, safe_mode=safe_mode)
        filtered = filter_pack(pack_obj, target_cfg)

        run = BenchmarkRun(
            target_type=target_type,
            target_config=config,
            target_fingerprint=fingerprint,
            pack=pack,
            pack_version=filtered.pack_version,
            policy=policy,
            status="created",
            total_in_pack=filtered.total_in_pack,
            total_applicable=filtered.total_applicable,
            skipped=filtered.skipped_count,
            skipped_reasons=filtered.skipped_reasons,
            source_run_id=uuid.UUID(source_run_id) if source_run_id else None,
            idempotency_key=uuid.UUID(idempotency_key) if idempotency_key else None,
        )
        await self._run_repo.create(run)
        await self._session.commit()
        return run

    # -- Get / list / delete -------------------------------------------

    async def get_run(self, run_id: uuid.UUID) -> BenchmarkRun | None:
        return await self._run_repo.get(run_id)

    async def get_run_safe(self, run_id: uuid.UUID) -> BenchmarkRun | None:
        """Get run with auth_secret_ref masked (for API responses)."""
        run = await self._run_repo.get(run_id)
        if run and run.target_config:
            run.target_config = strip_auth_from_config(run.target_config)
        return run

    async def decrypt_auth_for_run(self, run: BenchmarkRun) -> str | None:
        """Decrypt auth_secret_ref from target_config for in-memory use only."""
        ref = (run.target_config or {}).get("auth_secret_ref")
        if not ref:
            return None
        from src.red_team.secrets.store import EncryptedColumnSecretStore

        store = EncryptedColumnSecretStore()
        return await store.retrieve(ref)

    async def list_runs(
        self,
        limit: int = 50,
        offset: int = 0,
        target_type: str | None = None,
    ) -> list[BenchmarkRun]:
        return await self._run_repo.list_runs(limit=limit, offset=offset, target_type=target_type)

    async def delete_run(self, run_id: uuid.UUID) -> bool:
        """Delete or cancel a run. Returns True if found."""
        run = await self._run_repo.get(run_id)
        if not run:
            return False
        if run.status in ("created", "running"):
            await self._run_repo.update_status(run_id, "cancelled")
        else:
            await self._run_repo.delete(run_id)
        await self._session.commit()
        return True

    # -- Scenario results -----------------------------------------------

    async def list_scenarios(
        self,
        run_id: uuid.UUID,
        limit: int = 100,
        offset: int = 0,
        passed: bool | None = None,
        category: str | None = None,
    ) -> list[BenchmarkScenarioResult]:
        results = await self._result_repo.list_by_run(run_id, limit=limit, offset=offset)
        if passed is not None:
            results = [r for r in results if r.passed == passed]
        if category is not None:
            results = [r for r in results if r.category == category]
        return results

    async def get_scenario(self, run_id: uuid.UUID, scenario_id: str) -> BenchmarkScenarioResult | None:
        return await self._result_repo.get_by_scenario(run_id, scenario_id)

    # -- Packs ----------------------------------------------------------

    @staticmethod
    def list_packs() -> list[PackInfo]:
        return list_packs()

    # -- Compare --------------------------------------------------------

    async def compare_runs(self, run_a_id: uuid.UUID, run_b_id: uuid.UUID) -> dict[str, Any]:
        run_a = await self._run_repo.get(run_a_id)
        run_b = await self._run_repo.get(run_b_id)
        if not run_a or not run_b:
            return {"error": "One or both runs not found"}

        warning = None
        if run_a.pack != run_b.pack:
            warning = "Runs use different packs — comparison may not be meaningful"
        if run_a.target_fingerprint != run_b.target_fingerprint:
            warning = (warning + "; " if warning else "") + "Runs target different endpoints"

        # Compute fixed / new failures
        results_a = await self._result_repo.list_by_run(run_a_id)
        results_b = await self._result_repo.list_by_run(run_b_id)

        failed_a = {r.scenario_id for r in results_a if r.passed is False}
        failed_b = {r.scenario_id for r in results_b if r.passed is False}

        fixed = sorted(failed_a - failed_b)
        new_failures = sorted(failed_b - failed_a)

        return {
            "run_a": run_a,
            "run_b": run_b,
            "score_delta": (run_b.score_simple or 0) - (run_a.score_simple or 0),
            "weighted_delta": (run_b.score_weighted or 0) - (run_a.score_weighted or 0),
            "warning": warning,
            "fixed_failures": fixed,
            "new_failures": new_failures,
        }


# ---------------------------------------------------------------------------
# Standalone helpers (no BenchmarkService instance needed)
# ---------------------------------------------------------------------------


async def cleanup_expired_secrets(session: AsyncSession) -> int:
    """Null out ``auth_secret_ref`` from target_config 24 h after completion.

    Scans completed runs whose ``completed_at + 24h < now()`` and whose
    ``target_config`` still contains an ``auth_secret_ref``.

    Returns the number of runs cleaned.
    """
    cutoff = datetime.now(UTC) - timedelta(hours=24)
    stmt = (
        select(BenchmarkRun)
        .where(BenchmarkRun.completed_at.isnot(None))
        .where(BenchmarkRun.completed_at < cutoff)
        .where(BenchmarkRun.status.in_(["completed", "failed", "cancelled"]))
    )
    result = await session.execute(stmt)
    runs = list(result.scalars().all())

    cleaned = 0
    for run in runs:
        cfg = run.target_config or {}
        if "auth_secret_ref" in cfg:
            cfg = dict(cfg)
            del cfg["auth_secret_ref"]
            run.target_config = cfg
            cleaned += 1

    if cleaned:
        await session.commit()
    return cleaned
