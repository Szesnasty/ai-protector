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
          <h1 class="text-h5">{{ isBaseline ? 'Baseline Results' : 'Benchmark Results' }}</h1>
        </div>
        <p class="text-body-2 text-medium-emphasis" data-testid="header-info">
          <v-icon :icon="targetIcon" size="x-small" class="mr-1" />
          {{ targetLabel }}
          &nbsp;·&nbsp; {{ humanPack(run.pack) }}
          &nbsp;·&nbsp; {{ timeAgo }}
          <v-chip
            v-if="runClass"
            :color="runClass.color"
            variant="tonal"
            size="x-small"
            :prepend-icon="runClass.icon"
            class="ml-2"
            data-testid="run-type-chip"
          >
            {{ runClass.label }}
          </v-chip>
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

      <!-- Baseline run banner — prominent, always visible for unprotected runs -->
      <v-alert
        v-if="isBaseline"
        type="warning"
        variant="tonal"
        class="mb-6"
        data-testid="baseline-banner"
      >
        <template #title>
          <v-icon icon="mdi-shield-off-outline" size="small" class="mr-1" />
          Baseline Run — No Active Protection
        </template>
        <template #text>
          This benchmark ran directly against the model without AI Protector.
          Results show baseline behavior, not verified runtime protection.
          Safe outcomes may come from model self-defense or unattributed behavior — <strong>not enforced controls.</strong>
        </template>
      </v-alert>

      <!-- False-sense-of-safety warning — high score on baseline run -->
      <v-alert
        v-if="isBaseline && (run.score_simple ?? 0) >= 80 && run.executed >= 5"
        color="blue-grey"
        variant="tonal"
        class="mb-6"
        data-testid="false-safety-warning"
      >
        <template #prepend>
          <v-icon icon="mdi-eye-off" color="blue-grey" />
        </template>
        <template #title>
          High score, but no protection in place
        </template>
        <template #text>
          Most safe outcomes in this run came from model behavior or unattributed safe responses, not verified protection controls.
          A high baseline score does <strong>not</strong> mean your endpoint has enforced runtime protection.
          <nuxt-link to="/red-team/configure?target=hosted_endpoint" class="text-decoration-none font-weight-bold ml-1">
            Set up protection and re-run →
          </nuxt-link>
        </template>
      </v-alert>

      <!-- ================================================================ -->
      <!-- Hero — Executive Summary                                          -->
      <!-- ================================================================ -->
      <v-card v-if="run.executed > 0" variant="flat" class="mb-6 pa-5" data-testid="score-section">
        <v-row align="center">
          <!-- LEFT: Score + verdict -->
          <v-col cols="12" md="5" class="d-flex flex-column align-center align-md-start text-center text-md-start">
            <div class="d-flex align-center ga-4 mb-3">
              <div
                class="score-badge"
                :style="{ borderColor: scoreMeta.color }"
              >
                <span class="score-value" :style="{ color: scoreMeta.color }">
                  {{ run.score_simple ?? 0 }}
                </span>
              </div>
              <div>
                <v-chip
                  :color="scoreMeta.vuetifyColor"
                  variant="tonal"
                  size="small"
                  class="mb-1"
                  data-testid="score-label"
                >
                  {{ scoreMeta.label }}
                </v-chip>
                <p class="text-caption text-medium-emphasis mb-0">
                  {{ run.executed }} scenario{{ run.executed !== 1 ? 's' : '' }} tested
                </p>
              </div>
            </div>
            <!-- One-sentence interpretation -->
            <p class="text-body-2 text-medium-emphasis mb-0" data-testid="score-interpretation">
              {{ scoreInterpretation }}
            </p>
          </v-col>

          <!-- RIGHT: Stats + Primary CTA -->
          <v-col cols="12" md="7">
            <!-- Stats row -->
            <div class="d-flex flex-wrap ga-4 mb-4">
              <div class="text-center">
                <span class="text-h6 font-weight-bold" :class="isBaseline ? 'text-blue-grey' : 'text-success'">{{ run.passed }}</span>
                <p class="text-caption text-medium-emphasis mb-0">{{ isBaseline ? 'safe outcomes' : 'blocked' }}</p>
              </div>
              <div class="text-center">
                <span class="text-h6 font-weight-bold text-error">{{ failedCount }}</span>
                <p class="text-caption text-medium-emphasis mb-0">got through</p>
              </div>
              <div v-if="criticalCount > 0" class="text-center">
                <span class="text-h6 font-weight-bold" style="color: #d32f2f;">{{ criticalCount }}</span>
                <p class="text-caption text-medium-emphasis mb-0">high/critical gaps</p>
              </div>
              <div class="text-center">
                <span class="text-h6 font-weight-bold text-medium-emphasis">{{ run.skipped }}</span>
                <p class="text-caption text-medium-emphasis mb-0">skipped</p>
              </div>
            </div>

            <!-- Protection status block — baseline only -->
            <div v-if="isBaseline" class="mb-4 pa-3 rounded-lg" style="background: rgba(0,0,0,0.03);" data-testid="protection-status-block">
              <div class="d-flex flex-column ga-1">
                <span class="text-caption text-medium-emphasis">
                  <v-icon icon="mdi-shield-off-outline" size="x-small" class="mr-1" />Runtime protection: <strong>Not enabled</strong>
                </span>
                <span class="text-caption text-medium-emphasis">
                  <v-icon icon="mdi-gauge-empty" size="x-small" class="mr-1" />Protection efficacy: <strong>N/A</strong>
                </span>
                <span class="text-caption text-medium-emphasis">
                  <v-icon icon="mdi-clipboard-check-outline" size="x-small" class="mr-1" />Verified protection controls: <strong>Not measured in this run</strong>
                </span>
              </div>
            </div>

            <!-- Recommended next step — above the fold -->
            <template v-if="failedCount > 0">
              <p class="text-caption font-weight-bold text-uppercase text-medium-emphasis mb-1">Recommended next step</p>
              <p v-if="isBaseline" class="text-caption text-medium-emphasis mb-3">
                This baseline shows {{ failedCount }} attack{{ failedCount !== 1 ? 's' : '' }} that got through without any enforced protection. Safe outcomes in this run came from model behavior alone — not verified runtime controls. Set up AI Protector and re-run to measure real protection.
              </p>
              <p v-else class="text-caption text-medium-emphasis mb-3">
                Most of the remaining risk comes from prompt injection and jailbreak bypasses. Tighten your policy and re-run this benchmark to verify improvement.
              </p>
              <div class="d-flex flex-wrap ga-2 mb-1">
                <v-btn
                  v-if="isBaseline"
                  color="primary"
                  variant="flat"
                  size="small"
                  prepend-icon="mdi-shield-plus"
                  data-testid="hero-setup-btn"
                  @click="showSetupDialog = true"
                >
                  Set Up Protection
                </v-btn>
                <v-btn
                  v-if="isBaseline"
                  variant="outlined"
                  size="small"
                  prepend-icon="mdi-compare"
                  to="/compare"
                  data-testid="hero-compare-btn"
                >
                  Open Protection Compare
                </v-btn>
                <v-btn
                  v-if="isBaseline"
                  variant="outlined"
                  size="small"
                  prepend-icon="mdi-download"
                  data-testid="hero-export-btn"
                  @click="onExport"
                >
                  Export Baseline Report
                </v-btn>
                <v-btn
                  v-if="isBaseline"
                  variant="text"
                  size="small"
                  prepend-icon="mdi-replay"
                  :loading="isRerunning"
                  data-testid="hero-rerun-btn"
                  @click="onRerun"
                >
                  Re-run Benchmark
                </v-btn>
                <template v-if="!isBaseline">
                  <v-btn
                    color="primary"
                    variant="flat"
                    size="small"
                    prepend-icon="mdi-shield-half-full"
                    data-testid="hero-setup-btn"
                    @click="showSetupDialog = true"
                  >
                    View Recommended Setup
                  </v-btn>
                  <v-btn
                    variant="outlined"
                    size="small"
                    prepend-icon="mdi-replay"
                    :loading="isRerunning"
                    data-testid="hero-rerun-btn"
                    @click="onRerun"
                  >
                    Re-run Benchmark
                  </v-btn>
                  <v-btn
                    variant="text"
                    size="small"
                    prepend-icon="mdi-download"
                    data-testid="hero-export-btn"
                    @click="onExport"
                  >
                    Export
                  </v-btn>
                </template>
              </div>
              <p v-if="isBaseline" class="text-caption text-medium-emphasis mt-2 mb-0">
                Set up AI Protector and re-run this benchmark to verify enforced protection instead of model-only resistance.
              </p>
              <p v-else class="text-caption text-medium-emphasis mt-1 mb-0">
                Usually requires a server-side endpoint change · Re-run after setup to verify improvement
              </p>
              <p v-if="!isBaseline" class="text-caption mt-3 mb-0">
                <nuxt-link to="/compare" class="text-decoration-none">
                  <v-icon size="14" class="mr-1">mdi-compare</v-icon>
                  Want to see how protection changes model behavior? Open Protection Compare
                </nuxt-link>
              </p>
            </template>

            <!-- All passed — different treatment for baseline vs protected -->
            <template v-else>
              <!-- Baseline: don't celebrate, explain model resistance -->
              <template v-if="isBaseline">
                <p class="text-caption font-weight-bold text-uppercase text-medium-emphasis mb-1">What this means</p>
                <p class="text-caption text-medium-emphasis mb-3">
                  All tested scenarios had safe outcomes, but these reflect model behavior — not enforced runtime protection.
                  Model resistance can change with updates or new attack techniques. This is not proof your endpoint is protected.
                </p>
                <div class="d-flex flex-wrap ga-2 mb-1">
                  <v-btn
                    color="primary"
                    variant="flat"
                    size="small"
                    prepend-icon="mdi-shield-plus"
                    @click="showSetupDialog = true"
                  >
                    Set Up Protection
                  </v-btn>
                  <v-btn
                    variant="outlined"
                    size="small"
                    prepend-icon="mdi-compare"
                    to="/compare"
                  >
                    Open Protection Compare
                  </v-btn>
                  <v-btn
                    variant="outlined"
                    size="small"
                    prepend-icon="mdi-download"
                    @click="onExport"
                  >
                    Export Baseline Report
                  </v-btn>
                  <v-btn
                    variant="text"
                    size="small"
                    prepend-icon="mdi-replay"
                    :loading="isRerunning"
                    @click="onRerun"
                  >
                    Re-run Benchmark
                  </v-btn>
                </div>
                <p class="text-caption text-medium-emphasis mt-2 mb-0">
                  Set up AI Protector and re-run this benchmark to verify enforced protection instead of model-only resistance.
                </p>
              </template>
              <!-- Protected: celebrate -->
              <template v-else>
                <div class="d-flex flex-wrap ga-2">
                  <v-btn
                    variant="outlined"
                    size="small"
                    prepend-icon="mdi-replay"
                    :loading="isRerunning"
                    @click="onRerun"
                  >
                    Re-run Benchmark
                  </v-btn>
                  <v-btn
                    variant="text"
                    size="small"
                    prepend-icon="mdi-download"
                    @click="onExport"
                  >
                    Export
                  </v-btn>
                </div>
              </template>
            </template>
          </v-col>
        </v-row>
      </v-card>

      <!-- ================================================================ -->
      <!-- Why this baseline looks safer (breakdown) — baseline only          -->
      <!-- ================================================================ -->
      <template v-if="isBaseline && run.executed > 0">
        <h2 class="text-h6 mb-3">Why this baseline looks safer than it is</h2>
        <v-card variant="flat" class="mb-6 pa-4" data-testid="baseline-breakdown">
          <div class="d-flex flex-wrap ga-6 mb-4">
            <div class="text-center">
              <span class="text-h6 font-weight-bold text-blue-grey">{{ run.passed }}</span>
              <p class="text-caption text-medium-emphasis mb-0">Safe outcomes</p>
              <p class="text-caption text-disabled mb-0" style="font-size: 0.7rem;">model resisted or no breach</p>
            </div>
            <div class="text-center">
              <span class="text-h6 font-weight-bold" style="color: #78909c;">0</span>
              <p class="text-caption text-medium-emphasis mb-0">Blocked by AI Protector</p>
            </div>
            <div class="text-center">
              <span class="text-h6 font-weight-bold text-error">{{ failedCount }}</span>
              <p class="text-caption text-medium-emphasis mb-0">Attacks succeeded</p>
            </div>
            <div v-if="run.skipped > 0" class="text-center">
              <span class="text-h6 font-weight-bold text-medium-emphasis">{{ run.skipped }}</span>
              <p class="text-caption text-medium-emphasis mb-0">Skipped</p>
            </div>
          </div>
          <v-alert
            color="blue-grey-darken-1"
            variant="tonal"
            density="compact"
            class="baseline-guardrail-note"
            data-testid="baseline-guardrail-note"
          >
            <template #prepend>
              <v-icon icon="mdi-information-outline" size="small" />
            </template>
            <template #text>
              <span class="text-body-2">
                Most safe outcomes in this run came from model behavior or unattributed safe responses — not verified protection controls.
                <strong>"Safe outcome" does not mean "actively protected."</strong>
              </span>
            </template>
          </v-alert>
        </v-card>
      </template>

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
              {{ cat.passedCount }}/{{ cat.total }} {{ isBaseline ? 'safe outcomes observed' : 'blocked' }} ({{ cat.percent }}%)
            </span>
          </div>
          <v-progress-linear
            :model-value="cat.percent"
            :color="isBaseline ? (cat.percent >= 80 ? 'blue-grey' : cat.percent >= 60 ? 'warning' : 'error') : (cat.percent >= 80 ? 'success' : cat.percent >= 60 ? 'warning' : 'error')"
            height="10"
            rounded
          />
          <div v-if="isBaseline" class="d-flex ga-3 mt-1">
            <span class="text-caption text-blue-grey">{{ cat.passedCount }} safe outcome{{ cat.passedCount !== 1 ? 's' : '' }}</span>
            <span class="text-caption text-medium-emphasis">·</span>
            <span class="text-caption text-error">{{ cat.total - cat.passedCount }} got through</span>
          </div>
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
              <v-list-item-title class="text-body-2">
                <span class="failure-id text-medium-emphasis">{{ fail.scenario_id }}</span>
                <span v-if="fail.title" class="text-medium-emphasis"> · </span>
                <span class="font-weight-medium">{{ fail.title || fail.scenario_id }}</span>
              </v-list-item-title>
              <v-list-item-subtitle class="text-caption mt-1">
                {{ humanCategory(fail.category) }}
                <span v-if="failureImpact(fail)" class="text-error">
                  &nbsp;·&nbsp; {{ failureImpact(fail) }}
                </span>
              </v-list-item-subtitle>
              <template #append>
                <div class="d-flex align-center ga-2">
                  <v-chip
                    v-if="failureMitigation(fail)"
                    :color="failureMitigation(fail).startsWith('Can be') ? 'warning' : 'warning'"
                    variant="outlined"
                    size="x-small"
                  >
                    {{ failureMitigation(fail) }}
                  </v-chip>
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
          <v-icon :icon="isBaseline ? 'mdi-robot-happy' : 'mdi-shield-check'" :color="isBaseline ? 'blue-grey' : 'success'" size="48" class="mb-2" />
          <p class="text-body-1 font-weight-medium">{{ isBaseline ? 'No breaches detected — but no active protection either' : 'All attacks blocked' }}</p>
          <p class="text-body-2 text-medium-emphasis">
            {{ isBaseline
              ? 'All scenarios had safe outcomes, but these reflect model behavior — not enforced protection. Set up AI Protector for verified runtime controls.'
              : 'No scenarios got through your endpoint\'s defenses.'
            }}
          </p>
        </div>
      </v-card>

      <!-- ================================================================ -->
      <!-- How to Protect This Endpoint — dialog                             -->
      <!-- ================================================================ -->
      <v-dialog v-model="showSetupDialog" max-width="580">
        <v-card>
          <v-card-title class="d-flex align-center">
            <v-icon icon="mdi-shield-half-full" size="small" class="mr-2" />
            How to Protect This Endpoint
          </v-card-title>
          <v-card-text>
            <!-- What to change -->
            <h3 class="text-subtitle-2 font-weight-bold mb-2">1. Update your backend</h3>
            <p class="text-body-2 text-medium-emphasis mb-3">
              Route requests through AI Protector instead of sending them directly to your model.
              This is a server-side change — no frontend modifications needed.
            </p>

            <!-- What to paste -->
            <h3 class="text-subtitle-2 font-weight-bold mb-2">2. Use this protected URL</h3>
            <v-card variant="tonal" class="pa-3 mb-1">
              <code class="text-body-2" style="word-break: break-all;" data-testid="protected-url">
                {{ protectedBaseUrl }}
              </code>
            </v-card>
            <p class="text-caption text-medium-emphasis mb-3">
              Replace your current model endpoint URL with this in your backend config or SDK init.
            </p>

            <!-- Integration effort -->
            <v-alert type="info" variant="tonal" density="compact" class="mb-3">
              <div class="text-caption">
                <strong>Typical setup: 5–15 minutes</strong><br />
                Requires a backend endpoint change. No frontend changes needed if your app already uses a server-side AI layer.
              </div>
            </v-alert>

            <!-- What to do after -->
            <h3 class="text-subtitle-2 font-weight-bold mb-2">3. Verify improvement</h3>
            <p class="text-body-2 text-medium-emphasis mb-0">
              After routing traffic through AI Protector, re-run this benchmark to compare results.
            </p>
          </v-card-text>
          <v-card-actions>
            <v-spacer />
            <v-btn variant="text" @click="showSetupDialog = false">Close</v-btn>
            <v-btn
              color="primary"
              variant="flat"
              prepend-icon="mdi-replay"
              :loading="isRerunning"
              @click="showSetupDialog = false; onRerun()"
            >
              Re-run Benchmark
            </v-btn>
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
import { humanCategory, severityMeta, humanPack, scoreLabel, baselineScoreLabel, classifyRun } from '~/utils/redTeamLabels'

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
const showSetupDialog = ref(false)
const policyApplied = ref(false)
const _rerunPolicy = ref('Strict')
const isRerunning = ref(false)

