<template>
  <v-container fluid class="results-page">
    <!-- Loading state -->
    <div v-if="loading" class="d-flex justify-center align-center" style="min-height: 300px;">
      <v-progress-circular indeterminate color="primary" />
    </div>

    <template v-else-if="run">
      <!-- Header -->
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
          <v-icon :icon="targetIcon" size="x-small" class="mr-1" />
          {{ targetLabel }}
          &nbsp;·&nbsp; {{ humanPack(run.pack) }}
          &nbsp;·&nbsp; {{ timeAgo }}
        </p>
      </div>

      <!-- Before / After comparison (high up per spec) -->
      <v-card
        v-if="comparison"
        variant="flat"
        class="mb-6 pa-4"
        data-testid="before-after"
      >
        <div class="d-flex align-center flex-wrap ga-3">
          <span class="text-body-2">
            Before: <strong>{{ comparison.run_a.score_simple ?? 0 }}/100</strong>
          </span>
          <v-icon icon="mdi-arrow-right" size="small" />
          <span class="text-body-2">
            After: <strong>{{ comparison.run_b.score_simple ?? 0 }}/100</strong>
          </span>
          <v-chip
            :color="comparison.score_delta >= 0 ? 'success' : 'error'"
            variant="tonal"
            size="small"
          >
            {{ comparison.score_delta >= 0 ? '+' : '' }}{{ comparison.score_delta }}
          </v-chip>
        </div>
        <p class="text-caption text-medium-emphasis mt-2">
          {{ comparison.fixed.length }} fixed
          &nbsp;·&nbsp; {{ comparison.new_failures.length }} new failure{{ comparison.new_failures.length !== 1 ? 's' : '' }}
        </p>
      </v-card>

      <!-- Safe mode banner -->
      <v-alert
        v-if="skippedMutating > 0"
        type="info"
        variant="tonal"
        density="compact"
        class="mb-6"
        data-testid="safe-mode-banner"
      >
        <template #text>
          Safe mode was enabled — {{ skippedMutating }} mutating scenario{{ skippedMutating !== 1 ? 's were' : ' was' }} skipped.
          <v-tooltip location="bottom">
            <template #activator="{ props: tp }">
              <a v-bind="tp" class="text-primary" style="cursor: pointer;">What are mutating scenarios?</a>
            </template>
            <span>Mutating scenarios trigger real actions (delete, modify, transfer) that could affect your target. Safe mode skips them.</span>
          </v-tooltip>
        </template>
      </v-alert>

      <!-- All-skipped banner -->
      <v-alert
        v-if="run.executed === 0 && run.total_applicable === 0"
        type="warning"
        variant="tonal"
        class="mb-6"
        data-testid="all-skipped-banner"
      >
        No scenarios were applicable. Try disabling Safe mode or selecting a different pack.
      </v-alert>

      <!-- Few-executed warning -->
      <v-alert
        v-else-if="run.executed > 0 && run.executed < 5"
        type="warning"
        variant="tonal"
        density="compact"
        class="mb-6"
        data-testid="few-executed-warning"
      >
        Score based on only {{ run.executed }} scenario{{ run.executed !== 1 ? 's' : '' }}. May not be fully representative.
      </v-alert>

      <!-- Partial results -->
      <v-alert
        v-else-if="run.status === 'cancelled' || (run.status === 'failed' && run.executed > 0)"
        type="info"
        variant="tonal"
        density="compact"
        class="mb-6"
        data-testid="partial-results-banner"
      >
        Partial score &mdash; {{ run.executed }} of {{ run.total_applicable }} scenarios completed.
      </v-alert>

      <!-- ================================================================ -->
      <!-- Hero — Score                                                      -->
      <!-- ================================================================ -->
      <v-card v-if="run.executed > 0" variant="flat" class="mb-6 pa-6 text-center" data-testid="score-section">
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
            Based on {{ run.executed }} executed scenario{{ run.executed !== 1 ? 's' : '' }}
          </p>
          <p class="text-body-2 text-medium-emphasis mt-1">
            {{ run.passed }} blocked &nbsp;·&nbsp;
            {{ failedCount }} got through &nbsp;·&nbsp;
            {{ run.skipped }} skipped
          </p>
          <p v-if="criticalCount > 0" class="text-body-2 font-weight-medium mt-2" style="color: #d32f2f;">
            {{ criticalCount }} critical / high severity gap{{ criticalCount !== 1 ? 's' : '' }}
          </p>
        </div>
      </v-card>

      <!-- ================================================================ -->
      <!-- Category Breakdown                                                -->
      <!-- ================================================================ -->
      <h2 class="text-h6 mb-3">Category Breakdown</h2>
      <v-card variant="flat" class="mb-6 pa-4" data-testid="category-breakdown">
        <div
          v-for="cat in categoryBars"
          :key="cat.slug"
          class="mb-4"
        >
          <div class="d-flex justify-space-between mb-1">
            <span class="text-body-2 font-weight-medium">{{ cat.label }}</span>
            <span class="text-body-2 text-medium-emphasis">
              {{ cat.passedCount }}/{{ cat.total }} blocked ({{ cat.percent }}%)
            </span>
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

      <!-- ================================================================ -->
      <!-- Top Failures                                                      -->
      <!-- ================================================================ -->
      <h2 class="text-h6 mb-3">Top Failures</h2>
      <v-card variant="flat" class="mb-6 pa-4" data-testid="top-failures">
        <template v-if="topFailures.length > 0">
          <v-list density="compact" class="bg-transparent">
            <v-list-item
              v-for="fail in topFailures"
              :key="fail.scenario_id"
              class="px-0 mb-2"
              @click="router.push(`/red-team/results/${runId}/scenario/${fail.scenario_id}`)"
              style="cursor: pointer;"
            >
              <template #prepend>
                <v-icon
                  :icon="severityMeta(fail.severity).icon"
                  :color="severityMeta(fail.severity).color"
                  size="small"
                  class="mr-3"
                />
              </template>
              <v-list-item-title class="text-body-2 font-weight-medium">
                {{ fail.title || fail.scenario_id }}
              </v-list-item-title>
              <v-list-item-subtitle class="text-caption">
                {{ fail.scenario_id }}
                &nbsp;·&nbsp; {{ humanCategory(fail.category) }}
                <template v-if="fail.description">
                  &nbsp;·&nbsp; {{ fail.description }}
                </template>
              </v-list-item-subtitle>
              <template #append>
                <div class="d-flex align-center ga-2">
                  <v-chip
                    :color="severityMeta(fail.severity).color"
                    variant="tonal"
                    size="x-small"
                    :prepend-icon="severityMeta(fail.severity).icon"
                  >
                    {{ severityMeta(fail.severity).label }}
                  </v-chip>
                  <v-icon icon="mdi-chevron-right" size="small" />
                </div>
              </template>
            </v-list-item>
          </v-list>
        </template>
        <div v-else class="text-center pa-4">
          <v-icon icon="mdi-shield-check" color="success" size="48" class="mb-2" />
          <p class="text-body-1 font-weight-medium">All attacks blocked</p>
          <p class="text-body-2 text-medium-emphasis">No scenarios got through your agent's defenses.</p>
        </div>
      </v-card>

      <!-- ================================================================ -->
      <!-- CTA — Variant A (Demo Agent / Registered Agent)                   -->
      <!-- ================================================================ -->
      <v-card v-if="ctaVariant === 'A'" variant="flat" class="mb-6 pa-6" data-testid="cta-section">
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
            prepend-icon="mdi-replay"
            :loading="isRerunning"
            data-testid="rerun-btn"
            @click="onRerun"
          >
            Re-run Benchmark
          </v-btn>
          <v-btn
            variant="text"
            prepend-icon="mdi-download"
            data-testid="export-btn"
            @click="onExport"
          >
            Export JSON
          </v-btn>
        </div>
        <p v-if="policyApplied" class="text-body-2 text-success mt-3">
          <v-icon icon="mdi-check" size="small" /> Policy changed to {{ rerunPolicy }}.
          Click Re-run to see the improvement.
        </p>
      </v-card>

      <!-- CTA — Variant B (Local Agent / Hosted Endpoint) -->
      <v-card v-else variant="flat" class="mb-6 pa-6" data-testid="cta-section-b">
        <h2 class="text-h6 mb-2">Protect this endpoint</h2>
        <p class="text-body-2 text-medium-emphasis mb-4">
          Your agent has {{ criticalCount || failedCount }} critical security gap{{ (criticalCount || failedCount) !== 1 ? 's' : '' }}.
          Choose a protection path:
        </p>

        <v-row class="mb-4">
          <v-col cols="12" sm="6">
            <v-card variant="tonal" class="pa-4 h-100" data-testid="proxy-path-card">
              <div class="d-flex align-center mb-2">
                <v-avatar color="primary" variant="tonal" size="36" class="mr-2">
                  <v-icon icon="mdi-shield-half-full" size="20" />
                </v-avatar>
                <span class="text-subtitle-2 font-weight-bold">Quick — Proxy Setup</span>
              </div>
              <p class="text-body-2 text-medium-emphasis mb-3">
                Route traffic through AI Protector. No code changes.
              </p>
              <v-btn
                color="primary"
                variant="flat"
                size="small"
                append-icon="mdi-arrow-right"
                data-testid="proxy-setup-btn"
                :to="`/proxy/setup?endpoint=${encodeURIComponent(targetEndpointUrl)}`"
              >
                Set up Proxy
              </v-btn>
            </v-card>
          </v-col>
          <v-col cols="12" sm="6">
            <v-card variant="tonal" class="pa-4 h-100" data-testid="wizard-path-card">
              <div class="d-flex align-center mb-2">
                <v-avatar color="secondary" variant="tonal" size="36" class="mr-2">
                  <v-icon icon="mdi-wizard-hat" size="20" />
                </v-avatar>
                <span class="text-subtitle-2 font-weight-bold">Deep — Agent Wizard</span>
              </div>
              <p class="text-body-2 text-medium-emphasis mb-3">
                Register tools, roles, RBAC. Most precise protection.
              </p>
              <v-btn
                color="secondary"
                variant="flat"
                size="small"
                append-icon="mdi-arrow-right"
                data-testid="wizard-btn"
                :to="`/agents/new?url=${encodeURIComponent(targetEndpointUrl)}&name=${encodeURIComponent(run?.pack ?? 'agent')}&type=${run?.target_type}`"
              >
                Open Wizard
              </v-btn>
            </v-card>
          </v-col>
        </v-row>

        <div class="d-flex flex-wrap ga-3">
          <v-btn
            variant="outlined"
            prepend-icon="mdi-replay"
            :loading="isRerunning"
            data-testid="rerun-btn-b"
            @click="onRerun"
          >
            Re-run Benchmark
          </v-btn>
          <v-btn
            variant="text"
            prepend-icon="mdi-download"
            data-testid="export-btn-b"
            @click="onExport"
          >
            Export JSON
          </v-btn>
        </div>
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
import { humanCategory, severityMeta, humanPack, scoreLabel } from '~/utils/redTeamLabels'

