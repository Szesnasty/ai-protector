<template>
  <v-container fluid class="results-page">
    <!-- Loading state -->
    <div v-if="loading" class="d-flex justify-center align-center" style="min-height: 300px;">
      <v-progress-circular indeterminate color="primary" />
    </div>

    <template v-else-if="run">
      <!-- Header info bar -->
      <div class="mb-6">
        <div class="d-flex align-center mb-1">
          <v-btn
            icon="mdi-arrow-left"
            variant="text"
            size="small"
            class="mr-2"
            :to="'/red-team'"
          />
          <h1 class="text-h5">Benchmark Results</h1>
        </div>
        <p class="text-body-2 text-medium-emphasis" data-testid="header-info">
          Target: Demo Agent &nbsp;│&nbsp; Pack: {{ run.pack }}
          &nbsp;│&nbsp; {{ timeAgo }}
        </p>
      </div>

      <!-- Hero section — Score badge -->
      <v-card variant="flat" class="mb-6 pa-6 text-center" data-testid="score-section">
        <div class="d-flex flex-column align-center">
          <div
            class="score-badge mb-3"
            :style="{ borderColor: scoreMeta.color }"
          >
            <span class="score-value" :style="{ color: scoreMeta.color }">
              {{ run.score_simple ?? 0 }}
            </span>
          </div>
          <v-chip
            :color="scoreMeta.vuetifyColor"
            variant="tonal"
            size="small"
            class="mb-2"
            data-testid="score-label"
          >
            {{ scoreMeta.label }}
          </v-chip>
          <p class="text-body-2 text-medium-emphasis" data-testid="score-summary">
            {{ criticalCount }} critical gap{{ criticalCount !== 1 ? 's' : '' }}
            &nbsp;│&nbsp; {{ run.passed }} attacks blocked
            &nbsp;│&nbsp; {{ run.total_applicable }} tested
          </p>
        </div>
      </v-card>

      <!-- Category breakdown -->
      <h2 class="text-h6 mb-3">Category Breakdown</h2>
      <v-card variant="flat" class="mb-6 pa-4" data-testid="category-breakdown">
        <div
          v-for="cat in categoryBars"
          :key="cat.name"
          class="mb-4"
        >
          <div class="d-flex justify-space-between mb-1">
            <span class="text-body-2 font-weight-medium">{{ cat.name }}</span>
            <span class="text-body-2 text-medium-emphasis">{{ cat.passedCount }}/{{ cat.total }} ({{ cat.percent }}%)</span>
          </div>
          <v-progress-linear
            :model-value="cat.percent"
            :color="cat.percent >= 80 ? 'success' : cat.percent >= 60 ? 'warning' : 'error'"
            height="10"
            rounded
          />
        </div>
        <p v-if="categoryBars.length === 0" class="text-body-2 text-medium-emphasis">
          No category data available.
        </p>
      </v-card>

      <!-- Top failures -->
      <h2 class="text-h6 mb-3">Top Failures</h2>
      <v-card variant="flat" class="mb-6 pa-4" data-testid="top-failures">
        <template v-if="topFailures.length > 0">
          <v-list density="compact">
            <v-list-item
              v-for="fail in topFailures"
              :key="fail.scenario_id"
              class="px-0"
            >
              <template #prepend>
                <v-icon icon="mdi-close-circle" color="error" size="small" class="mr-2" />
              </template>
              <v-list-item-title class="text-body-2 font-weight-medium">
                {{ fail.scenario_id }}
              </v-list-item-title>
              <v-list-item-subtitle class="text-caption">
                Expected: {{ fail.expected }} → Got: {{ fail.actual ?? 'ALLOW' }}
                &nbsp;·&nbsp; {{ fail.category }}
              </v-list-item-subtitle>
              <template #append>
                <v-btn
                  variant="text"
                  size="x-small"
                  color="primary"
                  @click="router.push(`/red-team/results/${runId}/scenario/${fail.scenario_id}`)"
                >
                  View Details
                </v-btn>
              </template>
            </v-list-item>
          </v-list>
        </template>
        <div v-else class="text-center pa-4">
          <v-icon icon="mdi-check-circle" color="success" size="48" class="mb-2" />
          <p class="text-body-2 text-medium-emphasis">No failures! All scenarios passed.</p>
        </div>
      </v-card>

      <!-- Confidence (demo agent = High, no banner needed per spec) -->
      <!-- For future phases with Medium confidence, a banner will go here -->
    </template>

    <!-- Error state -->
    <v-alert v-else type="error" variant="tonal" class="mt-4">
      Could not load benchmark results.
    </v-alert>
  </v-container>
