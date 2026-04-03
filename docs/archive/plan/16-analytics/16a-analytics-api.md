# 16a — Analytics API

| | |
|---|---|
| **Parent** | [Step 16 — Frontend: Analytics](SPEC.md) |
| **Estimated time** | 3–4 hours |
| **Depends on** | Step 09 (requests table with audit data), Step 15a (requests router registered) |

---

## Goal

Build 5 aggregation endpoints under `/v1/analytics` that power the analytics dashboard. All endpoints query the `requests` table with a configurable time window. Pure SQL aggregations — no materialized views needed at MVP scale.

---

## Pydantic Schemas

```python
# apps/proxy-service/src/schemas/analytics.py  (NEW)

class AnalyticsSummary(BaseModel):
    """KPI summary for the dashboard header."""
    total_requests: int
    blocked: int
    modified: int
    allowed: int
    block_rate: float              # blocked / total (0.0–1.0)
    avg_risk: float                # average risk_score
    avg_latency_ms: float          # average latency_ms
    top_intent: str | None         # most frequent intent

class TimelineBucket(BaseModel):
    """One time bucket in the timeline chart."""
    time: datetime                 # bucket start time
    total: int
    blocked: int
    modified: int
    allowed: int

class PolicyStats(BaseModel):
    """Per-policy aggregation."""
    policy_id: uuid.UUID
    policy_name: str
    total: int
    blocked: int
    modified: int
    allowed: int
    block_rate: float
    avg_risk: float

class RiskFlagCount(BaseModel):
    """One risk flag with occurrence count."""
    flag: str
    count: int
    pct: float                     # count / total_requests

class IntentCount(BaseModel):
    """One intent with occurrence count."""
    intent: str
    count: int
    pct: float
```

---

## API Endpoints

### 1. `GET /v1/analytics/summary`

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `hours` | int | 24 | Lookback window in hours (1–720) |

Response: `AnalyticsSummary`

SQL sketch:
```sql
SELECT
  count(*) AS total_requests,
  count(*) FILTER (WHERE decision = 'BLOCK') AS blocked,
  count(*) FILTER (WHERE decision = 'MODIFY') AS modified,
  count(*) FILTER (WHERE decision = 'ALLOW') AS allowed,
  avg(risk_score) AS avg_risk,
  avg(latency_ms) AS avg_latency_ms
FROM requests
WHERE created_at >= now() - interval '{hours} hours';

-- top_intent: separate query
SELECT intent, count(*) AS cnt
FROM requests
WHERE created_at >= now() - interval '{hours} hours'
  AND intent IS NOT NULL
GROUP BY intent
ORDER BY cnt DESC
LIMIT 1;
```

### 2. `GET /v1/analytics/timeline`

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `hours` | int | 24 | Lookback window |
| `bucket` | str | `auto` | Bucket size: `5m`, `15m`, `1h`, `6h`, `1d`, or `auto` |

Auto-bucket logic:
- hours ≤ 2 → `5m`
- hours ≤ 12 → `15m`
- hours ≤ 72 → `1h`
- hours ≤ 336 → `6h`
- else → `1d`

Response: `list[TimelineBucket]`

SQL sketch (PostgreSQL `date_trunc` + `generate_series` for zero-filled buckets):
```sql
WITH buckets AS (
  SELECT generate_series(
    date_trunc('hour', now() - interval '{hours} hours'),
    now(),
    interval '{bucket}'
  ) AS bucket_time
),
counts AS (
  SELECT
    date_trunc('{bucket_trunc}', created_at) AS bucket_time,
    count(*) AS total,
    count(*) FILTER (WHERE decision = 'BLOCK') AS blocked,
    count(*) FILTER (WHERE decision = 'MODIFY') AS modified,
    count(*) FILTER (WHERE decision = 'ALLOW') AS allowed
  FROM requests
  WHERE created_at >= now() - interval '{hours} hours'
  GROUP BY 1
)
SELECT
  b.bucket_time AS time,
  COALESCE(c.total, 0) AS total,
  COALESCE(c.blocked, 0) AS blocked,
  COALESCE(c.modified, 0) AS modified,
  COALESCE(c.allowed, 0) AS allowed
FROM buckets b
LEFT JOIN counts c ON b.bucket_time = c.bucket_time
ORDER BY b.bucket_time;
```

Implementation note: use SQLAlchemy `text()` for the generate_series CTE since it's PostgreSQL-specific. Alternatively, use `func.date_trunc` with `func.generate_series`.

### 3. `GET /v1/analytics/by-policy`

| Param | Type | Default |
|-------|------|---------|
| `hours` | int | 24 |

Response: `list[PolicyStats]`

SQL: GROUP BY `policy_id` with JOIN on policies for name. Only include active policies.

### 4. `GET /v1/analytics/top-flags`

| Param | Type | Default |
|-------|------|---------|
| `hours` | int | 24 |
| `limit` | int | 10 |

Response: `list[RiskFlagCount]`

Implementation:
- `risk_flags` is JSONB `{"denylist_hit": true, "injection": 0.95, "pii_detected": true, ...}`
- Use `jsonb_each_text(risk_flags)` to unnest keys
- Filter: only keys where value is truthy (`value::text NOT IN ('false', '0', '0.0', 'null', '')`)
- GROUP BY key, COUNT, ORDER BY count DESC, LIMIT

SQL sketch:
```sql
SELECT
  kv.key AS flag,
  count(*) AS cnt
FROM requests,
  LATERAL jsonb_each_text(risk_flags) AS kv
WHERE created_at >= now() - interval '{hours} hours'
  AND kv.value NOT IN ('false', '0', '0.0', 'null', '')
GROUP BY kv.key
ORDER BY cnt DESC
LIMIT {limit};
```

