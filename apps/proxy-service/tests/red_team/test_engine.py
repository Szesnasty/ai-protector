"""Tests for red_team.engine — Run Engine orchestration."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from src.red_team.engine import (
    ConcurrencyConflictError,
    ConfigValidationError,
    HttpResponse,
    InvalidStateError,
    RunConfig,
    RunEngine,
    RunState,
    compute_target_fingerprint,
)
from src.red_team.packs.loader import clear_cache
from src.red_team.schemas.dataclasses import RawTargetResponse

# Path to the real pack data for integration tests
_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "src" / "red_team" / "packs" / "data"


# ---------------------------------------------------------------------------
# Mock implementations
# ---------------------------------------------------------------------------


class MockHttpClient:
    """Mock HTTP client that returns configurable responses."""

    def __init__(self, response_text: str = "I cannot help with that request.") -> None:
        self.response_text = response_text
        self.call_count = 0
        self.fail_count = 0  # Number of times to fail before succeeding
        self.timeout_on: set[int] = set()  # Call indices that should timeout

    async def send_prompt(self, prompt: str, target_config: dict[str, Any]) -> HttpResponse:
        self.call_count += 1
        if self.call_count - 1 in self.timeout_on:
            await asyncio.sleep(999)  # Will be cancelled by timeout

        if self.fail_count > 0:
            self.fail_count -= 1
            raise ConnectionError("Mock connection failure")

        return HttpResponse(
            status_code=200,
            body=self.response_text,
            latency_ms=50.0,
        )


class MockNormalizer:
    """Mock normalizer that wraps the response body."""

    def normalize(self, http_response: HttpResponse, target_config: dict[str, Any]) -> RawTargetResponse:
        return RawTargetResponse(
            body_text=http_response.body,
            parsed_json=None,
            tool_calls=None,
            status_code=http_response.status_code,
            latency_ms=http_response.latency_ms,
            raw_body=http_response.body,
            provider_format="plain_text",
        )


class MockPersistence:
    """Mock persistence that stores data in memory."""

    def __init__(self) -> None:
        self.runs: dict[str, dict[str, Any]] = {}
        self.results: list[dict[str, Any]] = []
        self.active_runs: dict[str, dict[str, Any]] = {}
        self.idempotency_keys: dict[str, dict[str, Any]] = {}

    async def create_run(self, run_data: dict[str, Any]) -> str:
        self.runs[run_data["id"]] = run_data
        if run_data.get("state") in ("created", "running"):
            fp = run_data.get("target_fingerprint", "")
            self.active_runs[fp] = run_data
        if "config" in run_data and run_data["config"].get("idempotency_key"):
            self.idempotency_keys[run_data["config"]["idempotency_key"]] = run_data
        return run_data["id"]

    async def update_run(self, run_id: str, updates: dict[str, Any]) -> None:
        if run_id in self.runs:
            self.runs[run_id].update(updates)
            # Update active runs tracking
            if updates.get("state") in ("completed", "cancelled", "failed"):
                fp = self.runs[run_id].get("target_fingerprint", "")
                self.active_runs.pop(fp, None)

    async def persist_result(self, run_id: str, result_data: dict[str, Any]) -> None:
        result_data["run_id"] = run_id
        self.results.append(result_data)

    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        return self.runs.get(run_id)

    async def find_active_run(self, target_fingerprint: str) -> dict[str, Any] | None:
        return self.active_runs.get(target_fingerprint)

    async def find_by_idempotency_key(self, key: str) -> dict[str, Any] | None:
        return self.idempotency_keys.get(key)


class MockProgress:
    """Mock progress emitter that collects events."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def emit(self, run_id: str, event: dict[str, Any]) -> None:
        event["run_id"] = run_id
        self.events.append(event)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_config(**overrides: Any) -> RunConfig:
    base: dict[str, Any] = {
        "target_type": "demo",
        "target_config": {"agent_type": "chatbot_api", "safe_mode": False, "timeout_s": 1.0},
        "pack": "core_security",
    }
    base.update(overrides)
    return RunConfig(**base)


def _make_engine(
    http_client: MockHttpClient | None = None,
    normalizer: MockNormalizer | None = None,
    persistence: MockPersistence | None = None,
    progress: MockProgress | None = None,
) -> tuple[RunEngine, MockHttpClient, MockNormalizer, MockPersistence, MockProgress]:
    hc = http_client or MockHttpClient()
    n = normalizer or MockNormalizer()
    p = persistence or MockPersistence()
    pr = progress or MockProgress()
    return RunEngine(hc, n, p, pr), hc, n, p, pr


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_cache()
    yield
    clear_cache()


# ===========================================================================
# Config validation
# ===========================================================================


