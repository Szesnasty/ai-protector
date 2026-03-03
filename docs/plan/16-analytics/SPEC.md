# Step 16 — Frontend: Analytics

| | |
|---|---|
| **Phase** | Dashboard & Data |
| **Estimated time** | 10–14 hours |
| **Prev** | [Step 15 — Policies & Request Log](../15-policies-request-log/SPEC.md) |
| **Next** | [Step 17 — MLJudge & Advanced Scanners](../17-advanced-scanners/SPEC.md) |
| **Depends on** | Step 15 (request log API, populated requests table), Step 08 (policies) |
| **Master plan** | [MVP-PLAN.md](../MVP-PLAN.md) |

---

## Goal

Build a **real-time analytics dashboard** that gives operators instant visibility into firewall health and threat landscape. The dashboard shows KPI summary cards, a time-series chart of request volume + block rate, and breakdown panels for top risk flags, intent distribution, and per-policy block rates.

After this step:
- Operators see at-a-glance KPIs: total requests, block rate, average risk, avg latency
- Timeline chart shows request volume trends over configurable time windows (1h, 24h, 7d, 30d)
- Block rate breakdown by policy reveals which policies are most restrictive
- Top risk flags ranking shows the most common threat types
- Intent distribution pie/donut chart shows traffic classification
- All data auto-refreshes and responds to time-range selection

---

## Sub-steps

| # | Sub-step | Scope | Est. |
|---|----------|-------|------|
| a | [16a — Analytics API](16a-analytics-api.md) | 4 aggregation endpoints: summary, timeline, by-policy, top-flags, intent distribution | 3–4 h |
| b | [16b — KPI Cards & Timeline](16b-kpi-timeline.md) | Summary KPI cards, time-series area chart, time range selector | 3–4 h |
| c | [16c — Breakdown Panels](16c-breakdowns.md) | Block rate by policy bar chart, top risk flags ranked list, intent donut chart | 4–6 h |

---

## Architecture

### Analytics API design

All endpoints live under `/v1/analytics` and accept a time range:

```
GET /v1/analytics/summary?hours=24
→ { total_requests, blocked, modified, allowed, block_rate, avg_risk, avg_latency_ms, top_intent }

GET /v1/analytics/timeline?hours=24&bucket=1h
→ [ { time: "2026-03-03T14:00:00Z", total: 42, blocked: 5, allowed: 35, modified: 2 }, ... ]

GET /v1/analytics/by-policy?hours=24
→ [ { policy_name: "balanced", total: 100, blocked: 8, block_rate: 0.08, avg_risk: 0.35 }, ... ]

GET /v1/analytics/top-flags?hours=24&limit=10
→ [ { flag: "denylist_hit", count: 45, pct: 0.32 }, { flag: "injection", count: 30, pct: 0.21 }, ... ]

GET /v1/analytics/intents?hours=24
→ [ { intent: "chat", count: 120, pct: 0.60 }, { intent: "jailbreak", count: 15, pct: 0.075 }, ... ]
```

### Aggregation strategy

All queries run against the `requests` table with `created_at >= now() - interval`. No materialized views or cron jobs — direct aggregation is fine for MVP scale (< 100k rows). If needed later, we can add a `requests_hourly` summary table.

### Charting library

Use **Chart.js** via `vue-chartjs` (already lightweight, works well with Vuetify):
- `npm install chart.js vue-chartjs`
- Line/area chart for timeline
- Horizontal bar chart for policy block rates
- Doughnut chart for intent distribution

---

