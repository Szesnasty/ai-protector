"""Tests for the Progress Emitter module (07-progress-emitter)."""

from __future__ import annotations

import asyncio
import json
import uuid

import pytest

from src.red_team.progress.emitter import ProgressEmitter
from src.red_team.progress.events import (
    ProgressEventType,
    RunCancelledEvent,
    RunCompleteEvent,
    RunFailedEvent,
    ScenarioCompleteEvent,
    ScenarioSkippedEvent,
    ScenarioStartEvent,
    event_type_for,
    is_terminal,
)
from src.red_team.progress.formatter import format_sse

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_sse(raw: str) -> tuple[str, dict]:
    """Parse an SSE string → (event_type, data_dict)."""
    lines = raw.strip().split("\n")
    event_type = ""
    data = ""
    for line in lines:
        if line.startswith("event: "):
            event_type = line[len("event: ") :]
        elif line.startswith("data: "):
            data = line[len("data: ") :]
    return event_type, json.loads(data)


# ---------------------------------------------------------------------------
# SSE Format Tests
# ---------------------------------------------------------------------------


class TestFormatSSE:
    def test_format_sse_scenario_start(self) -> None:
        event = ScenarioStartEvent(scenario_id="sqli-basic", index=1, total_applicable=12)
        sse = format_sse(event)

        assert sse.startswith("event: scenario_start\n")
        assert sse.endswith("\n\n")

        event_type, data = _parse_sse(sse)
        assert event_type == "scenario_start"
        assert data["scenario_id"] == "sqli-basic"
        assert data["index"] == 1
        assert data["total_applicable"] == 12

    def test_format_sse_scenario_complete(self) -> None:
        event = ScenarioCompleteEvent(scenario_id="sqli-basic", passed=True, actual="BLOCK", latency_ms=42)
        sse = format_sse(event)

        event_type, data = _parse_sse(sse)
        assert event_type == "scenario_complete"
        assert data["passed"] is True
        assert data["actual"] == "BLOCK"
        assert data["latency_ms"] == 42

    def test_format_sse_scenario_skipped(self) -> None:
        event = ScenarioSkippedEvent(scenario_id="xss-stored", reason="safe_mode")
        sse = format_sse(event)

        event_type, data = _parse_sse(sse)
        assert event_type == "scenario_skipped"
        assert data["reason"] == "safe_mode"

    def test_format_sse_run_complete(self) -> None:
        event = RunCompleteEvent(
            score_simple=85,
            score_weighted=78,
            total_in_pack=15,
            total_applicable=12,
            executed=10,
            passed=8,
            failed=2,
            skipped=2,
            skipped_reasons={"safe_mode": 1, "not_applicable": 1},
        )
        sse = format_sse(event)

        event_type, data = _parse_sse(sse)
        assert event_type == "run_complete"
        assert data["score_simple"] == 85
        assert data["skipped_reasons"] == {"safe_mode": 1, "not_applicable": 1}

    def test_format_sse_run_failed(self) -> None:
        event = RunFailedEvent(error="connection refused", completed_scenarios=3)
        sse = format_sse(event)

        event_type, data = _parse_sse(sse)
        assert event_type == "run_failed"
        assert data["error"] == "connection refused"

    def test_format_sse_run_cancelled(self) -> None:
        event = RunCancelledEvent(completed_scenarios=5, partial_score=60)
        sse = format_sse(event)

        event_type, data = _parse_sse(sse)
        assert event_type == "run_cancelled"
        assert data["partial_score"] == 60

    def test_format_sse_run_cancelled_no_score(self) -> None:
        event = RunCancelledEvent(completed_scenarios=0, partial_score=None)
        _, data = _parse_sse(format_sse(event))
        assert data["partial_score"] is None


# ---------------------------------------------------------------------------
# Event Payload Serialization
# ---------------------------------------------------------------------------


