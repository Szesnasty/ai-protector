"""Tests for Red Team API routes (Phase 1, spec 01-api-routes).

Uses an isolated in-memory SQLite database via the red_team conftest,
with a test-scoped FastAPI app override so routes never touch PG.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.red_team.persistence.models import BenchmarkRun, BenchmarkScenarioResult

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_PREFIX = "/v1/benchmark"


@pytest.fixture
async def app(session: AsyncSession):
    """Create a FastAPI app with DB dependency overridden to use test session."""
    from fastapi import FastAPI

    from src.red_team.api.routes import router

    test_app = FastAPI()
    test_app.include_router(router, prefix="/v1")

    # Override the DB dependency
    from src.db.session import get_db

    async def _override_db():
        yield session

    test_app.dependency_overrides[get_db] = _override_db
    return test_app


@pytest.fixture
async def client(app):
    """Async HTTP client wired to the test app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_run(
    session: AsyncSession,
    *,
    status: str = "completed",
    pack: str = "core_security",
    target_type: str = "demo",
    score_simple: int | None = 85,
    score_weighted: int | None = 78,
    target_fingerprint: str = "fp_demo_001",
) -> BenchmarkRun:
    run = BenchmarkRun(
        target_type=target_type,
        target_config={"endpoint_url": "http://demo"},
        target_fingerprint=target_fingerprint,
        pack=pack,
        pack_version="1.0.0",
        status=status,
        score_simple=score_simple,
        score_weighted=score_weighted,
        total_in_pack=12,
        total_applicable=10,
        executed=10,
        passed=8,
        failed=2,
        skipped=2,
        skipped_reasons={"safe_mode": 1, "not_applicable": 1},
    )
    session.add(run)
    await session.flush()
    return run


async def _seed_scenario(
    session: AsyncSession,
    run_id: uuid.UUID,
    *,
    scenario_id: str = "sqli-basic",
    passed: bool = True,
    category: str = "injection",
) -> BenchmarkScenarioResult:
    result = BenchmarkScenarioResult(
        run_id=run_id,
        scenario_id=scenario_id,
        category=category,
        severity="critical",
        prompt="test prompt",
        expected="BLOCK",
        actual="BLOCK" if passed else "ALLOW",
        passed=passed,
        detector_type="keyword",
        detector_detail={"matched": ["sql"]},
        latency_ms=42,
    )
    session.add(result)
    await session.flush()
    return result


# ---------------------------------------------------------------------------
# POST /v1/benchmark/runs
# ---------------------------------------------------------------------------