definePageMeta({ layout: 'default' })

const route = useRoute()
const router = useRouter()
const runId = computed(() => route.params.id as string)

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
// Computed — target label
// ---------------------------------------------------------------------------

const TARGET_LABELS: Record<string, { label: string; icon: string }> = {
  demo_agent: { label: 'Demo Agent', icon: 'mdi-robot-outline' },
  registered_agent: { label: 'Registered Agent', icon: 'mdi-shield-check' },
  local_agent: { label: 'Local Agent', icon: 'mdi-laptop' },
  hosted_endpoint: { label: 'Hosted Endpoint', icon: 'mdi-cloud-outline' },
}

const targetMeta = computed(() => TARGET_LABELS[run.value?.target_type ?? ''] ?? { label: run.value?.target_type ?? 'Agent', icon: 'mdi-robot-outline' })
const targetLabel = computed(() => targetMeta.value.label)
const targetIcon = computed(() => targetMeta.value.icon)

// ---------------------------------------------------------------------------
// Computed — score
// ---------------------------------------------------------------------------

const scoreMeta = computed(() => scoreLabel(run.value?.score_simple ?? 0))

const criticalCount = computed(() => {
  return scenarios.value.filter(
    (s) => s.passed === false && (s.severity === 'critical' || s.severity === 'high'),
  ).length
})