### 5. `GET /v1/analytics/intents`

| Param | Type | Default |
|-------|------|---------|
| `hours` | int | 24 |

Response: `list[IntentCount]`

SQL: GROUP BY intent, count, filter out NULLs, order by count DESC.

---

## Router Implementation

```python
# apps/proxy-service/src/routers/analytics.py  (NEW)

router = APIRouter(tags=["analytics"])

def _cutoff(hours: int) -> datetime:
    """Calculate the cutoff timestamp for the lookback window."""
    return datetime.now(timezone.utc) - timedelta(hours=hours)

def _auto_bucket(hours: int) -> str:
    """Determine bucket interval string for timeline."""
    if hours <= 2:    return "5 minutes"
    if hours <= 12:   return "15 minutes"
    if hours <= 72:   return "1 hour"
    if hours <= 336:  return "6 hours"
    return "1 day"

BUCKET_MAP = {
    "5m": "5 minutes",
    "15m": "15 minutes",
    "1h": "1 hour",
    "6h": "6 hours",
    "1d": "1 day",
}

@router.get("/analytics/summary", response_model=AnalyticsSummary)
async def get_summary(
    hours: int = Query(24, ge=1, le=720),
    db: AsyncSession = Depends(get_db),
) -> dict: ...

@router.get("/analytics/timeline", response_model=list[TimelineBucket])
async def get_timeline(
    hours: int = Query(24, ge=1, le=720),
    bucket: str = Query("auto"),
    db: AsyncSession = Depends(get_db),
) -> list: ...

@router.get("/analytics/by-policy", response_model=list[PolicyStats])
async def get_by_policy(
    hours: int = Query(24, ge=1, le=720),
    db: AsyncSession = Depends(get_db),
) -> list: ...

@router.get("/analytics/top-flags", response_model=list[RiskFlagCount])
async def get_top_flags(
    hours: int = Query(24, ge=1, le=720),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> list: ...

@router.get("/analytics/intents", response_model=list[IntentCount])
async def get_intents(
    hours: int = Query(24, ge=1, le=720),
    db: AsyncSession = Depends(get_db),
) -> list: ...
```

Register in `main.py`:
```python
from src.routers.analytics import router as analytics_router
app.include_router(analytics_router, prefix="/v1")
```

---

## File Tree

```
apps/proxy-service/
├── src/
│   ├── routers/
│   │   └── analytics.py            # NEW
│   ├── schemas/
│   │   ├── __init__.py             # MODIFIED
│   │   └── analytics.py            # NEW
│   └── main.py                     # MODIFIED — register router
└── tests/
    └── test_analytics.py           # NEW
```

---

## Tests

```python
# tests/test_analytics.py

# Fixture: seed 50 requests with varied decisions, intents, risk_flags, policies, timestamps

# test_summary_empty — no requests → total=0, block_rate=0, avg_risk=0
# test_summary_with_data — seed data → correct counts, block_rate, avg_risk
# test_summary_time_window — requests outside window excluded
# test_timeline_buckets — returns correct number of buckets, zero-filled
# test_timeline_auto_bucket — hours=2 → 5m buckets, hours=24 → 1h buckets
# test_by_policy — per-policy stats, all active policies included
# test_top_flags — ranked by count, correct percentages
# test_top_flags_limit — limit=3 → only top 3
# test_intents — grouped by intent, sorted desc
# test_intents_excludes_null — null intents not in results
```

---

## Definition of Done

### Automated
```bash
cd apps/proxy-service && python -m pytest tests/test_analytics.py -v
```

### Smoke tests
```bash
# Summary
curl -s 'http://localhost:8000/v1/analytics/summary?hours=24' | python -m json.tool
# → { total_requests: N, blocked: M, block_rate: 0.XX, ... }

# Timeline (auto bucket)
curl -s 'http://localhost:8000/v1/analytics/timeline?hours=24' | python -m json.tool
# → array of { time, total, blocked, modified, allowed }

# Timeline (explicit bucket)
curl -s 'http://localhost:8000/v1/analytics/timeline?hours=2&bucket=5m' | python -m json.tool

# By policy
curl -s 'http://localhost:8000/v1/analytics/by-policy?hours=24' | python -m json.tool

# Top flags
curl -s 'http://localhost:8000/v1/analytics/top-flags?hours=24&limit=5' | python -m json.tool

# Intents
curl -s 'http://localhost:8000/v1/analytics/intents?hours=24' | python -m json.tool
```

### Checklist
- [ ] `GET /v1/analytics/summary` — KPI aggregation with block_rate, avg_risk, avg_latency, top_intent
- [ ] `GET /v1/analytics/timeline` — time-bucketed counts with auto-bucket logic + zero-fill
- [ ] `GET /v1/analytics/by-policy` — per-policy stats with block_rate and avg_risk
- [ ] `GET /v1/analytics/top-flags` — JSONB key extraction, truthy filter, ranked
- [ ] `GET /v1/analytics/intents` — intent distribution with percentages
- [ ] All endpoints accept `hours` parameter (1–720)
- [ ] Schemas: `AnalyticsSummary`, `TimelineBucket`, `PolicyStats`, `RiskFlagCount`, `IntentCount`
- [ ] Router registered in `main.py` under `/v1`
- [ ] Tests cover all endpoints + edge cases (empty data, time windows)

---

| **Prev** | **Next** |
|---|---|
| — | [16b — KPI Cards & Timeline](16b-kpi-timeline.md) |
