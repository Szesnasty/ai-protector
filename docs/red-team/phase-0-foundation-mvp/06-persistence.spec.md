# 06 — Persistence

> **Module:** `red-team/persistence/`
> **Phase:** 0 (Foundation) — MVP
> **Depends on:** Scenario Schema (`red-team/schemas/`)

## Scope

DB models (SQLAlchemy) and a thin repository layer for `BenchmarkRun` and `BenchmarkScenarioResult`. No business logic — just CRUD + queries.

## Implementation Steps

### Step 1: Define `BenchmarkRun` DB model

All fields from the spec data model:
- `id` (UUID, PK)
- `target_type`, `target_config` (JSON), `pack`, `pack_version`, `policy`
- `status` (enum: created | running | completed | cancelled | failed)
- `score`, `score_simple`, `score_weighted` (nullable int)
- `confidence` (enum: high | medium)
- `total`, `passed`, `failed`, `skipped`, `skipped_mutating`, `false_positives`
- `started_at`, `completed_at` (datetime)
- `created_at`, `updated_at` (timestamps)

### Step 2: Define `BenchmarkScenarioResult` DB model

All fields from the spec:
- `id` (UUID, PK)
- `run_id` (FK → BenchmarkRun)
- `scenario_id`, `category`, `severity`, `mutating`, `applicable_to`
- `prompt` (text)
- `expected`, `actual` (enum or string)
- `passed` (nullable bool — null if skipped)
- `skipped` (bool), `skipped_reason` (enum or null)
- `detector_type`, `detector_detail` (JSON)
- `latency_ms` (nullable int)
- `pipeline_result` (JSON, nullable)
- `raw_response_retained_until` (datetime, nullable) — retention tracking

### Step 3: Create Alembic migration

- Add both tables with proper indexes:
  - Index on `BenchmarkRun.status` (for concurrency guard: find running runs)
  - Index on `BenchmarkRun.target_type` + `target_config->endpoint_url` (for "same target" detection)
  - Index on `BenchmarkScenarioResult.run_id` (FK, partition results by run)
  - Index on `BenchmarkScenarioResult.raw_response_retained_until` (for cleanup job)

### Step 4: Implement repository layer

```python
class BenchmarkRunRepository:
    async def create(self, run: BenchmarkRun) → BenchmarkRun
    async def get(self, run_id: UUID) → BenchmarkRun | None
    async def list(self, limit, offset, target_type?) → list[BenchmarkRun]
    async def update_status(self, run_id, status, scores?) → None
    async def find_running_for_target(self, target_config) → BenchmarkRun | None
    async def delete(self, run_id) → None

class BenchmarkScenarioResultRepository:
    async def create(self, result: BenchmarkScenarioResult) → None
    async def create_batch(self, results: list[BenchmarkScenarioResult]) → None
    async def list_by_run(self, run_id, limit?, offset?) → list[BenchmarkScenarioResult]
    async def get_by_scenario(self, run_id, scenario_id) → BenchmarkScenarioResult | None
    async def count_by_run(self, run_id) → RunCounts  # passed, failed, skipped
```

### Step 5: Implement retention cleanup

```python
async def purge_expired_responses():
    """Null out raw response data where retained_until < now()"""
    # Sets pipeline_result = NULL, clears verbose payload fields
    # Keeps: passed, actual, detector_type, detector_detail, latency_ms
```

- Can be called by a cron job / Celery task
- Respects `BENCHMARK_RESPONSE_RETENTION_DAYS` config

## Tests

| Test | What it verifies |
|------|-----------------|
| `test_create_run` | Run record persists with correct fields |
| `test_get_run` | Retrieve run by ID |
| `test_update_status` | Status transitions persist |
| `test_find_running_for_target` | Finds active run for same target, returns None otherwise |
| `test_create_scenario_result` | Single result persists |
| `test_create_batch_results` | Batch insert works |
| `test_list_by_run` | Returns results for a specific run, not others |
| `test_count_by_run` | Returns correct passed/failed/skipped counts |
| `test_purge_expired` | Results past retention → pipeline_result nulled |
| `test_purge_preserves_metadata` | Purged results still have passed, detector_type, latency |
| `test_retained_until_set_on_create` | New results have correct retention timestamp |
| `test_migration_applies_cleanly` | Alembic migration up + down works |

## Definition of Done

- [ ] Both DB models created with all spec fields
- [ ] `raw_response_retained_until` column on `BenchmarkScenarioResult`
- [ ] Alembic migration with proper indexes
- [ ] Repository layer with all CRUD methods
- [ ] Retention cleanup function implemented
- [ ] All tests pass with a test database (SQLite or PostgreSQL)
- [ ] No business logic in repository — pure data access
