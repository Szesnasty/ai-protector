# 16c — Breakdown Panels

| | |
|---|---|
| **Parent** | [Step 16 — Frontend: Analytics](SPEC.md) |
| **Estimated time** | 4–6 hours |
| **Depends on** | 16a (Analytics API: by-policy, top-flags, intents), 16b (page scaffold + useAnalytics) |

---

## Goal

Build the lower section of the analytics dashboard: **block rate by policy** (horizontal bar chart), **top risk flags** (ranked list), and **intent distribution** (doughnut chart). These panels use the data already fetched by `useAnalytics.ts` from sub-step 16b.

---

## Components

### `analytics/policy-chart.vue` — Block rate by policy (horizontal bar chart)

Props: `data: PolicyStats[]`, `loading: boolean`

Chart.js configuration:
- Type: `Bar` with `indexAxis: 'y'` (horizontal bars)
- Labels: policy names (fast, balanced, strict, paranoid, + any custom)
- Datasets:
  - **Block rate** — bar width proportional to `block_rate`, color-coded per policy
- Color mapping:
  - `fast` → green (`#4CAF50`)
  - `balanced` → amber (`#FFC107`)
  - `strict` → orange (`#FF9800`)
  - `paranoid` → red (`#F44336`)
  - custom → grey (`#9E9E9E`)
- X axis: percentage (0%–100%), formatted with `%` suffix
- Tooltip: "Policy: {name} — {blocked}/{total} requests blocked ({block_rate}%)"

Additional info below chart:
- Small table / list showing per-policy details:

```
Policy     Total   Blocked   Block Rate   Avg Risk
paranoid     50       8       16.0%        0.62
strict      120      10        8.3%        0.45
balanced    800      40        5.0%        0.32
fast        200       2        1.0%        0.15
```

```vue
<v-card>
  <v-card-title class="text-subtitle-1">Block Rate by Policy</v-card-title>
  <v-card-text>
    <Bar v-if="data?.length" :data="chartData" :options="chartOptions" :height="160" />
    <div v-else class="text-center text-medium-emphasis py-8">No policy data</div>
  </v-card-text>
</v-card>
```

Loading: `v-skeleton-loader type="image"` (160px)

### `analytics/flags-list.vue` — Top risk flags (ranked list)

Props: `data: RiskFlagCount[]`, `loading: boolean`

No chart library needed — use Vuetify components:

```
┌───────────────────────────────────────┐
│ Top Risk Flags                        │
├───────────────────────────────────────┤
│ 1. 🔴 denylist_hit        45  (32%)  │
│    ████████████████░░░░░░░░░░░░░░░░  │
│ 2. 🟠 injection            30  (21%)  │
│    ███████████░░░░░░░░░░░░░░░░░░░░░  │
│ 3. 🟡 pii_detected         18  (13%)  │
│    ██████░░░░░░░░░░░░░░░░░░░░░░░░░░  │
│ 4. 🟢 toxicity             12   (9%)  │
│    ████░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │
│ 5.    secrets                8   (6%)  │
│    ███░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │
└───────────────────────────────────────┘
```

Implementation:
```vue
<v-card>
  <v-card-title class="text-subtitle-1">Top Risk Flags</v-card-title>
  <v-card-text>
    <v-list density="compact" v-if="data?.length">
      <v-list-item v-for="(flag, i) in data" :key="flag.flag">
        <template #prepend>
          <span class="text-body-2 text-medium-emphasis mr-2">{{ i + 1 }}.</span>
        </template>
        <v-list-item-title>{{ formatFlagName(flag.flag) }}</v-list-item-title>
        <template #append>
          <span class="text-body-2 font-weight-bold mr-2">{{ flag.count }}</span>
          <span class="text-caption text-medium-emphasis">({{ (flag.pct * 100).toFixed(1) }}%)</span>
        </template>
        <v-progress-linear
          :model-value="flag.pct * 100"
          :color="flagColor(flag.flag)"
          height="4"
          class="mt-1"
        />
      </v-list-item>
    </v-list>
    <div v-else class="text-center text-medium-emphasis py-8">No flags recorded</div>
  </v-card-text>
</v-card>
```

Flag name formatting: `denylist_hit` → `Denylist Hit`, `pii_detected` → `PII Detected`

Flag colors:
- `denylist_hit` → red
- `injection` → deep-orange
- `pii_detected` → orange
- `toxicity` → amber
- `secrets` → purple
- default → grey

### `analytics/intent-chart.vue` — Intent distribution (doughnut chart)

Props: `data: IntentCount[]`, `loading: boolean`

