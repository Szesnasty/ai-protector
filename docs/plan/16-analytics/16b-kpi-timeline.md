# 16b — KPI Cards & Timeline Chart

| | |
|---|---|
| **Parent** | [Step 16 — Frontend: Analytics](SPEC.md) |
| **Estimated time** | 3–4 hours |
| **Depends on** | 16a (Analytics API: summary + timeline endpoints) |

---

## Goal

Build the top section of the analytics dashboard: **5 KPI summary cards** and a **time-series area chart** showing request volume trends. Add a **time range selector** (1h, 24h, 7d, 30d) that controls all analytics panels globally.

---

## Dependencies

```bash
cd apps/frontend && npm install chart.js vue-chartjs
```

---

## Components

### `analytics/kpi-cards.vue` — 5 summary cards

Props: `summary: AnalyticsSummary | null`, `loading: boolean`

Cards layout: 5 cards in a responsive row (`v-col cols="12" sm="6" md="4" lg` or flex)

| Card | Icon | Value | Color |
|------|------|-------|-------|
| Total Requests | `mdi-chart-timeline-variant` | `total_requests` | `primary` |
| Block Rate | `mdi-shield-off` | `block_rate` (formatted as %) | `error` |
| Modified | `mdi-shield-edit` | `modified` | `warning` |
| Allowed | `mdi-shield-check` | `allowed` | `success` |
| Avg Latency | `mdi-timer-outline` | `avg_latency_ms` (formatted as `Xms`) | `info` |

Each card:
```vue
<v-card variant="outlined">
  <v-card-text class="d-flex align-center">
    <v-avatar :color="color" variant="tonal" size="48" class="mr-4">
      <v-icon :icon="icon" />
    </v-avatar>
    <div>
      <div class="text-caption text-medium-emphasis">{{ label }}</div>
      <div class="text-h5 font-weight-bold">{{ formattedValue }}</div>
      <div class="text-caption" v-if="subtitle">{{ subtitle }}</div>
    </div>
  </v-card-text>
</v-card>
```

Additional info per card:
- **Total Requests**: subtitle = `avg_risk` as "Avg risk: 0.XX"
- **Block Rate**: subtitle = `blocked` count as "N blocked"
- **Avg Latency**: subtitle = top_intent as "Top: {intent}"

Loading state: `v-skeleton-loader type="card"` for each card

### `analytics/timeline-chart.vue` — Area chart

Props: `data: TimelineBucket[]`, `loading: boolean`

Chart.js configuration:
- Type: `Line` (with `fill: true` for area effect)
- X axis: `time` labels (formatted: `HH:mm` for hours, `MM/DD` for days)
- Datasets:
  - **Total** — primary color, filled area (opacity 0.1)
  - **Blocked** — red, filled area (opacity 0.2)
  - **Modified** — orange, dashed line
- Responsive, maintain aspect ratio
- Tooltip: shows all values for the hovered bucket
- Legend: top right

```typescript
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js'

ChartJS.register(
  CategoryScale, LinearScale, PointElement, LineElement,
  Title, Tooltip, Legend, Filler
)
```

Chart options:
```typescript
const options = {
  responsive: true,
  maintainAspectRatio: false,
  interaction: { mode: 'index', intersect: false },
  plugins: {
    legend: { position: 'top' },
    tooltip: { mode: 'index' },
  },
  scales: {
    x: { grid: { display: false } },
    y: { beginAtZero: true, ticks: { precision: 0 } },
  },
}
```

Loading state: `v-skeleton-loader type="image"` with fixed height (300px)
Empty state: "No data for this time range" centered text

---

## Page Structure (`analytics.vue`)

```vue
<template>
  <v-container fluid>
    <!-- Header -->
    <div class="d-flex align-center justify-space-between mb-4">
      <div>
        <h1 class="text-h4">Analytics</h1>
        <p class="text-body-2 text-medium-emphasis">
          Firewall performance and threat overview
        </p>
      </div>
      <div class="d-flex align-center ga-2">
        <v-btn-toggle v-model="selectedRange" mandatory variant="outlined" density="compact">
          <v-btn v-for="r in timeRanges" :key="r.value" :value="r.value" size="small">
            {{ r.label }}
          </v-btn>
        </v-btn-toggle>
        <v-btn icon="mdi-refresh" variant="text" @click="refreshAll" :loading="isRefreshing" />
      </div>
    </div>

    <!-- KPI Cards -->
    <analytics-kpi-cards :summary="summary" :loading="summaryLoading" class="mb-6" />

    <!-- Timeline Chart -->
    <v-card class="mb-6">
      <v-card-title class="text-subtitle-1">Request Volume</v-card-title>
      <v-card-text>
        <analytics-timeline-chart :data="timeline" :loading="timelineLoading" />
      </v-card-text>
    </v-card>

    <!-- Breakdown panels (Step 16c) -->
    <v-row>
      <v-col cols="12" md="6">
        <analytics-policy-chart :data="byPolicy" :loading="byPolicyLoading" />
      </v-col>
      <v-col cols="12" md="6">
        <analytics-flags-list :data="topFlags" :loading="topFlagsLoading" />
      </v-col>
    </v-row>
    <v-row>
      <v-col cols="12" md="6">
        <analytics-intent-chart :data="intents" :loading="intentsLoading" />
      </v-col>
    </v-row>
  </v-container>
</template>
```

