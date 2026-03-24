# 07 — Progress Emitter

> **Module:** `red-team/progress/`
> **Phase:** 0 (Foundation) — MVP
> **Depends on:** Scenario Schema (`red-team/schemas/`)

## Scope

Formats and emits SSE (Server-Sent Events) during a benchmark run. Pure formatting — no HTTP server logic (that's in `api/`).

## Implementation Steps

### Step 1: Define event types

```python
class ProgressEventType(str, Enum):
    SCENARIO_START    = "scenario_start"
    SCENARIO_COMPLETE = "scenario_complete"
    SCENARIO_SKIPPED  = "scenario_skipped"
    RUN_COMPLETE      = "run_complete"
    RUN_FAILED        = "run_failed"
    RUN_CANCELLED     = "run_cancelled"
```

### Step 2: Define event payload schemas

```python
@dataclass
class ScenarioStartEvent:
    scenario_id: str
    index: int              # 1-based
    total_applicable: int   # Denominator for progress (not total_in_pack)

@dataclass
class ScenarioCompleteEvent:
    scenario_id: str
    passed: bool
    actual: str       # "BLOCK" | "ALLOW" | "MODIFY"
    latency_ms: int

@dataclass
class ScenarioSkippedEvent:
    scenario_id: str
    reason: str       # "safe_mode" | "not_applicable" | "timeout" | etc.

@dataclass
class RunCompleteEvent:
    score_simple: int
    score_weighted: int
    total_in_pack: int
    total_applicable: int
    executed: int
    passed: int
    failed: int
    skipped: int
    skipped_reasons: dict[str, int]

@dataclass
class RunFailedEvent:
    error: str
    completed_scenarios: int

@dataclass
class RunCancelledEvent:
    completed_scenarios: int
    partial_score: int | None
```

### Step 3: Implement SSE formatter

```python
def format_sse(event_type: str, data: dict) → str:
    """Format as SSE: 'event: {type}\ndata: {json}\n\n'"""
```

### Step 4: Implement event emitter interface

```python
class ProgressEmitter:
    async def emit(self, event: ProgressEvent) → None
    def subscribe(self, run_id: UUID) → AsyncGenerator[str, None]
```

- In-memory pub/sub per run_id (asyncio.Queue or similar)
- `emit()` pushes to all subscribers of that run
- `subscribe()` yields SSE-formatted strings
- Cleanup: remove subscribers when run completes/fails/cancels

## Tests

| Test | What it verifies |
|------|-----------------|
| `test_format_sse_scenario_start` | Correct SSE format for scenario_start |
| `test_format_sse_scenario_complete` | Correct SSE format for scenario_complete |
| `test_format_sse_run_complete` | Correct SSE format with score data |
| `test_emit_reaches_subscriber` | Emitted event arrives at subscriber |
| `test_multiple_subscribers` | Multiple subscribers each receive the event |
| `test_subscribe_only_own_run` | Subscriber for run A doesn't receive events from run B |
| `test_cleanup_after_complete` | Subscribers cleaned up after run_complete |
| `test_event_payload_serialization` | All event data serializes to valid JSON |

## Definition of Done

- [ ] All 6 event types defined with payload schemas
- [ ] SSE formatter produces valid SSE format
- [ ] Emitter pub/sub works with async generators
- [ ] Subscribers isolated per run_id
- [ ] Cleanup on run completion
- [ ] All tests pass, >90% coverage
- [ ] No HTTP server logic — that belongs in `api/`