Chart.js configuration:
- Type: `Doughnut`
- Labels: intent names
- Data: count values
- Colors: sequential palette (maxing at 8-10 colors, then cycle)
- Center text: total count (using Chart.js plugin or custom CSS overlay)
- Legend: positioned to the right (desktop) or bottom (mobile)

Color palette:
```typescript
const INTENT_COLORS = [
  '#2196F3',  // blue — chat
  '#4CAF50',  // green — question
  '#F44336',  // red — jailbreak
  '#FF9800',  // orange — extraction
  '#9C27B0',  // purple — exfiltration
  '#00BCD4',  // cyan — coding
  '#795548',  // brown — summarize
  '#607D8B',  // blue-grey — other
]
```

```vue
<v-card>
  <v-card-title class="text-subtitle-1">Intent Distribution</v-card-title>
  <v-card-text>
    <div style="position: relative; max-width: 360px; margin: 0 auto;">
      <Doughnut v-if="data?.length" :data="chartData" :options="chartOptions" />
      <div v-else class="text-center text-medium-emphasis py-8">No intent data</div>
    </div>
  </v-card-text>
</v-card>
```

Chart options:
```typescript
const options = {
  responsive: true,
  maintainAspectRatio: true,
  cutout: '55%',
  plugins: {
    legend: {
      position: 'right',
      labels: { usePointStyle: true, padding: 12 },
    },
    tooltip: {
      callbacks: {
        label: (ctx) => `${ctx.label}: ${ctx.raw} (${(pct * 100).toFixed(1)}%)`,
      },
    },
  },
}
```

---

## Chart.js Registration

All chart components need to register Chart.js modules. Create a shared registration utility:

```typescript
// composables/useChartSetup.ts  (or inline in each component)
import {
  Chart as ChartJS,
  ArcElement,
  BarElement,
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
  ArcElement, BarElement,
  CategoryScale, LinearScale,
  PointElement, LineElement,
  Title, Tooltip, Legend, Filler
)
```

---

## Type additions (`types/api.ts`)

```typescript
export interface PolicyStats {
  policy_id: string
  policy_name: string
  total: number
  blocked: number
  modified: number
  allowed: number
  block_rate: number
  avg_risk: number
}

export interface RiskFlagCount {
  flag: string
  count: number
  pct: number
}

export interface IntentCount {
  intent: string
  count: number
  pct: number
}
```

---

## File Tree

```
apps/frontend/app/
├── components/
│   └── analytics/
│       ├── policy-chart.vue         # NEW — horizontal bar chart
│       ├── flags-list.vue           # NEW — ranked list with progress bars
│       └── intent-chart.vue         # NEW — doughnut chart
├── composables/
│   └── useChartSetup.ts             # NEW (optional — shared Chart.js registration)
└── types/
    └── api.ts                       # MODIFIED — PolicyStats, RiskFlagCount, IntentCount
```

---

## Responsive Behavior

| Breakpoint | Layout |
|------------|--------|
| lg+ (≥1280px) | 2 columns: [policy chart] [flags list], [intent chart] [empty] |
| md (960–1279px) | 2 columns: same as lg |
| sm (600–959px) | 1 column: stacked vertically |
| xs (<600px) | 1 column, charts at reduced height |

Doughnut chart legend moves to bottom on `sm` and below.

---

## Definition of Done

### UI verification
- [ ] Policy bar chart shows all active policies with correct block rates
- [ ] Bar colors match policy level (fast=green → paranoid=red)
- [ ] Top flags list shows ranked flags with progress bars and percentages
- [ ] Flag names are human-readable (snake_case → Title Case)
- [ ] Intent doughnut chart shows distribution with legend
- [ ] All 3 panels respond to time range changes
- [ ] All 3 panels have proper loading/empty states
- [ ] Responsive layout: 2 columns on desktop, 1 column on mobile

### Checklist
- [ ] `analytics/policy-chart.vue` — horizontal bar chart with color-coded policies
- [ ] `analytics/flags-list.vue` — ranked list with formatted names and progress bars
- [ ] `analytics/intent-chart.vue` — doughnut chart with color palette and legend
- [ ] `PolicyStats`, `RiskFlagCount`, `IntentCount` types added
- [ ] Chart.js components properly registered (Bar, Doughnut imports)
- [ ] All panels integrated into `analytics.vue` page layout
- [ ] Tooltips show detailed info on hover

---

| **Prev** | **Next** |
|---|---|
| [16b — KPI Cards & Timeline](16b-kpi-timeline.md) | — |
