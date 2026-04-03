# 15a — Request Log API

| | |
|---|---|
| **Parent** | [Step 15 — Policies & Request Log](SPEC.md) |
| **Estimated time** | 3–4 hours |
| **Depends on** | Step 09 (Request model, LoggingNode writes audit rows) |

---

## Goal

Build a REST API for querying the `requests` audit table with server-side pagination, flexible sorting, full-text search, and multi-parameter filtering. The `Request` model and `log_request_from_state()` already populate the table — this sub-step only adds **read endpoints**.

---

## Pydantic Schemas

```python
# apps/proxy-service/src/schemas/request.py  (NEW)

class RequestRead(BaseModel):
    """Lightweight schema for list view (excludes large JSONB fields)."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: str
    policy_id: uuid.UUID
    policy_name: str              # joined from policy.name
    intent: str | None
    prompt_preview: str | None
    decision: str
    risk_score: float | None
    risk_flags: dict | None
    latency_ms: int | None
    model_used: str | None
    tokens_in: int | None
    tokens_out: int | None
    blocked_reason: str | None
    response_masked: bool | None
    created_at: datetime

class RequestDetail(RequestRead):
    """Full detail schema — includes heavy JSONB columns."""
    scanner_results: dict | None
    output_filter_results: dict | None
    node_timings: dict | None
    prompt_hash: str | None

class PaginatedResponse(BaseModel, Generic[T]):
    """Generic wrapper for paginated list responses."""
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int                    # = ceil(total / page_size)
```

---

## API Endpoints

### `GET /v1/requests` — Paginated list

Query parameters:

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `page` | int | 1 | Page number (1-indexed) |
| `page_size` | int | 25 | Items per page (max 100) |
| `sort` | str | `created_at` | Column to sort by |
| `order` | str | `desc` | `asc` or `desc` |
| `decision` | str? | — | Filter: `ALLOW`, `MODIFY`, `BLOCK` |
| `intent` | str? | — | Filter: exact match on intent field |
| `policy_id` | UUID? | — | Filter by policy UUID |
| `client_id` | str? | — | Filter: exact match |
| `risk_min` | float? | — | Filter: `risk_score >= risk_min` |
| `risk_max` | float? | — | Filter: `risk_score <= risk_max` |
| `search` | str? | — | ILIKE search in `prompt_preview` |
| `from` | datetime? | — | Filter: `created_at >= from` |
| `to` | datetime? | — | Filter: `created_at <= to` |

Response: `PaginatedResponse[RequestRead]`

Implementation notes:
- Use `select(Request).join(Policy)` to get `policy_name`
- Count query: `select(func.count()).select_from(stmt.subquery())` for total
- Allowed sort columns whitelist: `created_at`, `decision`, `risk_score`, `latency_ms`, `client_id`
- Clamp `page_size` to `[1, 100]`
- Return 200 with empty `items: []` if no results (never 404)

### `GET /v1/requests/{request_id}` — Full detail

Response: `RequestDetail`

Returns 404 if not found.

---

## Router Implementation