class TestEventPayloadSerialization:
    """All event payloads must serialize to valid JSON via format_sse."""

    ALL_EVENTS = [
        ScenarioStartEvent(scenario_id="a", index=1, total_applicable=5),
        ScenarioCompleteEvent(scenario_id="a", passed=False, actual="ALLOW", latency_ms=100),
        ScenarioSkippedEvent(scenario_id="b", reason="timeout"),
        RunCompleteEvent(
            score_simple=90,
            score_weighted=85,
            total_in_pack=10,
            total_applicable=8,
            executed=7,
            passed=6,
            failed=1,
            skipped=1,
            skipped_reasons={"timeout": 1},
        ),
        RunFailedEvent(error="boom", completed_scenarios=0),
        RunCancelledEvent(completed_scenarios=3, partial_score=50),
    ]

    @pytest.mark.parametrize("event", ALL_EVENTS, ids=lambda e: type(e).__name__)
    def test_all_serialize_to_valid_json(self, event) -> None:
        sse = format_sse(event)
        _, data = _parse_sse(sse)
        # Must be a dict
        assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# Event Type Mapping
# ---------------------------------------------------------------------------


class TestEventTypeMapping:
    def test_event_type_for_all(self) -> None:
        assert event_type_for(ScenarioStartEvent("x", 1, 1)) == ProgressEventType.SCENARIO_START
        assert event_type_for(ScenarioCompleteEvent("x", True, "BLOCK", 0)) == ProgressEventType.SCENARIO_COMPLETE
        assert event_type_for(ScenarioSkippedEvent("x", "r")) == ProgressEventType.SCENARIO_SKIPPED
        assert event_type_for(RunCompleteEvent(0, 0, 0, 0, 0, 0, 0, 0, {})) == ProgressEventType.RUN_COMPLETE
        assert event_type_for(RunFailedEvent("e", 0)) == ProgressEventType.RUN_FAILED
        assert event_type_for(RunCancelledEvent(0, None)) == ProgressEventType.RUN_CANCELLED

    def test_event_type_for_unknown_raises(self) -> None:
        with pytest.raises(TypeError, match="Unknown event type"):
            event_type_for("not an event")  # type: ignore[arg-type]

    def test_terminal_events(self) -> None:
        assert is_terminal(ProgressEventType.RUN_COMPLETE)
        assert is_terminal(ProgressEventType.RUN_FAILED)
        assert is_terminal(ProgressEventType.RUN_CANCELLED)
        assert not is_terminal(ProgressEventType.SCENARIO_START)
        assert not is_terminal(ProgressEventType.SCENARIO_COMPLETE)
        assert not is_terminal(ProgressEventType.SCENARIO_SKIPPED)


# ---------------------------------------------------------------------------
# Emitter Pub/Sub Tests
# ---------------------------------------------------------------------------


