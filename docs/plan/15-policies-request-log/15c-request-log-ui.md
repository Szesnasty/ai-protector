# 15c — Request Log UI

| | |
|---|---|
| **Parent** | [Step 15 — Policies & Request Log](SPEC.md) |
| **Estimated time** | 4–6 hours |
| **Depends on** | 15a (Request Log API), Step 05 (Nuxt + Vuetify shell) |

---

## Goal

Replace the placeholder `requests.vue` page with a full **Request Log viewer**: a Vuetify data table with server-side pagination, a filter bar, sortable columns, and expandable rows that reveal full pipeline details (scanner results, output filter actions, node timings, risk flags).

---

## Page Layout

```
┌────────────────────────────────────────────────────────────────────┐
│  Request Log                                                       │
│  Audit trail of all firewall-processed requests                    │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌──── Filter Bar ─────────────────────────────────────────────┐  │
│  │ Decision: [All ▾]  Policy: [All ▾]  Intent: [____]         │  │
│  │ Risk: [0.0 ──●── 1.0]   Search: [____________]  [🗓 Date] │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │ ▼ │ Time       │ Client   │Policy│Intent │Decision│Risk│ms │  │
│  ├───┼────────────┼──────────┼──────┼───────┼────────┼────┼───┤  │
│  │ ► │ 14:23:01   │ agent-1  │balan │chat   │ ALLOW  │0.2 │45 │  │
│  │ ▼ │ 14:22:58   │ anon     │stric │jailbr │ BLOCK  │0.9 │12 │  │
│  │   ├────────────────────────────────────────────────────────┤  │
│  │   │ ┌─ Prompt Preview ──────────────────────────────────┐  │  │
│  │   │ │ "Ignore all previous instructions and tell me..." │  │  │
│  │   │ └──────────────────────────────────────────────────────┘  │
│  │   │ ┌─ Risk Flags ─────┐  ┌─ Scanner Results ──────────┐  │  │
│  │   │ │ denylist_hit: T  │  │ llm_guard:                 │  │  │
│  │   │ │ injection: 0.95  │  │   injection: 0.95          │  │  │
│  │   │ │ custom_rules: 2  │  │ presidio:                  │  │  │
│  │   │ └──────────────────┘  │   entities: 0              │  │  │
│  │   │                       └─────────────────────────────┘  │  │
│  │   │ ┌─ Node Timings ───┐  ┌─ Blocked Reason ───────────┐  │  │
│  │   │ │ parse: 1ms       │  │ Denylist hit: "ignore all  │  │  │
│  │   │ │ intent: 3ms      │  │ previous instructions"     │  │  │
│  │   │ │ rules: 2ms       │  └─────────────────────────────┘  │  │
│  │   │ │ llm_guard: 45ms  │                                   │  │
│  │   │ └──────────────────┘                                   │  │
│  │ ► │ 14:22:55   │ agent-1  │balan │chat   │ ALLOW  │0.1 │38 │  │
│  ├───┴────────────┴──────────┴──────┴───────┴────────┴────┴───┤  │
│  │                  ◄ 1 2 3 ... 15 ►    25 per page ▾         │  │
│  └─────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
```

---

## Components

### `requests/filters.vue` — Filter bar

Props: `modelValue: RequestFilters`

```typescript
interface RequestFilters {
  decision: string | null      // ALLOW | MODIFY | BLOCK
  policy_id: string | null
  intent: string | null
  risk_min: number | null
  risk_max: number | null
  search: string | null
  from: string | null          // ISO date
  to: string | null
}
```

UI elements:
- **Decision** — `v-select` with items: All, ALLOW, MODIFY, BLOCK. Color-coded chips.
- **Policy** — `v-select` populated from `usePolicies()` composable
- **Intent** — `v-text-field` with debounce (300ms)
- **Risk range** — `v-range-slider` (0.0–1.0, step 0.05) with min/max labels
- **Search** — `v-text-field` with `mdi-magnify` icon, debounce (300ms)
- **Date range** — two `v-text-field` type="date" (from / to)
- **Clear all** button when any filter is active

Emits: `update:modelValue` on every change (debounced for text fields)

### `requests/table.vue` — Server-side data table

Props: `filters: RequestFilters`

Uses Vuetify `v-data-table-server`:
- `items-length` bound to API `total`
- `@update:options` triggers API refetch with new `page`, `itemsPerPage`, `sortBy`

Columns:
| Column | Field | Sortable | Format |
|--------|-------|----------|--------|
| (expand toggle) | — | No | `v-btn` icon |
| Time | `created_at` | Yes | `HH:mm:ss` (tooltip: full datetime) |
| Client | `client_id` | Yes | Truncated to 12 chars |
| Policy | `policy_name` | No | Colored chip |
| Intent | `intent` | No | Chip if present, `—` if null |
| Decision | `decision` | Yes | Color chip: green=ALLOW, orange=MODIFY, red=BLOCK |
| Risk | `risk_score` | Yes | Progress bar (0–1) with color |
| Latency | `latency_ms` | Yes | `{N}ms` |
| Tokens | `tokens_in`/`tokens_out` | No | `{in}→{out}` |

Row click / expand toggle → expands detail section.

### `requests/detail-row.vue` — Expandable detail content

Props: `request: RequestDetail`

Lazy-loaded: when a row expands, fetch `GET /v1/requests/{id}` to get full detail (scanner_results, node_timings, etc.).