const failedCount = computed(() => {
  return scenarios.value.filter((s) => s.passed === false).length
})

const skippedMutating = computed(() => {
  return run.value?.skipped_reasons?.safe_mode ?? 0
})

const ctaVariant = computed(() => {
  const t = run.value?.target_type
  if (t === 'local_agent' || t === 'hosted_endpoint') return 'B'
  return 'A'
})

const targetEndpointUrl = computed(() => {
  return run.value?.target_config?.endpoint_url ?? ''
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

// ---------------------------------------------------------------------------
// Computed — category bars (human-readable names)
// ---------------------------------------------------------------------------

const categoryBars = computed(() => {
  const groups = new Map<string, { passed: number; total: number }>()
  for (const s of scenarios.value) {
    if (s.skipped) continue
    const cat = s.category || 'uncategorized'
    const g = groups.get(cat) ?? { passed: 0, total: 0 }
    g.total++
    if (s.passed) g.passed++
    groups.set(cat, g)
  }

  return Array.from(groups.entries())
    .map(([slug, g]) => ({
      slug,
      label: humanCategory(slug),
      passedCount: g.passed,
      total: g.total,
      percent: g.total > 0 ? Math.round((g.passed / g.total) * 100) : 0,
    }))
    .sort((a, b) => a.percent - b.percent) // worst first
})

// ---------------------------------------------------------------------------
// Computed — top failures (with enriched fields)
// ---------------------------------------------------------------------------

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
      title: s.title,
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

    if (runData.source_run_id) {
      try {
        comparison.value = await benchmarkService.compareRuns(runData.source_run_id, runData.id)
      } catch {
        // Comparison is optional
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