class TestCreateRun:
    async def test_create_run_returns_201(self, client: AsyncClient) -> None:
        resp = await client.post(
            f"{_PREFIX}/runs",
            json={
                "target_type": "demo",
                "target_config": {"endpoint_url": "http://demo"},
                "pack": "core_security",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert data["status"] == "created"
        assert data["pack"] == "core_security"
        assert data["total_in_pack"] > 0
        assert data["total_applicable"] >= 0

    async def test_create_run_409_concurrent(self, client: AsyncClient, session: AsyncSession) -> None:
        # Seed an active run for the same target
        await _seed_run(
            session,
            status="running",
            target_fingerprint="__concurrent__",
            target_type="demo",
        )
        # Use same target_config so fingerprint matches
        # We need to know what fingerprint would be computed — easier to just
        # attempt two creates and check the second fails.
        resp1 = await client.post(
            f"{_PREFIX}/runs",
            json={
                "target_type": "demo",
                "target_config": {"endpoint_url": "http://unique-409"},
                "pack": "core_security",
            },
        )
        assert resp1.status_code == 201

        # Second create with same target should 409
        resp2 = await client.post(
            f"{_PREFIX}/runs",
            json={
                "target_type": "demo",
                "target_config": {"endpoint_url": "http://unique-409"},
                "pack": "core_security",
            },
        )
        assert resp2.status_code == 409


# ---------------------------------------------------------------------------
# GET /v1/benchmark/runs
# ---------------------------------------------------------------------------


class TestListRuns:
    async def test_list_runs_empty(self, client: AsyncClient) -> None:
        resp = await client.get(f"{_PREFIX}/runs")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_runs_paginated(self, client: AsyncClient, session: AsyncSession) -> None:
        for i in range(5):
            await _seed_run(session, target_fingerprint=f"fp_{i}", score_simple=80 + i)

        resp = await client.get(f"{_PREFIX}/runs", params={"limit": 3})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3

    async def test_list_runs_by_target_type(self, client: AsyncClient, session: AsyncSession) -> None:
        await _seed_run(session, target_type="demo", target_fingerprint="fp_d")
        await _seed_run(session, target_type="local_agent", target_fingerprint="fp_l")

        resp = await client.get(f"{_PREFIX}/runs", params={"target_type": "demo"})
        data = resp.json()
        assert all(r["target_type"] == "demo" for r in data)


# ---------------------------------------------------------------------------
# GET /v1/benchmark/runs/:id
# ---------------------------------------------------------------------------


class TestGetRunDetail:
    async def test_get_run_details(self, client: AsyncClient, session: AsyncSession) -> None:
        run = await _seed_run(session)
        resp = await client.get(f"{_PREFIX}/runs/{run.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(run.id)
        assert data["score_simple"] == 85
        assert data["target_type"] == "demo"
        assert "skipped_reasons" in data

    async def test_get_run_404(self, client: AsyncClient) -> None:
        fake_id = uuid.uuid4()
        resp = await client.get(f"{_PREFIX}/runs/{fake_id}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /v1/benchmark/runs/:id/scenarios
# ---------------------------------------------------------------------------


class TestListScenarios:
    async def test_list_scenarios_by_run(self, client: AsyncClient, session: AsyncSession) -> None:
        run = await _seed_run(session)
        await _seed_scenario(session, run.id, scenario_id="sqli-1", passed=True)
        await _seed_scenario(session, run.id, scenario_id="sqli-2", passed=False)

        resp = await client.get(f"{_PREFIX}/runs/{run.id}/scenarios")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    async def test_filter_by_passed(self, client: AsyncClient, session: AsyncSession) -> None:
        run = await _seed_run(session)
        await _seed_scenario(session, run.id, scenario_id="s1", passed=True)
        await _seed_scenario(session, run.id, scenario_id="s2", passed=False)

        resp = await client.get(f"{_PREFIX}/runs/{run.id}/scenarios", params={"passed": "false"})
        data = resp.json()
        assert all(r["passed"] is False for r in data)


# ---------------------------------------------------------------------------
# GET /v1/benchmark/runs/:id/scenarios/:sid
# ---------------------------------------------------------------------------


class TestGetScenarioDetail:
    async def test_get_scenario_detail(self, client: AsyncClient, session: AsyncSession) -> None:
        run = await _seed_run(session)
        await _seed_scenario(session, run.id, scenario_id="sqli-test")

        resp = await client.get(f"{_PREFIX}/runs/{run.id}/scenarios/sqli-test")
        assert resp.status_code == 200
        data = resp.json()
        assert data["scenario_id"] == "sqli-test"
        assert data["prompt"] == "test prompt"
        assert data["detector_type"] == "keyword"

    async def test_get_scenario_404(self, client: AsyncClient, session: AsyncSession) -> None:
        run = await _seed_run(session)
        resp = await client.get(f"{_PREFIX}/runs/{run.id}/scenarios/nonexistent")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /v1/benchmark/runs/:id
# ---------------------------------------------------------------------------


class TestDeleteRun:
    async def test_cancel_running_run(self, client: AsyncClient, session: AsyncSession) -> None:
        run = await _seed_run(session, status="running")
        resp = await client.delete(f"{_PREFIX}/runs/{run.id}")
        assert resp.status_code == 204

        # Verify status changed
        detail = await client.get(f"{_PREFIX}/runs/{run.id}")
        assert detail.json()["status"] == "cancelled"

    async def test_delete_completed_run(self, client: AsyncClient, session: AsyncSession) -> None:
        run = await _seed_run(session, status="completed")
        resp = await client.delete(f"{_PREFIX}/runs/{run.id}")
        assert resp.status_code == 204

        # Verify gone
        detail = await client.get(f"{_PREFIX}/runs/{run.id}")
        assert detail.status_code == 404

    async def test_delete_nonexistent_404(self, client: AsyncClient) -> None:
        resp = await client.delete(f"{_PREFIX}/runs/{uuid.uuid4()}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /v1/benchmark/packs
# ---------------------------------------------------------------------------


class TestListPacks:
    async def test_list_packs(self, client: AsyncClient) -> None:
        resp = await client.get(f"{_PREFIX}/packs")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 2  # core_security + agent_threats at minimum
        pack_names = [p["name"] for p in data]
        assert "core_security" in pack_names
        assert "agent_threats" in pack_names
        for p in data:
            assert "name" in p
            assert "version" in p
            assert "scenario_count" in p
            assert p["scenario_count"] > 0


# ---------------------------------------------------------------------------
# GET /v1/benchmark/compare
# ---------------------------------------------------------------------------


class TestCompareRuns:
    async def test_compare_two_runs(self, client: AsyncClient, session: AsyncSession) -> None:
        run_a = await _seed_run(session, score_simple=70, score_weighted=65, target_fingerprint="fp_cmp")
        run_b = await _seed_run(session, score_simple=90, score_weighted=85, target_fingerprint="fp_cmp")

        # Add scenario results
        await _seed_scenario(session, run_a.id, scenario_id="s1", passed=False)
        await _seed_scenario(session, run_a.id, scenario_id="s2", passed=True)
        await _seed_scenario(session, run_b.id, scenario_id="s1", passed=True)
        await _seed_scenario(session, run_b.id, scenario_id="s2", passed=True)

        resp = await client.get(f"{_PREFIX}/compare", params={"a": str(run_a.id), "b": str(run_b.id)})
        assert resp.status_code == 200
        data = resp.json()
        assert data["score_delta"] == 20  # 90 - 70
        assert data["weighted_delta"] == 20  # 85 - 65
        assert "s1" in data["fixed_failures"]
        assert data["new_failures"] == []

    async def test_compare_different_packs_warning(self, client: AsyncClient, session: AsyncSession) -> None:
        run_a = await _seed_run(session, pack="core_security", target_fingerprint="fp_w1")
        run_b = await _seed_run(session, pack="agent_threats", target_fingerprint="fp_w2")

        resp = await client.get(f"{_PREFIX}/compare", params={"a": str(run_a.id), "b": str(run_b.id)})
        assert resp.status_code == 200
        data = resp.json()
        assert data["warning"] is not None
        assert "different" in data["warning"].lower()

    async def test_compare_404(self, client: AsyncClient) -> None:
        resp = await client.get(
            f"{_PREFIX}/compare",
            params={"a": str(uuid.uuid4()), "b": str(uuid.uuid4())},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /v1/benchmark/runs/:id/progress — SSE
# ---------------------------------------------------------------------------


class TestSSEStream:
    async def test_sse_stream_sends_events(self, client: AsyncClient, session: AsyncSession) -> None:
        """SSE endpoint returns text/event-stream and streams events."""
        import asyncio

        from src.red_team.api.routes import _progress_emitter
        from src.red_team.progress.events import RunCompleteEvent

        run = await _seed_run(session, status="running")

        received: list[str] = []

        async def _consume():
            async with client.stream(
                "GET",
                f"{_PREFIX}/runs/{run.id}/progress",
                headers={"Accept": "text/event-stream"},
            ) as resp:
                assert "text/event-stream" in resp.headers.get("content-type", "")
                async for line in resp.aiter_text():
                    received.append(line)
                    if "run_complete" in line:
                        break

        task = asyncio.create_task(_consume())
        await asyncio.sleep(0.05)

        # Push a terminal event so the subscriber stops
        await _progress_emitter.emit(
            run.id,
            RunCompleteEvent(
                score_simple=90,
                score_weighted=85,
                total_in_pack=10,
                total_applicable=10,
                executed=10,
                passed=9,
                failed=1,
                skipped=0,
                skipped_reasons={},
            ),
        )

        await asyncio.wait_for(task, timeout=5.0)
        combined = "".join(received)
        assert "run_complete" in combined