```python
# apps/proxy-service/src/routers/requests.py  (NEW)

router = APIRouter(tags=["requests"])

ALLOWED_SORT_COLUMNS = {
    "created_at": Request.created_at,
    "decision": Request.decision,
    "risk_score": Request.risk_score,
    "latency_ms": Request.latency_ms,
    "client_id": Request.client_id,
}

@router.get("/requests", response_model=PaginatedResponse[RequestRead])
async def list_requests(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    sort: str = Query("created_at"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    decision: str | None = Query(None),
    intent: str | None = Query(None),
    policy_id: uuid.UUID | None = Query(None),
    client_id: str | None = Query(None),
    risk_min: float | None = Query(None, ge=0, le=1),
    risk_max: float | None = Query(None, ge=0, le=1),
    search: str | None = Query(None),
    date_from: datetime | None = Query(None, alias="from"),
    date_to: datetime | None = Query(None, alias="to"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    # Build base query
    stmt = select(Request).join(Policy)

    # Apply filters
    if decision:
        stmt = stmt.where(Request.decision == decision.upper())
    if intent:
        stmt = stmt.where(Request.intent == intent)
    if policy_id:
        stmt = stmt.where(Request.policy_id == policy_id)
    if client_id:
        stmt = stmt.where(Request.client_id == client_id)
    if risk_min is not None:
        stmt = stmt.where(Request.risk_score >= risk_min)
    if risk_max is not None:
        stmt = stmt.where(Request.risk_score <= risk_max)
    if search:
        stmt = stmt.where(Request.prompt_preview.ilike(f"%{search}%"))
    if date_from:
        stmt = stmt.where(Request.created_at >= date_from)
    if date_to:
        stmt = stmt.where(Request.created_at <= date_to)

    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar()

    # Sort
    sort_col = ALLOWED_SORT_COLUMNS.get(sort, Request.created_at)
    stmt = stmt.order_by(sort_col.desc() if order == "desc" else sort_col.asc())

    # Paginate
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(stmt)
    items = result.scalars().all()

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, -(-total // page_size)),  # ceil division
    }

@router.get("/requests/{request_id}", response_model=RequestDetail)
async def get_request(
    request_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> RequestDetail:
    row = await db.get(Request, request_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Request not found")
    return row
```

Register in `main.py`:
```python
from src.routers.requests import router as requests_router
app.include_router(requests_router, prefix="/v1")
```

---

## File Tree

```
apps/proxy-service/
├── src/
│   ├── routers/
│   │   └── requests.py            # NEW
│   ├── schemas/
│   │   ├── __init__.py            # MODIFIED — export new schemas
│   │   └── request.py             # NEW
│   └── main.py                    # MODIFIED — register router
└── tests/
    └── test_request_log.py        # NEW
```

---

## Tests

```python
# tests/test_request_log.py

# test_list_requests_empty — no rows → { items: [], total: 0, page: 1, pages: 1 }
# test_list_requests_pagination — insert 30 rows, page_size=10 → 3 pages, correct items
# test_list_requests_filter_decision — filter BLOCK → only blocked requests
# test_list_requests_filter_intent — filter jailbreak → correct subset
# test_list_requests_filter_date_range — from/to → time-bounded results
# test_list_requests_search — search="hack" → ILIKE match on prompt_preview
# test_list_requests_sort_risk_score — sort=risk_score&order=desc → descending
# test_list_requests_invalid_sort — sort=nonexistent → falls back to created_at
# test_get_request_detail — full row with scanner_results, node_timings
# test_get_request_not_found — 404
```

---

## Definition of Done

### Automated
```bash
cd apps/proxy-service && python -m pytest tests/test_request_log.py -v
```

### Smoke tests
```bash
# Paginated list
curl -s 'http://localhost:8000/v1/requests?page=1&page_size=5' | python -m json.tool
# → { items: [...], total: N, page: 1, page_size: 5, pages: M }

# Filter by decision
curl -s 'http://localhost:8000/v1/requests?decision=BLOCK&page_size=3'

# Search
curl -s 'http://localhost:8000/v1/requests?search=hack'

# Detail
curl -s 'http://localhost:8000/v1/requests/{ID}' | python -m json.tool
# → all JSONB fields present
```

### Checklist
- [ ] `GET /v1/requests` with pagination (page, page_size, total, pages)
- [ ] Sorting by 5 columns (created_at, decision, risk_score, latency_ms, client_id)
- [ ] Filter: decision, intent, policy_id, client_id, risk_min, risk_max
- [ ] Filter: search (ILIKE on prompt_preview)
- [ ] Filter: date range (from, to)
- [ ] `GET /v1/requests/{id}` — full detail (scanner_results, node_timings, output_filter_results)
- [ ] Schemas: `RequestRead` (lightweight), `RequestDetail` (full), `PaginatedResponse`
- [ ] Router registered in `main.py` under `/v1`
- [ ] `policy_name` field joined from policies table
- [ ] Tests cover pagination, all filters, sorting, detail, 404

---

| **Prev** | **Next** |
|---|---|
| — | [15b — Policies CRUD UI](15b-policies-ui.md) |