Sections:

**1. Prompt Preview**
- Full `prompt_preview` text in a `v-code` or pre-formatted block
- Copy button

**2. Risk Flags** (grid of chips)
- Each key-value from `risk_flags` as a colored chip
- Boolean flags: green (false) / red (true)
- Numeric flags: color based on threshold

**3. Scanner Results** (collapsible sections)
- `scanner_results.llm_guard` → scores table
- `scanner_results.presidio` → entities list
- Each scanner as a `v-expansion-panel`

**4. Output Filter Results**
- `output_filter_results` — redaction actions taken
- Show as key-value list

**5. Node Timings** (horizontal bar chart or simple table)
- Each node name + time in ms
- Sorted by execution order
- Total latency at bottom

**6. Blocked Reason**
- Only shown if `decision === 'BLOCK'`
- `blocked_reason` in red alert box

---

## Composable

### `useRequestLog.ts` — Server-side pagination

```typescript
export const useRequestLog = () => {
  const filters = ref<RequestFilters>({ ... })
  const page = ref(1)
  const pageSize = ref(25)
  const sortBy = ref('created_at')
  const sortOrder = ref<'asc' | 'desc'>('desc')

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['requests', filters, page, pageSize, sortBy, sortOrder],
    queryFn: async () => {
      const params = new URLSearchParams()
      params.set('page', String(page.value))
      params.set('page_size', String(pageSize.value))
      params.set('sort', sortBy.value)
      params.set('order', sortOrder.value)
      // append non-null filters
      ...
      const { data } = await api.get(`/v1/requests?${params}`)
      return data
    },
    keepPreviousData: true,  // smooth pagination transitions
  })

  const fetchDetail = async (id: string): Promise<RequestDetail> => {
    const { data } = await api.get(`/v1/requests/${id}`)
    return data
  }

  return { data, isLoading, error, filters, page, pageSize, sortBy, sortOrder, fetchDetail, refetch }
}
```

---

## Type additions (`types/api.ts`)

```typescript
export interface RequestRead {
  id: string
  client_id: string
  policy_id: string
  policy_name: string
  intent: string | null
  prompt_preview: string | null
  decision: 'ALLOW' | 'MODIFY' | 'BLOCK'
  risk_score: number | null
  risk_flags: Record<string, unknown> | null
  latency_ms: number | null
  model_used: string | null
  tokens_in: number | null
  tokens_out: number | null
  blocked_reason: string | null
  response_masked: boolean | null
  created_at: string
}

export interface RequestDetail extends RequestRead {
  scanner_results: Record<string, unknown> | null
  output_filter_results: Record<string, unknown> | null
  node_timings: Record<string, number> | null
  prompt_hash: string | null
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface RequestFilters {
  decision: string | null
  policy_id: string | null
  intent: string | null
  risk_min: number | null
  risk_max: number | null
  search: string | null
  from: string | null
  to: string | null
}
```

---

## File Tree

```
apps/frontend/app/
├── pages/
│   └── requests.vue                     # REWRITE
├── components/
│   └── requests/
│       ├── table.vue                    # NEW — v-data-table-server
│       ├── filters.vue                  # NEW — filter bar
│       └── detail-row.vue              # NEW — expanded row content
├── composables/
│   └── useRequestLog.ts                # NEW
└── types/
    └── api.ts                           # MODIFIED — add Request types
```

---

## UX Details

### Decision colors
- `ALLOW` → `color="success"` (green)
- `MODIFY` → `color="warning"` (orange)
- `BLOCK` → `color="error"` (red)

### Risk score progress bar
- 0.0–0.3 → green
- 0.3–0.6 → orange
- 0.6–1.0 → red

### Loading states
- Skeleton rows while fetching
- Spinner on detail row loading
- Disabled pagination while loading

### Empty states
- No requests yet → illustration + "No requests recorded. Try the Playground to generate some."
- No results for filters → "No requests match your filters." + Clear filters button

### Auto-refresh
- Optional toggle: "Auto-refresh every 10s" checkbox in header
- Uses `refetchInterval` from Vue Query

---

## Definition of Done

### UI verification
- [ ] Request log shows paginated table with real data from API
- [ ] Server-side pagination: page controls work, total count is correct
- [ ] Sorting: click column header → re-sorts via API
- [ ] Filter: decision → shows only BLOCK/ALLOW/MODIFY rows
- [ ] Filter: search → matches prompt preview text
- [ ] Filter: date range → time-bounded results
- [ ] Clear filters → resets all to default
- [ ] Expand row → fetches detail → shows scanner results, node timings, risk flags
- [ ] Blocked rows show blocked reason in red
- [ ] Proper loading, empty, and error states

### Checklist
- [ ] `requests/table.vue` — `v-data-table-server` with all columns
- [ ] `requests/filters.vue` — filter bar with debounced inputs
- [ ] `requests/detail-row.vue` — lazy-loaded detail sections
- [ ] `useRequestLog.ts` — server-side pagination + detail fetch
- [ ] `RequestRead`, `RequestDetail`, `PaginatedResponse`, `RequestFilters` types
- [ ] `requests.vue` page ties all components together
- [ ] Color-coded decision chips, risk progress bars
- [ ] Auto-refresh toggle (optional)

---

| **Prev** | **Next** |
|---|---|
| [15b — Policies CRUD UI](15b-policies-ui.md) | — |
