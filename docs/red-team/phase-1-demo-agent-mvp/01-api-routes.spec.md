# 01 — API Routes

> **Layer:** Backend (FastAPI)
> **Phase:** 1 (Demo Agent) — MVP
> **Depends on:** Phase 0 modules (Run Engine, Persistence, Progress Emitter)

## Scope

Thin FastAPI routes that expose the benchmark engine via HTTP. No business logic in routes — delegate to engine modules.

## Implementation Steps

### Step 1: `POST /v1/benchmark/runs` — Create & start a run

- Request body: `{ target_type, target_config, pack, policy? }`
- Validate input (Pydantic request model)
- Call Run Engine → `create_run()` + `start_run()` (async background task)
- Return: `{ id, status: "running", pack, total }`
- HTTP 409 if same target already has a running benchmark

### Step 2: `GET /v1/benchmark/runs` — List runs

- Query params: `limit`, `offset`, `target_type?`
- Return paginated list: `[{ id, target_type, pack, status, score, started_at }]`

### Step 3: `GET /v1/benchmark/runs/:id` — Run details + summary

- Return full run record including scores, counts, confidence badge
- 404 if not found

### Step 4: `GET /v1/benchmark/runs/:id/scenarios` — Scenario results

- Query params: `limit`, `offset`, `passed?`, `category?`
- Return paginated scenario results
- Supports filtering by pass/fail and category

### Step 5: `GET /v1/benchmark/runs/:id/scenarios/:sid` — Single scenario detail

- Return full scenario result including prompt, expected, actual, detector_detail, pipeline_result
- 404 if not found

### Step 6: `DELETE /v1/benchmark/runs/:id` — Cancel or delete

- If status = `running` → cancel run (transition to `cancelled`)
- If status = `completed`/`cancelled`/`failed` → delete run + results
- Return 204

### Step 7: `GET /v1/benchmark/runs/:id/progress` — SSE stream

- Return SSE stream from Progress Emitter
- Content-Type: `text/event-stream`
- Stream events until run completes/fails/cancels
- Client reconnection: accept `Last-Event-ID` header

### Step 8: `GET /v1/benchmark/packs` — Available attack packs

- Return list: `[{ name, version, description, scenario_count, applicable_to }]`
- Read from Pack Loader

### Step 9: `GET /v1/benchmark/compare?a=:id&b=:id` — Diff two runs

- Return: score delta, category breakdown comparison, fixed/new failures
- Validate both runs exist
- Warning if different targets or packs

## Tests

| Test | What it verifies |
|------|-----------------|
| `test_create_run_returns_201` | POST with valid config → 201 + run ID |
| `test_create_run_409_concurrent` | Second run on same target → 409 |
| `test_list_runs_paginated` | Returns correct page of runs |
| `test_get_run_details` | Returns all run fields including scores |
| `test_get_run_404` | Non-existent run → 404 |
| `test_list_scenarios_by_run` | Returns results for specific run |
| `test_get_scenario_detail` | Returns full scenario with prompt + detector output |
| `test_cancel_running_run` | DELETE on running → 204 + status=cancelled |
| `test_delete_completed_run` | DELETE on completed → 204 + data removed |
| `test_sse_stream_sends_events` | SSE endpoint streams scenario events |
| `test_list_packs` | Returns available packs with metadata |
| `test_compare_two_runs` | Returns delta, category diff, fixed failures |
| `test_compare_different_packs_warning` | Different packs → warning in response |

## Definition of Done

- [ ] All 9 endpoints implemented and returning correct responses
- [ ] Request validation via Pydantic models
- [ ] SSE stream works end-to-end (subscribe → receive events → stream ends)
- [ ] All routes delegate to engine modules (no business logic in routes)
- [ ] All tests pass with test database
- [ ] OpenAPI schema auto-generated and correct
