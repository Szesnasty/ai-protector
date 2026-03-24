"""SSE event types and payload schemas for benchmark progress."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ProgressEventType(str, Enum):
    """SSE event types emitted during a benchmark run."""

    SCENARIO_START = "scenario_start"
    SCENARIO_COMPLETE = "scenario_complete"
    SCENARIO_SKIPPED = "scenario_skipped"
    RUN_COMPLETE = "run_complete"
    RUN_FAILED = "run_failed"
    RUN_CANCELLED = "run_cancelled"


# ---------------------------------------------------------------------------
# Event payloads
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScenarioStartEvent:
    """Emitted when a scenario begins execution."""

    scenario_id: str
    index: int  # 1-based
    total_applicable: int  # denominator for progress (not total_in_pack)


@dataclass(frozen=True)
class ScenarioCompleteEvent:
    """Emitted when a scenario finishes (pass or fail)."""

    scenario_id: str
    passed: bool
    actual: str  # "BLOCK" | "ALLOW" | "MODIFY"
    latency_ms: int


@dataclass(frozen=True)
class ScenarioSkippedEvent:
    """Emitted when a scenario is skipped."""

    scenario_id: str
    reason: str  # "safe_mode" | "not_applicable" | "timeout" | etc.


@dataclass(frozen=True)
class RunCompleteEvent:
    """Emitted once when the entire run finishes successfully."""

    score_simple: int
    score_weighted: int
    total_in_pack: int
    total_applicable: int
    executed: int
    passed: int
    failed: int
    skipped: int
    skipped_reasons: dict[str, int]


@dataclass(frozen=True)
class RunFailedEvent:
    """Emitted when the run terminates with an unrecoverable error."""

    error: str
    completed_scenarios: int


@dataclass(frozen=True)
class RunCancelledEvent:
    """Emitted when the run is cancelled by the user."""

    completed_scenarios: int
    partial_score: int | None


# Union of all event payloads for type-checking convenience.
ProgressEvent = (
    ScenarioStartEvent
    | ScenarioCompleteEvent
    | ScenarioSkippedEvent
    | RunCompleteEvent
    | RunFailedEvent
    | RunCancelledEvent
)

# Map from payload type → ProgressEventType
_EVENT_TYPE_MAP: dict[type, ProgressEventType] = {
    ScenarioStartEvent: ProgressEventType.SCENARIO_START,
    ScenarioCompleteEvent: ProgressEventType.SCENARIO_COMPLETE,
    ScenarioSkippedEvent: ProgressEventType.SCENARIO_SKIPPED,
    RunCompleteEvent: ProgressEventType.RUN_COMPLETE,
    RunFailedEvent: ProgressEventType.RUN_FAILED,
    RunCancelledEvent: ProgressEventType.RUN_CANCELLED,
}

# Terminal events that signal subscriber cleanup.
_TERMINAL_EVENTS = frozenset(
    {
        ProgressEventType.RUN_COMPLETE,
        ProgressEventType.RUN_FAILED,
        ProgressEventType.RUN_CANCELLED,
    }
)


def event_type_for(event: ProgressEvent) -> ProgressEventType:
    """Resolve the SSE event type string for a given payload instance."""
    et = _EVENT_TYPE_MAP.get(type(event))
    if et is None:
        raise TypeError(f"Unknown event type: {type(event).__name__}")
    return et


def is_terminal(event_type: ProgressEventType) -> bool:
    """Return True if the event type signals run end."""
    return event_type in _TERMINAL_EVENTS