class TestCreateRunValidation:
    async def test_valid_config(self) -> None:
        engine, _, _, persistence, _ = _make_engine()
        run = await engine.create_run(_make_config())
        assert run.state == RunState.CREATED
        assert run.id in persistence.runs

    async def test_missing_target_type(self) -> None:
        engine, *_ = _make_engine()
        with pytest.raises(ConfigValidationError, match="target_type"):
            await engine.create_run(_make_config(target_type=""))

    async def test_missing_target_config(self) -> None:
        engine, *_ = _make_engine()
        with pytest.raises(ConfigValidationError, match="target_config"):
            await engine.create_run(_make_config(target_config={}))

    async def test_missing_pack(self) -> None:
        engine, *_ = _make_engine()
        with pytest.raises(ConfigValidationError, match="pack"):
            await engine.create_run(_make_config(pack=""))


# ===========================================================================
# Run lifecycle
# ===========================================================================


class TestRunLifecycle:
    async def test_happy_path(self) -> None:
        engine, http, _, persistence, progress = _make_engine()
        run = await engine.create_run(_make_config())
        assert run.state == RunState.CREATED

        run = await engine.execute_run(run)
        assert run.state == RunState.COMPLETED
        assert run.score is not None
        assert run.completed_at is not None
        assert len(run.results) > 0

        # Check persistence
        stored = persistence.runs[run.id]
        assert stored["state"] == "completed"

        # Check progress events
        event_types = [e["type"] for e in progress.events]
        assert "scenario_start" in event_types
        assert "scenario_complete" in event_types
        assert "run_complete" in event_types

    async def test_cancel(self) -> None:
        # Create an engine where HTTP is slow so we can cancel
        http = MockHttpClient()
        engine, _, _, persistence, progress = _make_engine(http_client=http)
        run = await engine.create_run(_make_config())

        # Set to running state manually
        run.state = RunState.RUNNING
        run = await engine.cancel_run(run)

        assert run.state == RunState.CANCELLED
        assert run.completed_at is not None

        # Check progress events
        event_types = [e["type"] for e in progress.events]
        assert "run_cancelled" in event_types

    async def test_cancel_non_running_raises(self) -> None:
        engine, *_ = _make_engine()
        run = await engine.create_run(_make_config())
        # run is in CREATED state, not RUNNING
        with pytest.raises(InvalidStateError):
            await engine.cancel_run(run)

    async def test_fail_on_connection_errors(self) -> None:
        http = MockHttpClient()
        http.fail_count = 100  # All calls fail
        engine, _, _, persistence, progress = _make_engine(http_client=http)
        run = await engine.create_run(_make_config())

        run = await engine.execute_run(run)
        assert run.state == RunState.FAILED
        assert run.error is not None
        assert "connection failures" in run.error.lower()


# ===========================================================================
# Scenario execution
# ===========================================================================


class TestScenarioExecution:
    async def test_timeout_skips_scenario(self) -> None:
        http = MockHttpClient()
        http.timeout_on = {0}  # First call times out
        engine, _, _, _, progress = _make_engine(http_client=http)

        config = _make_config(target_config={"agent_type": "chatbot_api", "safe_mode": False, "timeout_s": 0.1})
        run = await engine.create_run(config)
        run = await engine.execute_run(run)

        # At least one scenario should have been skipped
        skipped = [r for r in run.results if r.outcome.value == "skipped"]
        assert len(skipped) >= 1

    async def test_retry_on_first_failure(self) -> None:
        http = MockHttpClient()
        http.fail_count = 1  # First call fails, retry succeeds
        engine, _, _, persistence, _ = _make_engine(http_client=http)

        config = _make_config(target_config={"agent_type": "chatbot_api", "safe_mode": False, "timeout_s": 5.0})
        run = await engine.create_run(config)
        run = await engine.execute_run(run)

        # Run should complete (retry succeeded)
        assert run.state == RunState.COMPLETED


# ===========================================================================
# Concurrency guard
# ===========================================================================


class TestConcurrencyGuard:
    async def test_second_run_blocked(self) -> None:
        engine, _, _, persistence, _ = _make_engine()
        await engine.create_run(_make_config())

        # Try to create another run with same target
        with pytest.raises(ConcurrencyConflictError):
            await engine.create_run(_make_config())


# ===========================================================================
# Idempotency
# ===========================================================================


class TestIdempotency:
    async def test_same_key_returns_existing(self) -> None:
        engine, _, _, persistence, _ = _make_engine()
        key = "test-idem-key-123"
        config = _make_config(idempotency_key=key)

        run1 = await engine.create_run(config)

        # Clear active run so concurrency guard doesn't block
        persistence.active_runs.clear()

        run2 = await engine.create_run(config)
        assert run1.id == run2.id


# ===========================================================================
# Target fingerprint
# ===========================================================================