// ---------------------------------------------------------------------------
// Computed — target label
// ---------------------------------------------------------------------------

const TARGET_LABELS: Record<string, { label: string; icon: string }> = {
  demo_agent: { label: 'Demo Endpoint', icon: 'mdi-robot-outline' },
  demo: { label: 'Demo Endpoint', icon: 'mdi-robot-outline' },
  registered_agent: { label: 'Registered Endpoint', icon: 'mdi-shield-check' },
  local_agent: { label: 'Local Endpoint', icon: 'mdi-laptop' },
  hosted_endpoint: { label: 'Your Endpoint', icon: 'mdi-cloud-outline' },
}

const targetMeta = computed(() => TARGET_LABELS[run.value?.target_type ?? ''] ?? { label: run.value?.target_type ?? 'Agent', icon: 'mdi-robot-outline' })
const targetLabel = computed(() => targetMeta.value.label)
const targetIcon = computed(() => targetMeta.value.icon)

// ---------------------------------------------------------------------------
// Computed — run classification (baseline vs protected)
// ---------------------------------------------------------------------------

const runClass = computed(() => run.value ? classifyRun(run.value) : null)
const isBaseline = computed(() => runClass.value?.type === 'baseline')

// ---------------------------------------------------------------------------
// Computed — score (uses baseline labels for unprotected runs)
// ---------------------------------------------------------------------------