class TestProgressEmitter:
    async def test_emit_reaches_subscriber(self) -> None:
        emitter = ProgressEmitter()
        run_id = uuid.uuid4()
        received: list[str] = []

        async def _collect():
            async for msg in emitter.subscribe(run_id):
                received.append(msg)

        task = asyncio.create_task(_collect())
        # Give subscriber time to register
        await asyncio.sleep(0.01)

        event = ScenarioStartEvent(scenario_id="a", index=1, total_applicable=5)
        await emitter.emit(run_id, event)
        # Send terminal event to stop subscriber
        await emitter.emit(run_id, RunCompleteEvent(90, 85, 5, 5, 5, 4, 1, 0, {}))

        await asyncio.wait_for(task, timeout=1.0)
        assert len(received) == 2
        assert "scenario_start" in received[0]
        assert "run_complete" in received[1]

    async def test_multiple_subscribers(self) -> None:
        emitter = ProgressEmitter()
        run_id = uuid.uuid4()
        received_a: list[str] = []
        received_b: list[str] = []

        async def _collect(store: list[str]):
            async for msg in emitter.subscribe(run_id):
                store.append(msg)

        task_a = asyncio.create_task(_collect(received_a))
        task_b = asyncio.create_task(_collect(received_b))
        await asyncio.sleep(0.01)

        assert emitter.subscriber_count(run_id) == 2

        event = ScenarioStartEvent(scenario_id="x", index=1, total_applicable=1)
        await emitter.emit(run_id, event)
        await emitter.emit(run_id, RunCompleteEvent(100, 100, 1, 1, 1, 1, 0, 0, {}))

        await asyncio.wait_for(asyncio.gather(task_a, task_b), timeout=1.0)
        assert len(received_a) == 2
        assert len(received_b) == 2

    async def test_subscribe_only_own_run(self) -> None:
        emitter = ProgressEmitter()
        run_a = uuid.uuid4()
        run_b = uuid.uuid4()
        received_a: list[str] = []
        received_b: list[str] = []

        async def _collect(rid: uuid.UUID, store: list[str]):
            async for msg in emitter.subscribe(rid):
                store.append(msg)

        task_a = asyncio.create_task(_collect(run_a, received_a))
        task_b = asyncio.create_task(_collect(run_b, received_b))
        await asyncio.sleep(0.01)

        # Emit to run_a only
        await emitter.emit(run_a, ScenarioStartEvent("a", 1, 1))
        await emitter.emit(run_a, RunCompleteEvent(100, 100, 1, 1, 1, 1, 0, 0, {}))
        # Emit to run_b only
        await emitter.emit(run_b, RunCompleteEvent(50, 50, 1, 1, 1, 0, 1, 0, {}))

        await asyncio.wait_for(asyncio.gather(task_a, task_b), timeout=1.0)

        # run_a gets its 2 events, run_b gets its 1 event
        assert len(received_a) == 2
        assert len(received_b) == 1
        # run_a events don't leak to run_b
        assert "scenario_start" not in received_b[0]

    async def test_cleanup_after_complete(self) -> None:
        emitter = ProgressEmitter()
        run_id = uuid.uuid4()

        async def _collect():
            async for _msg in emitter.subscribe(run_id):
                pass

        task = asyncio.create_task(_collect())
        await asyncio.sleep(0.01)
        assert emitter.subscriber_count(run_id) == 1

        await emitter.emit(run_id, RunCompleteEvent(100, 100, 1, 1, 1, 1, 0, 0, {}))
        await asyncio.wait_for(task, timeout=1.0)

        # After terminal event + subscriber exit, cleanup should have occurred
        assert emitter.subscriber_count(run_id) == 0

    async def test_cleanup_after_failed(self) -> None:
        emitter = ProgressEmitter()
        run_id = uuid.uuid4()

        async def _collect():
            async for _msg in emitter.subscribe(run_id):
                pass

        task = asyncio.create_task(_collect())
        await asyncio.sleep(0.01)

        await emitter.emit(run_id, RunFailedEvent(error="boom", completed_scenarios=0))
        await asyncio.wait_for(task, timeout=1.0)
        assert emitter.subscriber_count(run_id) == 0

    async def test_cleanup_after_cancelled(self) -> None:
        emitter = ProgressEmitter()
        run_id = uuid.uuid4()

        async def _collect():
            async for _msg in emitter.subscribe(run_id):
                pass

        task = asyncio.create_task(_collect())
        await asyncio.sleep(0.01)

        await emitter.emit(run_id, RunCancelledEvent(completed_scenarios=2, partial_score=40))
        await asyncio.wait_for(task, timeout=1.0)
        assert emitter.subscriber_count(run_id) == 0

    async def test_emit_no_subscribers_is_noop(self) -> None:
        """emit() with no subscribers should not raise."""
        emitter = ProgressEmitter()
        run_id = uuid.uuid4()
        await emitter.emit(run_id, ScenarioStartEvent("x", 1, 1))
        # No error → pass

    async def test_subscriber_count(self) -> None:
        emitter = ProgressEmitter()
        run_id = uuid.uuid4()
        assert emitter.subscriber_count(run_id) == 0

        async def _collect():
            async for _msg in emitter.subscribe(run_id):
                pass

        task = asyncio.create_task(_collect())
        await asyncio.sleep(0.01)
        assert emitter.subscriber_count(run_id) == 1

        await emitter.emit(run_id, RunCompleteEvent(0, 0, 0, 0, 0, 0, 0, 0, {}))
        await asyncio.wait_for(task, timeout=1.0)
        assert emitter.subscriber_count(run_id) == 0
