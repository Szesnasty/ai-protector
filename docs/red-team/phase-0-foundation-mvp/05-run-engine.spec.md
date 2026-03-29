# 05 — Run Engine

> **Module:** `red-team/engine/`
> **Phase:** 0 (Foundation) — MVP
> **Depends on:** Pack Loader, Evaluator Engine, Score Calculator, HTTP Client, Response Normalizer, Persistence, Progress Emitter
> **Updated:** 2026-03-24 — aligned with counting / normalizer / worker boundary contracts

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
    source_run_id: UUID | None = None  # Set when this is a re-run (3 types: same, clone, after-protection)
    idempotency_key: UUID | None = None  # Client-generated, prevents double-click duplicates
```

> `target_fingerprint` is computed from `target_type + target_config` on run creation (see main spec → Target fingerprint). Not a RunConfig field — derived automatically.

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
        emit(scenario_start(scenario, i, total_applicable))
        try:
            raw_http = await http_client.send(scenario.prompt, run.target_config)
            response = normalizer.normalize(raw_http)   # HTTP → RawTargetResponse
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

> **Pipeline:** HTTP Client → Response Normalizer → Evaluator Engine → Score Calculator

### Step 4: Implement retry logic

- Per-scenario timeout: `target_config.timeout_s` (default 30s, max 120s)
- On connection failure: retry once after 2s
- 3 consecutive failures → mark run as `failed`, persist partial results
- Emit error event via Progress Emitter

### Step 5: Implement concurrency guard

- MVP: one run at a time per target
- Before creating a run, compute `target_fingerprint` and check for `status = running` with same fingerprint
- Return 409 Conflict if a run is already active
- Use `idempotency_key` (from request) to detect double-click: if same key within 60s → return existing `run_id` (200), don't create new run

### Step 6: Execution boundary (API vs Worker)

```
API process (FastAPI)          Worker process (BackgroundTasks MVP → Celery future)
─────────────────────          ──────────────────────────────────────────────────────
POST /runs                     execute_run()
  → validate config              → iterate scenarios
  → load & filter pack           → HTTP Client → Normalizer → Evaluator
  → persist run (status=created) → persist each result
  → enqueue to worker            → compute scores
  → return 202 + run_id          → finalize run (status=completed)
```

- API creates the run record, returns immediately with `202 Accepted` + `run_id`
- Worker picks up execution asynchronously
- MVP: `BackgroundTasks` (single-process); future: Celery with Redis broker
- The worker writes directly to the same DB — no message-passing for results

### Step 7: Re-run support

3 re-run operations supported via `source_run_id`:

| Operation | Description | Config change |
|-----------|-------------|---------------|
| Re-run (same) | Repeat exact config | `source_run_id` = original, config copied |
| Clone & modify | New run based on original | `source_run_id` = original, config modified |
| Re-run after protection | Compare before/after | `source_run_id` = original, policy added/changed |

All 3 create a new `BenchmarkRun` record — immutable history, no overwrites.

### Step 8: Wire all modules together

- Run Engine imports: Pack Loader, Evaluator, Score Calculator, HTTP Client, Response Normalizer, Persistence, Progress
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
| `test_concurrency_guard` | Second run on same `target_fingerprint` → 409 |
| `test_partial_results_persisted` | Failed run still has results for completed scenarios |
| `test_scores_computed_on_complete` | Completion triggers score calculation |
| `test_progress_events_emitted` | Each scenario emits start/complete/skipped events |
| `test_run_with_mock_http_client` | Full run against mocked HTTP → correct results |
| `test_skipped_scenarios_excluded_from_score` | Skipped scenarios don't affect score |
| `test_normalizer_in_pipeline` | HTTP response goes through normalizer before evaluator |
| `test_worker_execution_async` | `execute_run()` runs in background, API returns 202 |
| `test_rerun_same_config` | Re-run copies config exactly, sets `source_run_id` |
| `test_rerun_clone_modify` | Clone allows config changes, sets `source_run_id` |
| `test_rerun_after_protection` | Re-run with policy change, sets `source_run_id` |
| `test_counting_fields_in_result` | Completed run has `total_in_pack`, `total_applicable`, `executed`, `skipped_reasons` |
| `test_idempotency_key_prevents_duplicate` | Same key within 60s → returns existing run_id, not new |
| `test_idempotency_key_expired` | Same key after 60s → creates new run |
| `test_target_fingerprint_computed` | Fingerprint derived correctly from target_type + config |

## Definition of Done

- [ ] Run lifecycle state machine implemented (created → running → completed/cancelled/failed)
- [ ] Scenario execution loop with per-scenario timeout and error handling
- [ ] Retry logic (1 retry, 3 consecutive = fail)
- [ ] Concurrency guard (1 run per `target_fingerprint`)
- [ ] Idempotency key: duplicate POST within 60s → return existing run_id
- [ ] `target_fingerprint` computed on creation, stored on run record
- [ ] All dependencies injected (incl. Response Normalizer), testable with mocks
- [ ] Response Normalizer sits between HTTP Client and Evaluator in pipeline
- [ ] Worker boundary: API returns 202, execution is async
- [ ] Re-run support with `source_run_id` (3 operations)
- [ ] Counting fields populated: `total_in_pack`, `total_applicable`, `executed`, `skipped_reasons`
- [ ] Full integration test with mock HTTP client passes
- [ ] Partial results always persisted on cancel/fail
- [ ] All tests pass, >90% coverage