const scoreMeta = computed(() => {
  const score = run.value?.score_simple ?? 0
  return isBaseline.value ? baselineScoreLabel(score) : scoreLabel(score)
})

const criticalCount = computed(() => {
  return scenarios.value.filter(
    (s) => s.passed === false && (s.severity === 'critical' || s.severity === 'high'),
  ).length
})

const failedCount = computed(() => {
  return scenarios.value.filter((s) => s.passed === false).length
})

const _safeOutcomeCount = computed(() => {
  // For baseline runs: safe outcomes = passed count
  // We cannot attribute whether safe outcomes came from model resistance or no-breach;
  // show the combined number with a clear label.
  return run.value?.passed ?? 0
})

const skippedMutating = computed(() => {
  return run.value?.skipped_reasons?.safe_mode ?? 0
})

// ---------------------------------------------------------------------------
// Score interpretation — one-sentence narrative
// ---------------------------------------------------------------------------

const scoreInterpretation = computed(() => {
  const score = run.value?.score_simple ?? 0
  const cats = categoryBars.value
  // Find weakest and strongest categories
  const weakest = cats.length > 0 ? cats[0] : null // sorted worst-first
  const strongest = cats.length > 1 ? cats[cats.length - 1] : null

  // Baseline runs — honest framing, no false comfort
  if (isBaseline.value) {
    if (score >= 90) return 'The model produced safe outcomes for most scenarios, but these reflect baseline model behavior — not enforced runtime protection. Set up AI Protector and re-run to verify active controls.'
    if (score >= 80) {
      if (weakest) return `${weakest.label} remains weak in this baseline. Some scenarios avoided breach, but these outcomes reflect model behavior — not active protection.`
      return 'Most scenarios had safe outcomes, but model resistance alone is not verified runtime protection. Set up protection and re-run.'
    }
    if (score >= 60) {
      const parts: string[] = []
      if (weakest && weakest.percent < 50) parts.push(`${weakest.label} is largely undefended in this baseline.`)
      if (strongest && strongest.percent >= 80) parts.push(`${strongest.label} saw some model resistance, but not enforced protection.`)
      return parts.length ? parts.join(' ') + ' No active protection was measured.' : 'Mixed baseline results — no active protection was measured in this run.'
    }
    if (weakest) return `The model failed to resist most attacks. ${weakest.label} is the most exposed area. Set up AI Protector and re-run.`
    return 'Multiple attack categories bypassed the model. Set up AI Protector and re-run.'
  }

  // Protected runs — original interpretation
  if (score >= 90) return 'Your endpoint handled all major attack categories well.'
  if (score >= 80) {
    if (weakest) return `Most attacks were blocked. ${weakest.label} has room for improvement.`
    return 'Most attacks were blocked. Minor gaps remain.'
  }
  if (score >= 60) {
    const parts: string[] = []
    if (weakest && weakest.percent < 50) parts.push(`${weakest.label} protections are weak.`)
    if (strongest && strongest.percent >= 80) parts.push(`${strongest.label} controls performed well.`)
    return parts.length ? parts.join(' ') : 'Some attack categories need hardening.'
  }
  if (weakest) return `Significant gaps detected. ${weakest.label} is the most exposed area.`
  return 'Multiple attack categories bypassed defenses. Immediate hardening recommended.'
})

