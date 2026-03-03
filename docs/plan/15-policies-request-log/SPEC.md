# Step 15 — Frontend: Policies & Request Log

| | |
|---|---|
| **Phase** | Dashboard & Data |
| **Estimated time** | 10–14 hours |
| **Prev** | [Step 14 — Custom Security Rules](../14-custom-security-rules/SPEC.md) |
| **Next** | [Step 16 — Frontend: Analytics](../16-analytics/SPEC.md) |
| **Depends on** | Step 03 (Policy model), Step 08 (policies CRUD API), Step 09 (request logging) |
| **Master plan** | [MVP-PLAN.md](../MVP-PLAN.md) |

---

## Goal

Build a **Policies management UI** and a **Request Log viewer** — the two core operational screens for day-to-day monitoring and configuration. The backend already has the policies CRUD API and the `requests` table filled by the pipeline's `LoggingNode`. This step adds what's missing on the backend (request log list/detail endpoints with server-side pagination) and builds both frontend pages.

After this step:
- Operators manage all 4 policy levels via a rich config editor (thresholds, enabled nodes)
- Operators browse all firewall audit logs with server-side pagination, column sorting, and filters
- Expandable rows reveal full pipeline details: scanner results, output filter, node timings, risk flags
- All data is loaded on-demand with proper loading/error states

---

## Sub-steps

| # | Sub-step | Scope | Est. |
|---|----------|-------|------|
| a | [15a — Request Log API](15a-request-log-api.md) | `GET /v1/requests` with pagination, sorting, filters; `GET /v1/requests/{id}` detail | 3–4 h |
| b | [15b — Policies CRUD UI](15b-policies-ui.md) | Policies page: card grid, create/edit dialog, config editor (thresholds + nodes), delete | 3–4 h |
| c | [15c — Request Log UI](15c-request-log-ui.md) | Request log page: data table, server-side pagination, filters, expandable detail rows | 4–6 h |

---

## Architecture

### What exists already

| Layer | Component | Status |
|-------|-----------|--------|
| Backend model | `Request` (ORM) | ✅ 15+ columns (decision, risk_score, risk_flags, scanner_results, node_timings, etc.) |
| Backend model | `Policy` (ORM) | ✅ name, description, config (JSONB), is_active, version |
| Backend API | `GET/POST/PATCH/DELETE /v1/policies` | ✅ Full CRUD with config validation |
| Backend API | Request list/detail endpoints | ❌ **Missing — need to create** |
| Backend | `log_request_from_state()` | ✅ Writes audit rows from pipeline state |
| Frontend | `policies.vue` page | ❌ Placeholder ("Coming in Step 14") |
| Frontend | `requests.vue` page | ❌ Placeholder ("Coming in Step 14") |
| Frontend | `usePolicies.ts` composable | ✅ Basic list query via Vue Query |
| Frontend types | `Policy`, `ApiError` | ✅ In `types/api.ts` |

### Data flow

```
Pipeline → LoggingNode → requests table → Request Log API → Frontend table
                                              │
Policies table ←→ Policies CRUD API ←→ Frontend policy cards
```

### Request Log API design

```
GET  /v1/requests
  ?page=1&page_size=25           (pagination)
  &sort=created_at&order=desc    (sorting)
  &decision=BLOCK                (filter: ALLOW|MODIFY|BLOCK)
  &intent=jailbreak              (filter)
  &policy_id=uuid                (filter)
  &client_id=agent-1             (filter)
  &risk_min=0.5                  (filter: min risk score)
  &search=hack                   (search in prompt_preview)
  &from=2026-01-01&to=2026-03-01 (date range)

→ { items: RequestRead[], total: int, page: int, page_size: int, pages: int }

GET  /v1/requests/{id}
→ RequestDetail (full row with all JSONB fields)
```

---

## File Tree (all changes)

```
apps/proxy-service/
├── src/
│   ├── routers/
│   │   └── requests.py              # NEW — paginated list + detail
│   ├── schemas/
│   │   └── request.py               # NEW — RequestRead, RequestDetail, PaginatedResponse
│   └── main.py                      # MODIFIED — register requests router
└── tests/
    └── test_request_log.py          # NEW

apps/frontend/
├── app/
│   ├── pages/
│   │   ├── policies.vue             # REWRITE — full CRUD UI
│   │   └── requests.vue             # REWRITE — data table with pagination
│   ├── components/
│   │   ├── policies/
│   │   │   ├── card.vue             # NEW — policy summary card
│   │   │   ├── dialog.vue           # NEW — create/edit dialog
│   │   │   └── config-editor.vue    # NEW — thresholds + nodes editor
│   │   └── requests/
│   │       ├── table.vue            # NEW — data table with pagination
│   │       ├── filters.vue          # NEW — filter bar (decision, intent, date)
│   │       └── detail-row.vue       # NEW — expandable detail content
│   ├── composables/
│   │   ├── usePolicies.ts           # MODIFIED — add mutations (create, update, delete)
│   │   └── useRequestLog.ts         # NEW — server-side pagination composable
│   └── types/
│       └── api.ts                   # MODIFIED — add Request types
```

---

## Definition of Done

### Automated
```bash
cd apps/proxy-service && python -m pytest tests/test_request_log.py -v
# Pagination, filters, sorting, detail — all pass
```

### Smoke tests
```bash
# Request log with pagination
curl -s 'http://localhost:8000/v1/requests?page=1&page_size=5' | python -m json.tool
# → { items: [...], total: N, page: 1, page_size: 5, pages: M }

# Filter by decision
curl -s 'http://localhost:8000/v1/requests?decision=BLOCK' | python -m json.tool

# Get detail
curl -s 'http://localhost:8000/v1/requests/{ID}' | python -m json.tool
# → full row with scanner_results, node_timings, etc.
```

### UI verification
- Policies page: 4 policy cards → click edit → change threshold → save → version increments
- Request log: paginated table → filter by BLOCK → see only blocked requests → expand row → see scanner details

### Checklist
- [ ] Request log API with server-side pagination, sorting, 6+ filter params
- [ ] Request detail endpoint returns full audit row
- [ ] Policies page: card grid showing all policies with status indicators
- [ ] Policy create/edit dialog with config editor (threshold sliders, node toggles)
- [ ] Policy delete (soft-delete) for non-builtin policies
- [ ] Request log page: data table with server-side pagination controls
- [ ] Request log: filter bar (decision, intent, policy, date range, search)
- [ ] Request log: expandable rows with scanner results, risk flags, node timings
- [ ] Loading states, error handling, empty states for both pages
- [ ] Existing tests still pass

---

| **Prev** | **Next** |
|---|---|
| [Step 14 — Custom Security Rules](../14-custom-security-rules/SPEC.md) | [Step 16 — Frontend: Analytics](../16-analytics/SPEC.md) |