</template>

<script setup lang="ts">
import { api } from '~/services/api'

definePageMeta({ layout: 'default' })

const route = useRoute()
const router = useRouter()
const runId = computed(() => route.params.id as string)

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface RunDetail {
  id: string
  pack: string
  status: string
  target_type: string
  score_simple: number | null
  score_weighted: number | null
  confidence: string | null
  total_in_pack: number
  total_applicable: number
  executed: number
  passed: number
  failed: number
  skipped: number
  created_at: string | null
  completed_at: string | null
}

interface ScenarioResult {
  id: string
  scenario_id: string
  category: string
  severity: string
  prompt: string
  expected: string
  actual: string | null
  passed: boolean | null
  skipped: boolean
  skipped_reason: string | null
  detector_type: string | null
  latency_ms: number | null
}

interface ScoreMeta {
  label: string
  color: string
  vuetifyColor: string
}

// ---------------------------------------------------------------------------
// Data
// ---------------------------------------------------------------------------

const loading = ref(true)
const run = ref<RunDetail | null>(null)
const scenarios = ref<ScenarioResult[]>([])

// ---------------------------------------------------------------------------
// Computed
// ---------------------------------------------------------------------------

const scoreMeta = computed<ScoreMeta>(() => {
  const score = run.value?.score_simple ?? 0
  if (score >= 90) return { label: 'Strong', color: '#2e7d32', vuetifyColor: 'green-darken-2' }
  if (score >= 80) return { label: 'Good', color: '#4caf50', vuetifyColor: 'success' }
  if (score >= 60) return { label: 'Needs Hardening', color: '#fb8c00', vuetifyColor: 'warning' }
  if (score >= 40) return { label: 'Weak', color: '#ff9800', vuetifyColor: 'orange' }
  return { label: 'Critical', color: '#d32f2f', vuetifyColor: 'error' }
})

const criticalCount = computed(() => {
  return scenarios.value.filter(
    (s) => s.passed === false && (s.severity === 'critical' || s.severity === 'high'),
  ).length
})

const timeAgo = computed(() => {
  if (!run.value?.completed_at && !run.value?.created_at) return ''
  const ts = run.value.completed_at ?? run.value.created_at
  if (!ts) return ''
  const diff = Math.round((Date.now() - new Date(ts).getTime()) / 1000)
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.round(diff / 60)} min ago`
  if (diff < 86400) return `${Math.round(diff / 3600)}h ago`
  return `${Math.round(diff / 86400)}d ago`
})

// Group scenarios by category
const categoryBars = computed(() => {
  const groups = new Map<string, { passed: number; total: number }>()
  for (const s of scenarios.value) {
    if (s.skipped) continue
    const cat = s.category || 'Uncategorized'
    const g = groups.get(cat) ?? { passed: 0, total: 0 }
    g.total++
    if (s.passed) g.passed++
    groups.set(cat, g)
  }

  return Array.from(groups.entries())
    .map(([name, g]) => ({
      name,
      passedCount: g.passed,
      total: g.total,
      percent: g.total > 0 ? Math.round((g.passed / g.total) * 100) : 0,
    }))
    .sort((a, b) => a.percent - b.percent) // worst first
})

// Severity weight for sorting
const severityWeight: Record<string, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
}

const topFailures = computed(() => {
  return scenarios.value
    .filter((s) => s.passed === false)
    .sort((a, b) => (severityWeight[a.severity] ?? 9) - (severityWeight[b.severity] ?? 9))
    .slice(0, 5)
})

// ---------------------------------------------------------------------------
// Fetch
// ---------------------------------------------------------------------------

async function fetchData() {
  loading.value = true
  try {
    const [runRes, scenariosRes] = await Promise.all([
      api.get<RunDetail>(`/v1/benchmark/runs/${runId.value}`),
      api.get<ScenarioResult[]>(`/v1/benchmark/runs/${runId.value}/scenarios?limit=1000`),
    ])
    run.value = runRes.data
    scenarios.value = scenariosRes.data
  } catch {
    run.value = null
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchData()
})
</script>

<style lang="scss" scoped>
.score-badge {
  width: 120px;
  height: 120px;
  border-radius: 50%;
  border: 6px solid;
  display: flex;
  align-items: center;
  justify-content: center;
}

.score-value {
  font-size: 2.5rem;
  font-weight: 700;
  line-height: 1;
}
</style>