// ---------------------------------------------------------------------------
// Failure impact hints — short risk descriptions
// ---------------------------------------------------------------------------

const CATEGORY_IMPACT: Record<string, string> = {
  prompt_injection_jailbreak: 'Could expose system prompt or bypass instructions',
  data_leakage_pii: 'May leak sensitive data or PII in responses',
  tool_abuse: 'Could trigger unauthorized tool calls',
  access_control: 'Bypasses role or permission boundaries',
}

function failureImpact(fail: ScenarioResult): string {
  if (fail.severity === 'critical' || fail.severity === 'high') {
    return CATEGORY_IMPACT[fail.category] ?? 'Likely to recur in production'
  }
  return ''
}

// Mitigation label — tells user which ones are easy to fix
const CATEGORY_MITIGATION: Record<string, string> = {
  prompt_injection_jailbreak: 'Can be mitigated by strict profile',
  data_leakage_pii: 'Can be mitigated by strict profile',
  tool_abuse: 'Needs custom rule',
  access_control: 'Needs custom rule',
}

const BASELINE_CATEGORY_MITIGATION: Record<string, string> = {
  prompt_injection_jailbreak: 'Can be mitigated by strict profile',
  data_leakage_pii: 'Can be mitigated by strict profile',
  tool_abuse: 'Can be mitigated by custom rule',
  access_control: 'Can be mitigated by custom rule',
}

function failureMitigation(fail: ScenarioResult): string {
  if (isBaseline.value) {
    return BASELINE_CATEGORY_MITIGATION[fail.category] ?? ''
  }
  return CATEGORY_MITIGATION[fail.category] ?? ''
}

const _targetEndpointUrl = computed(() => {
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

const protectedBaseUrl = computed(() => {
  const base = window?.location?.origin ?? 'https://your-ai-protector.example.com'
  return `${base}/v1/proxy/chat`
})

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
  width: 80px;
  height: 80px;
  border-radius: 50%;
  border: 5px solid;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.score-value {
  font-size: 1.8rem;
  font-weight: 700;
  line-height: 1;
}

.failure-id {
  font-family: monospace;
  font-size: 0.85em;
  letter-spacing: -0.02em;
}

.baseline-guardrail-note {
  // Ensure readable contrast on the explanation note
  :deep(.v-alert__content) {
    opacity: 1;
  }
}
</style>