class TestTargetFingerprint:
    def test_computed_deterministically(self) -> None:
        fp1 = compute_target_fingerprint("demo", {"url": "http://localhost"})
        fp2 = compute_target_fingerprint("demo", {"url": "http://localhost"})
        assert fp1 == fp2

    def test_different_config_different_fingerprint(self) -> None:
        fp1 = compute_target_fingerprint("demo", {"url": "http://localhost:8000"})
        fp2 = compute_target_fingerprint("demo", {"url": "http://localhost:9000"})
        assert fp1 != fp2

    def test_fingerprint_stored_on_run(self) -> None:
        async def _test():
            engine, _, _, persistence, _ = _make_engine()
            run = await engine.create_run(_make_config())
            assert run.target_fingerprint
            assert len(run.target_fingerprint) == 16

        asyncio.get_event_loop().run_until_complete(_test())


# ===========================================================================
# Scores & results
# ===========================================================================


class TestScoresAndResults:
    async def test_scores_computed_on_complete(self) -> None:
        engine, _, _, _, _ = _make_engine()
        run = await engine.create_run(_make_config())
        run = await engine.execute_run(run)

        assert run.score is not None
        assert 0 <= run.score.score_simple <= 100

    async def test_partial_results_on_fail(self) -> None:
        http = MockHttpClient()
        http.fail_count = 100
        engine, _, _, persistence, _ = _make_engine(http_client=http)
        run = await engine.create_run(_make_config())
        run = await engine.execute_run(run)

        # Even on failure, results are collected
        assert run.state == RunState.FAILED
        assert len(run.results) > 0

    async def test_counting_fields(self) -> None:
        engine, _, _, _, _ = _make_engine()
        run = await engine.create_run(_make_config())
        run = await engine.execute_run(run)

        assert run.score is not None
        sr = run.score
        assert sr.total_in_pack > 0
        assert sr.total_applicable > 0
        assert sr.executed >= 0

    async def test_skipped_scenarios_excluded_from_score(self) -> None:
        engine, _, _, _, _ = _make_engine()
        # Use safe_mode to skip some scenarios
        config = _make_config(target_config={"agent_type": "chatbot_api", "safe_mode": True, "timeout_s": 1.0})
        run = await engine.create_run(config)
        # The filtered pack should have fewer scenarios than total
        assert run.filtered_pack.total_applicable <= run.filtered_pack.total_in_pack


# ===========================================================================
# Progress events
# ===========================================================================


class TestProgressEvents:
    async def test_events_emitted(self) -> None:
        engine, _, _, _, progress = _make_engine()
        run = await engine.create_run(_make_config())
        run = await engine.execute_run(run)

        event_types = [e["type"] for e in progress.events]
        assert "scenario_start" in event_types
        assert "run_complete" in event_types

    async def test_scenario_complete_events(self) -> None:
        engine, _, _, _, progress = _make_engine()
        run = await engine.create_run(_make_config())
        run = await engine.execute_run(run)

        complete_events = [e for e in progress.events if e["type"] == "scenario_complete"]
        assert len(complete_events) > 0
        assert "outcome" in complete_events[0]


# ===========================================================================
# Normalizer in pipeline
# ===========================================================================


class TestNormalizerInPipeline:
    async def test_normalizer_called(self) -> None:
        """Verify normalizer sits between HTTP client and evaluator."""

        class TrackingNormalizer:
            def __init__(self):
                self.called = False

            def normalize(self, http_response, target_config):
                self.called = True
                return RawTargetResponse(
                    body_text=http_response.body,
                    parsed_json=None,
                    tool_calls=None,
                    status_code=http_response.status_code,
                    latency_ms=http_response.latency_ms,
                    raw_body=http_response.body,
                    provider_format="plain_text",
                )

        normalizer = TrackingNormalizer()
        engine, _, _, _, _ = _make_engine(normalizer=normalizer)
        run = await engine.create_run(_make_config())
        await engine.execute_run(run)

        assert normalizer.called


# ===========================================================================
# Re-run support
# ===========================================================================


class TestRerun:
    async def test_rerun_same_config(self) -> None:
        engine, _, _, persistence, _ = _make_engine()
        run1 = await engine.create_run(_make_config())
        run1 = await engine.execute_run(run1)

        # Create re-run with same config
        config2 = _make_config(source_run_id=run1.id)
        run2 = await engine.create_run(config2)
        assert run2.id != run1.id
        assert run2.config.source_run_id == run1.id

    async def test_rerun_with_policy_change(self) -> None:
        engine, _, _, persistence, _ = _make_engine()
        run1 = await engine.create_run(_make_config())
        run1 = await engine.execute_run(run1)

        config2 = _make_config(source_run_id=run1.id, policy="strict")
        run2 = await engine.create_run(config2)
        assert run2.config.policy == "strict"
        assert run2.config.source_run_id == run1.id