## Dashboard Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  Analytics                                    Time: [1h|24h|7d|30d] │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐ │
│  │📊 Total │  │🚫 Block │  │⚠️ Modify│  │✅ Allow │  │⚡ Avg   │ │
│  │ Requests│  │  Rate   │  │  Count  │  │  Count  │  │ Latency │ │
│  │  1,247  │  │  6.2%   │  │    23   │  │  1,149  │  │  45ms   │ │
│  │ +12% ↑  │  │ -0.5% ↓ │  │ +3 ↑   │  │ +8% ↑  │  │ -2ms ↓  │ │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘ │
│                                                                     │
│  ┌── Request Volume Timeline ──────────────────────────────────┐   │
│  │  ╱\    ╱╲                                                    │   │
│  │ ╱  \__╱  ╲___╱╲__                      📈 Total            │   │
│  │╱                  ╲___                  🔴 Blocked          │   │
│  │                       ╲___              🟡 Modified         │   │
│  │ 00:00   04:00   08:00   12:00   16:00   20:00   24:00      │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌── Block Rate by Policy ──┐  ┌── Top Risk Flags ───────────┐    │
│  │                          │  │                              │    │
│  │ paranoid  ████████ 15.2% │  │ 1. denylist_hit     45 (32%)│    │
│  │ strict    █████── 8.1%   │  │ 2. injection        30 (21%)│    │
│  │ balanced  ███──── 5.0%   │  │ 3. pii_detected     18 (13%)│    │
│  │ fast      █────── 1.2%   │  │ 4. toxicity         12  (9%)│    │
│  │                          │  │ 5. secrets           8  (6%)│    │
│  └──────────────────────────┘  └──────────────────────────────┘    │
│                                                                     │
│  ┌── Intent Distribution ──────────────────────────────────────┐   │
│  │                                                              │   │
│  │       ┌──────┐                                               │   │
│  │      ╱  chat  ╲     chat: 60%                               │   │
│  │     │  60%     │    question: 20%                            │   │
│  │      ╲________╱     jailbreak: 7.5%                         │   │
│  │     question 20%    extraction: 5%                           │   │
│  │                     other: 7.5%                              │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## File Tree (all changes)

```
apps/proxy-service/
├── src/
│   ├── routers/
│   │   └── analytics.py               # NEW — 5 aggregation endpoints
│   ├── schemas/
│   │   └── analytics.py               # NEW — response schemas
│   └── main.py                        # MODIFIED — register analytics router
└── tests/
    └── test_analytics.py              # NEW

apps/frontend/
├── app/
│   ├── pages/
│   │   └── analytics.vue              # REWRITE
│   ├── components/
│   │   └── analytics/
│   │       ├── kpi-cards.vue          # NEW — 5 summary cards
│   │       ├── timeline-chart.vue     # NEW — area chart
│   │       ├── policy-chart.vue       # NEW — horizontal bar chart
│   │       ├── flags-list.vue         # NEW — ranked risk flags
│   │       └── intent-chart.vue       # NEW — doughnut chart
│   ├── composables/
│   │   └── useAnalytics.ts            # NEW — query composable
│   └── types/
│       └── api.ts                     # MODIFIED — add Analytics types
├── package.json                       # MODIFIED — add chart.js, vue-chartjs
```

---

## Definition of Done

### Automated
```bash
cd apps/proxy-service && python -m pytest tests/test_analytics.py -v
# All aggregation endpoints tested
```

### Smoke tests
```bash
# Summary KPIs
curl -s 'http://localhost:8000/v1/analytics/summary?hours=24' | python -m json.tool

# Timeline
curl -s 'http://localhost:8000/v1/analytics/timeline?hours=24&bucket=1h' | python -m json.tool

# By policy
curl -s 'http://localhost:8000/v1/analytics/by-policy?hours=24' | python -m json.tool

# Top flags
curl -s 'http://localhost:8000/v1/analytics/top-flags?hours=24&limit=5' | python -m json.tool

# Intent distribution
curl -s 'http://localhost:8000/v1/analytics/intents?hours=24' | python -m json.tool
```

### UI verification
- Analytics page loads with time range selector (24h default)
- KPI cards show correct totals
- Timeline chart renders with area fills
- Policy breakdown shows all active policies
- Top flags list shows ranked risk flags
- Intent doughnut chart shows distribution
- Switching time range updates all panels
- Auto-refresh works (optional toggle)

### Checklist
- [ ] 5 analytics API endpoints with time-range filtering
- [ ] Timeline bucketing (auto or manual: 5m, 1h, 1d)
- [ ] KPI summary cards with trend indicators
- [ ] Timeline area chart (Chart.js)
- [ ] Policy block rate horizontal bar chart
- [ ] Top risk flags ranked list
- [ ] Intent distribution doughnut chart
- [ ] Time range selector (1h, 24h, 7d, 30d)
- [ ] Auto-refresh toggle
- [ ] Loading/empty states for all panels
- [ ] Existing tests still pass

---

| **Prev** | **Next** |
|---|---|
| [Step 15 — Policies & Request Log](../15-policies-request-log/SPEC.md) | Step 17 — MLJudge & Advanced Scanners |
