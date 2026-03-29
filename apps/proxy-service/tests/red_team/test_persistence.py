"""Tests for red_team.persistence — DB models and repository layer.

Uses async SQLite for testing (no PostgreSQL required).
Engine + session fixtures are provided by tests/red_team/conftest.py.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from src.red_team.persistence import (
    BenchmarkRun,
    BenchmarkRunRepository,
    BenchmarkScenarioResult,
    BenchmarkScenarioResultRepository,
    RunCounts,
    purge_expired_responses,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run(**overrides) -> BenchmarkRun:
    defaults = {
        "id": uuid.uuid4(),
        "target_type": "demo",
        "target_config": {"url": "http://localhost:8000"},
        "target_fingerprint": "abc123def456",
        "pack": "core_security",
        "pack_version": "1.0.0",
        "status": "created",
        "total_in_pack": 12,
        "total_applicable": 10,
        "executed": 0,
        "passed": 0,
        "failed": 0,
        "skipped": 2,
        "skipped_reasons": {"not_applicable": 2},
        "false_positives": 0,
    }
    defaults.update(overrides)
    return BenchmarkRun(**defaults)


def _make_result(run_id: uuid.UUID, **overrides) -> BenchmarkScenarioResult:
    defaults = {
        "id": uuid.uuid4(),
        "run_id": run_id,
        "scenario_id": "CS-001",
        "category": "prompt_injection_jailbreak",
        "severity": "critical",
        "mutating": False,
        "applicable_to": ["chatbot_api"],
        "prompt": "Test prompt",
        "expected": "BLOCK",
        "passed": True,
        "skipped": False,
        "detector_type": "keyword",
        "latency_ms": 150,
    }
    defaults.update(overrides)
    return BenchmarkScenarioResult(**defaults)


# ===========================================================================
# BenchmarkRun tests
# ===========================================================================


class TestBenchmarkRunRepository:
    async def test_create_run(self, session: AsyncSession) -> None:
        repo = BenchmarkRunRepository(session)
        run = _make_run()
        created = await repo.create(run)

        assert created.id == run.id
        assert created.status == "created"
        assert created.target_fingerprint == "abc123def456"

    async def test_get_run(self, session: AsyncSession) -> None:
        repo = BenchmarkRunRepository(session)
        run = _make_run()
        await repo.create(run)

        found = await repo.get(run.id)
        assert found is not None
        assert found.id == run.id
        assert found.pack == "core_security"

    async def test_get_run_not_found(self, session: AsyncSession) -> None:
        repo = BenchmarkRunRepository(session)
        found = await repo.get(uuid.uuid4())
        assert found is None

    async def test_update_status(self, session: AsyncSession) -> None:
        repo = BenchmarkRunRepository(session)
        run = _make_run()
        await repo.create(run)

        await repo.update_status(run.id, "running")
        await session.flush()

        # Re-fetch to verify
        found = await repo.get(run.id)
        assert found is not None
        assert found.status == "running"

    async def test_update_status_with_scores(self, session: AsyncSession) -> None:
        repo = BenchmarkRunRepository(session)
        run = _make_run()
        await repo.create(run)

        await repo.update_status(
            run.id,
            "completed",
            scores={"score_simple": 85, "score_weighted": 78},
        )
        await session.flush()

        found = await repo.get(run.id)
        assert found is not None
        assert found.score_simple == 85
        assert found.score_weighted == 78

    async def test_find_running_for_target(self, session: AsyncSession) -> None:
        repo = BenchmarkRunRepository(session)
        run = _make_run(status="running", target_fingerprint="fp_abc")
        await repo.create(run)

        found = await repo.find_running_for_target("fp_abc")
        assert found is not None
        assert found.id == run.id

    async def test_find_running_for_target_not_found(self, session: AsyncSession) -> None:
        repo = BenchmarkRunRepository(session)
        run = _make_run(status="completed", target_fingerprint="fp_abc")
        await repo.create(run)

        found = await repo.find_running_for_target("fp_abc")
        assert found is None

    async def test_list_runs(self, session: AsyncSession) -> None:
        repo = BenchmarkRunRepository(session)
        for _i in range(3):
            await repo.create(_make_run(id=uuid.uuid4()))

        runs = await repo.list_runs(limit=10)
        assert len(runs) == 3

    async def test_list_runs_by_target_type(self, session: AsyncSession) -> None:
        repo = BenchmarkRunRepository(session)
        await repo.create(_make_run(id=uuid.uuid4(), target_type="demo"))
        await repo.create(_make_run(id=uuid.uuid4(), target_type="local_agent"))

        runs = await repo.list_runs(target_type="demo")
        assert len(runs) == 1
        assert runs[0].target_type == "demo"

    async def test_delete(self, session: AsyncSession) -> None:
        repo = BenchmarkRunRepository(session)
        run = _make_run()
        await repo.create(run)

        await repo.delete(run.id)
        await session.flush()

        found = await repo.get(run.id)
        assert found is None

    async def test_source_run_id_nullable(self, session: AsyncSession) -> None:
        repo = BenchmarkRunRepository(session)
        run = _make_run(source_run_id=None)
        await repo.create(run)

        found = await repo.get(run.id)
        assert found is not None
        assert found.source_run_id is None

    async def test_source_run_id_set_on_rerun(self, session: AsyncSession) -> None:
        repo = BenchmarkRunRepository(session)
        original = _make_run()
        await repo.create(original)

        rerun = _make_run(id=uuid.uuid4(), source_run_id=original.id)
        await repo.create(rerun)

        found = await repo.get(rerun.id)
        assert found is not None
        assert found.source_run_id == original.id

    async def test_skipped_reasons_json(self, session: AsyncSession) -> None:
        repo = BenchmarkRunRepository(session)
        reasons = {"safe_mode": 3, "not_applicable": 2}
        run = _make_run(skipped_reasons=reasons)
        await repo.create(run)

        found = await repo.get(run.id)
        assert found is not None
        assert found.skipped_reasons == reasons

    async def test_counting_invariant_on_read(self, session: AsyncSession) -> None:
        repo = BenchmarkRunRepository(session)
        run = _make_run(total_in_pack=15, total_applicable=12, skipped=3)
        await repo.create(run)

        found = await repo.get(run.id)
        assert found is not None
        assert found.total_in_pack == found.total_applicable + found.skipped

    async def test_target_fingerprint_stored(self, session: AsyncSession) -> None:
        repo = BenchmarkRunRepository(session)
        run = _make_run(target_fingerprint="abcdef1234567890")
        await repo.create(run)

        found = await repo.get(run.id)
        assert found is not None
        assert found.target_fingerprint == "abcdef1234567890"

    async def test_idempotency_key_stored(self, session: AsyncSession) -> None:
        repo = BenchmarkRunRepository(session)
        key = uuid.uuid4()
        run = _make_run(idempotency_key=key)
        await repo.create(run)

        found = await repo.find_by_idempotency_key(key)
        assert found is not None
        assert found.idempotency_key == key


# ===========================================================================
# BenchmarkScenarioResult tests
# ===========================================================================


class TestBenchmarkScenarioResultRepository:
    async def test_create_result(self, session: AsyncSession) -> None:
        run_repo = BenchmarkRunRepository(session)
        run = _make_run()
        await run_repo.create(run)

        repo = BenchmarkScenarioResultRepository(session)
        result = _make_result(run.id)
        await repo.create(result)

        found = await repo.get_by_scenario(run.id, "CS-001")
        assert found is not None
        assert found.passed is True

    async def test_create_batch(self, session: AsyncSession) -> None:
        run_repo = BenchmarkRunRepository(session)
        run = _make_run()
        await run_repo.create(run)

        repo = BenchmarkScenarioResultRepository(session)
        results = [_make_result(run.id, id=uuid.uuid4(), scenario_id=f"CS-{i:03d}") for i in range(1, 4)]
        await repo.create_batch(results)

        listed = await repo.list_by_run(run.id)
        assert len(listed) == 3

    async def test_list_by_run(self, session: AsyncSession) -> None:
        run_repo = BenchmarkRunRepository(session)
        run1 = _make_run()
        run2 = _make_run(id=uuid.uuid4())
        await run_repo.create(run1)
        await run_repo.create(run2)

        repo = BenchmarkScenarioResultRepository(session)
        await repo.create(_make_result(run1.id, id=uuid.uuid4(), scenario_id="CS-001"))
        await repo.create(_make_result(run1.id, id=uuid.uuid4(), scenario_id="CS-002"))
        await repo.create(_make_result(run2.id, id=uuid.uuid4(), scenario_id="CS-003"))

        results = await repo.list_by_run(run1.id)
        assert len(results) == 2
        scenario_ids = {r.scenario_id for r in results}
        assert scenario_ids == {"CS-001", "CS-002"}

    async def test_count_by_run(self, session: AsyncSession) -> None:
        run_repo = BenchmarkRunRepository(session)
        run = _make_run()
        await run_repo.create(run)

        repo = BenchmarkScenarioResultRepository(session)
        await repo.create(_make_result(run.id, id=uuid.uuid4(), scenario_id="CS-001", passed=True, skipped=False))
        await repo.create(_make_result(run.id, id=uuid.uuid4(), scenario_id="CS-002", passed=False, skipped=False))
        await repo.create(
            _make_result(
                run.id, id=uuid.uuid4(), scenario_id="CS-003", passed=None, skipped=True, skipped_reason="timeout"
            )
        )
        await session.flush()

        counts = await repo.count_by_run(run.id)
        assert isinstance(counts, RunCounts)
        assert counts.passed == 1
        assert counts.failed == 1
        assert counts.skipped == 1
        assert counts.total == 3

    async def test_retained_until_set(self, session: AsyncSession) -> None:
        run_repo = BenchmarkRunRepository(session)
        run = _make_run()
        await run_repo.create(run)

        repo = BenchmarkScenarioResultRepository(session)
        retained_until = datetime.now(UTC) + timedelta(days=30)
        result = _make_result(
            run.id,
            raw_response_retained_until=retained_until,
            pipeline_result={"raw": "data"},
        )
        await repo.create(result)

        found = await repo.get_by_scenario(run.id, "CS-001")
        assert found is not None
        assert found.raw_response_retained_until is not None
        assert found.pipeline_result is not None


# ===========================================================================
# Retention cleanup
# ===========================================================================


class TestRetentionCleanup:
    async def test_purge_expired(self, session: AsyncSession) -> None:
        run_repo = BenchmarkRunRepository(session)
        run = _make_run()
        await run_repo.create(run)

        repo = BenchmarkScenarioResultRepository(session)
        # Expired result
        expired = _make_result(
            run.id,
            id=uuid.uuid4(),
            scenario_id="CS-001",
            raw_response_retained_until=datetime.now(UTC) - timedelta(days=1),
            pipeline_result={"raw": "expired_data"},
        )
        # Not expired result
        valid = _make_result(
            run.id,
            id=uuid.uuid4(),
            scenario_id="CS-002",
            raw_response_retained_until=datetime.now(UTC) + timedelta(days=30),
            pipeline_result={"raw": "valid_data"},
        )
        await repo.create(expired)
        await repo.create(valid)
        await session.flush()

        count = await purge_expired_responses(session)
        assert count == 1

        # Verify expired result was purged
        found_expired = await repo.get_by_scenario(run.id, "CS-001")
        assert found_expired is not None
        assert found_expired.pipeline_result is None

        # Verify valid result was not purged
        found_valid = await repo.get_by_scenario(run.id, "CS-002")
        assert found_valid is not None
        assert found_valid.pipeline_result is not None

    async def test_purge_preserves_metadata(self, session: AsyncSession) -> None:
        run_repo = BenchmarkRunRepository(session)
        run = _make_run()
        await run_repo.create(run)

        repo = BenchmarkScenarioResultRepository(session)
        result = _make_result(
            run.id,
            raw_response_retained_until=datetime.now(UTC) - timedelta(days=1),
            pipeline_result={"raw": "data"},
            detector_type="keyword",
            latency_ms=200,
        )
        await repo.create(result)
        await session.flush()

        await purge_expired_responses(session)

        found = await repo.get_by_scenario(run.id, "CS-001")
        assert found is not None
        assert found.pipeline_result is None
        # Metadata preserved
        assert found.passed is True
        assert found.detector_type == "keyword"
        assert found.latency_ms == 200
