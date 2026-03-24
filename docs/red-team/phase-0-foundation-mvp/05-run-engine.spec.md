# 05 — Run Engine

> **Module:** `red-team/engine/`
> **Phase:** 0 (Foundation) — MVP
> **Depends on:** Pack Loader, Evaluator Engine, Score Calculator, HTTP Client, Persistence, Progress Emitter

## Scope

Orchestrates a full benchmark run: load pack → iterate scenarios → send prompts via HTTP Client → evaluate → collect results → compute scores → persist. This is the central coordinator.

## Implementation Steps

### Step 1: Define RunConfig

```python
@dataclass
class RunConfig:
    target_type: str       # "demo" | "local_agent" | "hosted_endpoint"
    target_config: dict    # endpoint_url, agent_type, safe_mode, timeout_s, etc.
    pack: str              # "core_security" | "agent_threats"
    policy: str | None     # nullable for external targets
```

### Step 2: Implement run lifecycle state machine

States: `created → running → completed | cancelled | failed`

- `create_run(config: RunConfig) → BenchmarkRun`
  - Validate config
  - Load and filter pack via Pack Loader
  - Persist run record with status `created`
  - Return run object
- `start_run(run_id) → AsyncGenerator[ProgressEvent]`
  - Transition to `running`
  - Iterate scenarios, yield progress events
- `cancel_run(run_id)` — transition to `cancelled`, persist partial results
- Transition to `failed` on fatal error (3 consecutive connection failures)

### Step 3: Implement scenario execution loop

```python
async def execute_run(run: BenchmarkRun, scenarios: list[Scenario]):
    for i, scenario in enumerate(scenarios):
        emit(scenario_start(scenario, i, total))
        try:
            response = await http_client.send(scenario.prompt, run.target_config)
            eval_result = evaluator.evaluate_scenario(scenario, response)
            persist_result(run.id, scenario, eval_result, response)
            emit(scenario_complete(scenario, eval_result))
        except TimeoutError:
            persist_skipped(run.id, scenario, "timeout")
            emit(scenario_skipped(scenario, "timeout"))
        except ConnectionError:
            handle_retry_or_fail(...)
    scores = compute_scores(all_results)
    finalize_run(run.id, scores)
    emit(run_complete(scores))
```

### Step 4: Implement retry logic

- Per-scenario timeout: `target_config.timeout_s` (default 30s, max 120s)
- On connection failure: retry once after 2s
- 3 consecutive failures → mark run as `failed`, persist partial results
- Emit error event via Progress Emitter

### Step 5: Implement concurrency guard

- MVP: one run at a time per target
- Before creating a run, check for `status = running` on same target
- Return 409 Conflict if a run is already active

### Step 6: Wire all modules together

- Run Engine imports: Pack Loader, Evaluator, Score Calculator, HTTP Client, Persistence, Progress
- Each dependency is injected (constructor / parameter), not hard-imported
- This enables testing with mocks for every dependency

## Tests

| Test | What it verifies |
|------|-----------------|
| `test_create_run_validates_config` | Invalid config → error |
| `test_create_run_persists_record` | Run record created in DB with status `created` |
| `test_run_lifecycle_happy_path` | created → running → completed with all results |
| `test_run_lifecycle_cancel` | Cancel mid-run → `cancelled`, partial results preserved |
| `test_run_lifecycle_fail_on_connection` | 3 consecutive failures → `failed`, partial results |
| `test_scenario_timeout_skips` | Slow response → scenario skipped with reason `timeout` |
| `test_retry_on_first_failure` | First connection failure retried, second succeeds |
| `test_concurrency_guard` | Second run on same target → 409 |
| `test_partial_results_persisted` | Failed run still has results for completed scenarios |
| `test_scores_computed_on_complete` | Completion triggers score calculation |
| `test_progress_events_emitted` | Each scenario emits start/complete/skipped events |
| `test_run_with_mock_http_client` | Full run against mocked HTTP → correct results |
| `test_skipped_scenarios_excluded_from_score` | Skipped scenarios don't affect score |

## Definition of Done

- [ ] Run lifecycle state machine implemented (created → running → completed/cancelled/failed)
- [ ] Scenario execution loop with per-scenario timeout and error handling
- [ ] Retry logic (1 retry, 3 consecutive = fail)
- [ ] Concurrency guard (1 run per target)
- [ ] All dependencies injected, testable with mocks
- [ ] Full integration test with mock HTTP client passes
- [ ] Partial results always persisted on cancel/fail
- [ ] All tests pass, >90% coverage