---

## Composable

### `useAnalytics.ts`

```typescript
export const useAnalytics = () => {
  const selectedRange = ref(24)  // hours

  const timeRanges = [
    { label: '1h', value: 1 },
    { label: '24h', value: 24 },
    { label: '7d', value: 168 },
    { label: '30d', value: 720 },
  ]

  // Summary
  const { data: summary, isLoading: summaryLoading, refetch: refetchSummary } = useQuery({
    queryKey: ['analytics', 'summary', selectedRange],
    queryFn: () => api.get(`/v1/analytics/summary?hours=${selectedRange.value}`).then(r => r.data),
    refetchInterval: 30_000,  // auto-refresh every 30s
  })

  // Timeline
  const { data: timeline, isLoading: timelineLoading, refetch: refetchTimeline } = useQuery({
    queryKey: ['analytics', 'timeline', selectedRange],
    queryFn: () => api.get(`/v1/analytics/timeline?hours=${selectedRange.value}`).then(r => r.data),
    refetchInterval: 30_000,
  })

  // By policy
  const { data: byPolicy, isLoading: byPolicyLoading, refetch: refetchByPolicy } = useQuery({
    queryKey: ['analytics', 'by-policy', selectedRange],
    queryFn: () => api.get(`/v1/analytics/by-policy?hours=${selectedRange.value}`).then(r => r.data),
    refetchInterval: 30_000,
  })

  // Top flags
  const { data: topFlags, isLoading: topFlagsLoading, refetch: refetchTopFlags } = useQuery({
    queryKey: ['analytics', 'top-flags', selectedRange],
    queryFn: () => api.get(`/v1/analytics/top-flags?hours=${selectedRange.value}`).then(r => r.data),
    refetchInterval: 30_000,
  })

  // Intents
  const { data: intents, isLoading: intentsLoading, refetch: refetchIntents } = useQuery({
    queryKey: ['analytics', 'intents', selectedRange],
    queryFn: () => api.get(`/v1/analytics/intents?hours=${selectedRange.value}`).then(r => r.data),
    refetchInterval: 30_000,
  })

  const refreshAll = () => {
    refetchSummary(); refetchTimeline(); refetchByPolicy(); refetchTopFlags(); refetchIntents()
  }

  return {
    selectedRange, timeRanges,
    summary, summaryLoading,
    timeline, timelineLoading,
    byPolicy, byPolicyLoading,
    topFlags, topFlagsLoading,
    intents, intentsLoading,
    refreshAll,
    isRefreshing: computed(() =>
      summaryLoading.value || timelineLoading.value || byPolicyLoading.value
      || topFlagsLoading.value || intentsLoading.value
    ),
  }
}
```

---

## Type additions (`types/api.ts`)

```typescript
export interface AnalyticsSummary {
  total_requests: number
  blocked: number
  modified: number
  allowed: number
  block_rate: number
  avg_risk: number
  avg_latency_ms: number
  top_intent: string | null
}

export interface TimelineBucket {
  time: string
  total: number
  blocked: number
  modified: number
  allowed: number
}
```

---

## File Tree

```
apps/frontend/
├── app/
│   ├── pages/
│   │   └── analytics.vue                # REWRITE (partial — header + KPIs + timeline)
│   ├── components/
│   │   └── analytics/
│   │       ├── kpi-cards.vue            # NEW
│   │       └── timeline-chart.vue       # NEW
│   ├── composables/
│   │   └── useAnalytics.ts             # NEW
│   └── types/
│       └── api.ts                       # MODIFIED
├── package.json                         # MODIFIED — chart.js, vue-chartjs
```

---

## Definition of Done

### UI verification
- [ ] Time range toggle: 1h, 24h, 7d, 30d — switching updates all panels
- [ ] 5 KPI cards show correct values from API
- [ ] KPI cards have loading skeleton while fetching
- [ ] Timeline area chart renders with 3 datasets (total, blocked, modified)
- [ ] Timeline x-axis labels format correctly (HH:mm for hours, MM/DD for days)
- [ ] Chart tooltip shows all values on hover
- [ ] Refresh button triggers manual refetch
- [ ] Auto-refresh every 30s works
- [ ] Empty state shown when no data

### Checklist
- [ ] `chart.js` + `vue-chartjs` installed
- [ ] `analytics/kpi-cards.vue` — 5 cards with icons, values, subtitles
- [ ] `analytics/timeline-chart.vue` — Line chart with area fill
- [ ] `useAnalytics.ts` — queries for all 5 analytics endpoints
- [ ] `AnalyticsSummary`, `TimelineBucket` types added
- [ ] `analytics.vue` page with header, time range toggle, refresh button
- [ ] Responsive layout (cards wrap on mobile)

---

| **Prev** | **Next** |
|---|---|
| [16a — Analytics API](16a-analytics-api.md) | [16c — Breakdown Panels](16c-breakdowns.md) |
