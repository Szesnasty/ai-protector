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

      <!-- Mini Before/After comparison (only shows if previous run exists) -->
      <v-card
        v-if="comparison"
        variant="flat"
        class="mb-6 pa-4"
        data-testid="before-after"
      >
        <div class="d-flex align-center flex-wrap ga-3">
          <span class="text-body-2">
            Before: <strong>{{ comparison.run_a.score_simple ?? 0 }}/100</strong>
            {{ scoreEmoji(comparison.run_a.score_simple ?? 0) }}
          </span>
          <v-icon icon="mdi-arrow-right" size="small" />
          <span class="text-body-2">
            After: <strong>{{ comparison.run_b.score_simple ?? 0 }}/100</strong>
            {{ scoreEmoji(comparison.run_b.score_simple ?? 0) }}
          </span>
          <v-chip
            :color="comparison.score_delta >= 0 ? 'success' : 'error'"
            variant="tonal"
            size="small"
          >
            {{ comparison.score_delta >= 0 ? '▲' : '▼' }} {{ comparison.score_delta >= 0 ? '+' : '' }}{{ comparison.score_delta }}
          </v-chip>
        </div>
        <p class="text-caption text-medium-emphasis mt-2">
          {{ comparison.fixed.length }} failure{{ comparison.fixed.length !== 1 ? 's' : '' }} fixed
          &nbsp;│&nbsp; {{ comparison.new_failures.length }} new failure{{ comparison.new_failures.length !== 1 ? 's' : '' }}
        </p>
      </v-card>

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

      <!-- CTA section — Demo Agent variant -->
      <v-card variant="flat" class="mb-6 pa-6" data-testid="cta-section">
        <h2 class="text-h6 mb-2">Want to improve this score?</h2>
        <p class="text-body-2 text-medium-emphasis mb-4">
          AI Protector detected {{ failedCount }} unprotected attack vector{{ failedCount !== 1 ? 's' : '' }}.
          Apply recommended policies to harden your agent.
        </p>
        <div class="d-flex flex-wrap ga-3">
          <v-btn
            color="primary"
            variant="flat"
            prepend-icon="mdi-shield-plus"
            data-testid="apply-profile-btn"
            @click="showApplyDialog = true"
          >
            Apply Recommended Profile
          </v-btn>
          <v-btn
            variant="outlined"
            prepend-icon="mdi-cog"
            :to="'/policies'"
          >
            Open Policies
          </v-btn>
          <v-btn
            variant="outlined"
            prepend-icon="mdi-replay"
            :loading="isRerunning"
            data-testid="rerun-btn"
            @click="onRerun"
          >
            Re-run with {{ rerunPolicy }} Policy
          </v-btn>
          <v-btn
            variant="outlined"
            prepend-icon="mdi-download"
            data-testid="export-btn"
            @click="onExport"
          >
            Export Report
          </v-btn>
        </div>
        <p v-if="policyApplied" class="text-body-2 text-success mt-3">
          <v-icon icon="mdi-check" size="small" /> Policy changed to {{ rerunPolicy }}.
          Click Re-run to see the improvement.
        </p>
      </v-card>

      <!-- Apply Recommended Profile dialog -->
      <v-dialog v-model="showApplyDialog" max-width="450">
        <v-card>
          <v-card-title>Switch to Strict Policy?</v-card-title>
          <v-card-text class="text-body-2">
            This enables stricter thresholds for prompt injection, jailbreak, and data leak detectors.
            It may increase false positives but will block more attacks.
          </v-card-text>
          <v-card-actions>
            <v-spacer />
            <v-btn variant="text" @click="showApplyDialog = false">Cancel</v-btn>
            <v-btn color="primary" variant="flat" @click="onApplyProfile">Apply Strict</v-btn>
          </v-card-actions>
        </v-card>
      </v-dialog>
    </template>

    <!-- Error state -->
    <v-alert v-else type="error" variant="tonal" class="mt-4">
      Could not load benchmark results.
    </v-alert>
  </v-container>
</template>

<script setup lang="ts">
import { benchmarkService } from '~/services/benchmarkService'
import type { RunDetail, ScenarioResult, CompareResult } from '~/services/benchmarkService'

definePageMeta({ layout: 'default' })

const route = useRoute()
const router = useRouter()
const runId = computed(() => route.params.id as string)

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

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
const comparison = ref<CompareResult | null>(null)
const showApplyDialog = ref(false)
const policyApplied = ref(false)
const rerunPolicy = ref('Strict')
const isRerunning = ref(false)

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

const failedCount = computed(() => {
  return scenarios.value.filter((s) => s.passed === false).length
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

function scoreEmoji(score: number): string {
  if (score >= 80) return '\uD83D\uDFE2'
  if (score >= 60) return '\uD83D\uDFE1'
  if (score >= 40) return '\uD83D\uDFE0'
  return '\uD83D\uDD34'
}

// ---------------------------------------------------------------------------
// CTA actions
// ---------------------------------------------------------------------------

function onApplyProfile() {
  showApplyDialog.value = false
  policyApplied.value = true
  rerunPolicy.value = 'Strict'
}

async function onRerun() {
  if (!run.value) return
  isRerunning.value = true
  try {
    const result = await benchmarkService.createRun({
      target_type: run.value.target_type,
      pack: run.value.pack,
      policy: policyApplied.value ? 'strict' : (run.value.policy ?? 'balanced'),
      source_run_id: run.value.id,
    })
    router.push(`/red-team/run/${result.id}`)
  } catch {
    isRerunning.value = false
  }
}

function onExport() {
  if (!run.value) return
  const report = {
    run: {
      id: run.value.id,
      target_type: run.value.target_type,
      pack: run.value.pack,
      status: run.value.status,
      score_simple: run.value.score_simple,
      score_weighted: run.value.score_weighted,
      total_applicable: run.value.total_applicable,
      passed: run.value.passed,
      failed: run.value.failed,
      skipped: run.value.skipped,
      policy: run.value.policy,
      created_at: run.value.created_at,
      completed_at: run.value.completed_at,
    },
    categories: categoryBars.value,
    scenarios: scenarios.value.map((s) => ({
      scenario_id: s.scenario_id,
      category: s.category,
      severity: s.severity,
      passed: s.passed,
      expected: s.expected,
      actual: s.actual,
      latency_ms: s.latency_ms,
    })),
  }
  const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `red-team-report-${run.value.id}.json`
  a.click()
  URL.revokeObjectURL(url)
}

// ---------------------------------------------------------------------------
// Fetch
// ---------------------------------------------------------------------------

async function fetchData() {
  loading.value = true
  try {
    const [runData, scenariosData] = await Promise.all([
      benchmarkService.getRun(runId.value),
      benchmarkService.getScenarios(runId.value),
    ])
    run.value = runData
    scenarios.value = scenariosData

    // If this run has a source_run_id, fetch comparison
    if (runData.source_run_id) {
      try {
        comparison.value = await benchmarkService.compareRuns(runData.source_run_id, runData.id)
      } catch {
        // Comparison is optional — don't fail the page
      }
    }
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
