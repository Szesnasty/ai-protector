<template>
  <v-container fluid class="scenario-detail-page">
    <!-- Loading -->
    <div v-if="loading" class="d-flex justify-center align-center" style="min-height: 300px;">
      <v-progress-circular indeterminate color="primary" />
    </div>

    <template v-else-if="scenario">
      <!-- Header -->
      <div class="mb-6">
        <v-btn
          variant="text"
          size="small"
          prepend-icon="mdi-arrow-left"
          class="mb-2"
          :to="`/red-team/results/${runId}`"
          data-testid="back-btn"
        >
          Back to Results
        </v-btn>

        <!-- Human title as H1 -->
        <h1 class="text-h5 mb-1">{{ scenario.title || scenario.scenario_id }}</h1>
        <p v-if="scenario.title" class="text-body-2 text-medium-emphasis mb-3">
          {{ scenario.scenario_id }}
        </p>

        <!-- Status + metadata chips -->
        <div class="d-flex flex-wrap ga-2 mb-3">
          <v-chip
            :color="scenario.passed ? 'success' : 'error'"
            variant="tonal"
            size="small"
            :prepend-icon="scenario.passed ? 'mdi-shield-check' : 'mdi-shield-alert'"
            data-testid="status-chip"
          >
            {{ scenario.passed ? 'Blocked' : 'Got through' }}
          </v-chip>
          <v-chip
            :color="sevMeta.color"
            variant="tonal"
            size="small"
            :prepend-icon="sevMeta.icon"
          >
            {{ sevMeta.label }}
          </v-chip>
          <v-chip variant="outlined" size="small" prepend-icon="mdi-tag">
            {{ humanCategory(scenario.category) }}
          </v-chip>
          <v-chip v-if="scenario.latency_ms !== null" variant="outlined" size="small" prepend-icon="mdi-timer-outline">
            {{ scenario.latency_ms }}ms
          </v-chip>
        </div>

        <!-- Description from pack metadata -->
        <p v-if="scenario.description" class="text-body-2 text-medium-emphasis">
          {{ scenario.description }}
        </p>
      </div>

      <!-- Result verdict -->
      <v-alert
        :type="scenario.passed ? 'success' : 'error'"
        variant="tonal"
        class="mb-6"
        data-testid="result-summary"
      >
        <strong>{{ verdictText }}</strong>
        <template v-if="!scenario.passed">
          <br />
          <span class="text-body-2">
            Expected: <strong>{{ scenario.expected }}</strong>
            &nbsp;→&nbsp; Got: <strong>{{ scenario.actual ?? 'ALLOW' }}</strong>
          </span>
        </template>
      </v-alert>

      <!-- Attack Prompt -->
      <h2 class="text-h6 mb-2">Attack Prompt</h2>
      <v-card variant="flat" class="mb-6">
        <v-card-text class="pa-0 position-relative">
          <v-btn
            icon="mdi-content-copy"
            variant="text"
            size="x-small"
            class="copy-btn"
            data-testid="copy-prompt-btn"
            @click="copyText(scenario.prompt)"
          >
            <v-icon icon="mdi-content-copy" />
            <v-tooltip activator="parent" location="top">Copy prompt</v-tooltip>
          </v-btn>
          <pre class="prompt-block pa-4" data-testid="attack-prompt">{{ scenario.prompt }}</pre>
        </v-card-text>
      </v-card>

      <!-- Agent Response (if available) -->
      <template v-if="scenario.actual">
        <h2 class="text-h6 mb-2">Agent Response</h2>
        <v-card variant="flat" class="mb-6">
          <v-card-text class="pa-0 position-relative">
            <v-btn
              icon="mdi-content-copy"
              variant="text"
              size="x-small"
              class="copy-btn"
              data-testid="copy-response-btn"
              @click="copyText(scenario.actual)"
            >
              <v-icon icon="mdi-content-copy" />
              <v-tooltip activator="parent" location="top">Copy response</v-tooltip>
            </v-btn>
            <pre class="prompt-block pa-4" data-testid="agent-response">{{ scenario.actual }}</pre>
          </v-card-text>
        </v-card>
      </template>

      <!-- Why it got through — use enriched API field first -->
      <template v-if="whyItPasses">
        <h2 class="text-h6 mb-2">Why It Got Through</h2>
        <v-card variant="flat" class="mb-6 pa-4" data-testid="why-section">
          <p class="text-body-2">{{ whyItPasses }}</p>
        </v-card>
      </template>

      <!-- How to fix it — use enriched API field first -->
      <template v-if="fixHints.length > 0">
        <h2 class="text-h6 mb-2">How to Fix It</h2>
        <v-card variant="flat" class="mb-6 pa-4" data-testid="fix-section">
          <v-list density="compact" class="bg-transparent">
            <v-list-item
              v-for="(hint, i) in fixHints"
              :key="i"
              class="px-0"
            >
              <template #prepend>
                <v-icon icon="mdi-wrench" size="small" color="primary" class="mr-2" />
              </template>
              <v-list-item-title class="text-body-2">
                <nuxt-link
                  v-if="hint.link"
                  :to="hint.link"
                  class="text-decoration-none text-primary"
                >
                  {{ hint.text }}
                </nuxt-link>
                <span v-else>{{ hint.text }}</span>
              </v-list-item-title>
            </v-list-item>
          </v-list>
        </v-card>
      </template>

      <!-- Prev / Next failure navigation -->
      <div v-if="failures.length > 1" class="d-flex justify-space-between mb-6">
        <v-btn
          v-if="prevFailure"
          variant="text"
          size="small"
          prepend-icon="mdi-chevron-left"
          :to="`/red-team/results/${runId}/scenario/${prevFailure.scenario_id}`"
        >
          {{ prevFailure.title || prevFailure.scenario_id }}
        </v-btn>
        <span v-else />
        <v-btn
          v-if="nextFailure"
          variant="text"
          size="small"
          append-icon="mdi-chevron-right"
          :to="`/red-team/results/${runId}/scenario/${nextFailure.scenario_id}`"
        >
          {{ nextFailure.title || nextFailure.scenario_id }}
        </v-btn>
      </div>

      <!-- Technical Details — collapsed -->
      <v-expansion-panels v-model="technicalPanel" class="mb-6" variant="accordion">
        <v-expansion-panel value="technical" data-testid="technical-details">
          <v-expansion-panel-title>
            <v-icon icon="mdi-code-braces" size="small" class="mr-2" />
            Technical Details
          </v-expansion-panel-title>
          <v-expansion-panel-text>
            <div class="text-body-2">
              <p v-if="scenario.detector_type" class="mb-2">
                <strong>Detector:</strong> {{ scenario.detector_type }}
              </p>
              <template v-if="scenario.detector_detail">
                <p class="mb-1"><strong>Detector Detail:</strong></p>
                <pre class="detail-block pa-3 mb-3">{{ JSON.stringify(scenario.detector_detail, null, 2) }}</pre>
              </template>
              <template v-if="scenario.pipeline_result">
                <p class="mb-1"><strong>Pipeline Result:</strong></p>
                <pre class="detail-block pa-3">{{ JSON.stringify(scenario.pipeline_result, null, 2) }}</pre>
              </template>
              <p v-if="!scenario.detector_detail && !scenario.pipeline_result" class="text-medium-emphasis">
                No detailed pipeline data available for this scenario.
              </p>
            </div>
          </v-expansion-panel-text>
        </v-expansion-panel>
      </v-expansion-panels>
    </template>

    <!-- Error -->
    <v-alert v-else type="error" variant="tonal" class="mt-4">
      Could not load scenario details.
    </v-alert>
  </v-container>
</template>

<script setup lang="ts">
import { benchmarkService } from '~/services/benchmarkService'
import type { ScenarioResult } from '~/services/benchmarkService'
import { humanCategory, severityMeta } from '~/utils/redTeamLabels'

definePageMeta({ layout: 'default' })

const route = useRoute()
const runId = computed(() => route.params.id as string)
const scenarioId = computed(() => route.params.sid as string)

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface FixHint {
  text: string
  link: string | null
}

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

const loading = ref(true)
const scenario = ref<ScenarioResult | null>(null)
const allScenarios = ref<ScenarioResult[]>([])
const technicalPanel = ref<string | undefined>(undefined)

// ---------------------------------------------------------------------------
// Computed
// ---------------------------------------------------------------------------

const sevMeta = computed(() => severityMeta(scenario.value?.severity ?? 'medium'))

const verdictText = computed(() => {
  if (!scenario.value) return ''
  if (scenario.value.passed) {
    return 'BLOCKED — your agent stopped this attack'
  }
  return 'GOT THROUGH — this attack bypassed your agent'
})

// Use enriched API field first, then fall back to detector_detail
const whyItPasses = computed(() => {
  if (scenario.value?.why_it_passes) return scenario.value.why_it_passes
  const detail = scenario.value?.detector_detail
  if (!detail) return null
  return (detail as Record<string, unknown>).why_it_passes as string | null ?? null
})

// Use enriched API field first, then fall back to detector_detail
const fixHints = computed<FixHint[]>(() => {
  const enrichedHints = scenario.value?.fix_hints
  if (enrichedHints && enrichedHints.length > 0) {
    return enrichedHints.map((h) => ({ text: h, link: inferFixLink(h) }))
  }
  const detail = scenario.value?.detector_detail
  if (!detail) return []
  const hints = (detail as Record<string, unknown>).fix_hints
  if (!Array.isArray(hints)) return []
  return hints.map((h: unknown) => {
    if (typeof h === 'string') {
      return { text: h, link: inferFixLink(h) }
    }
    const obj = h as Record<string, string>
    return { text: obj.text ?? String(h), link: obj.link ?? inferFixLink(obj.text ?? '') }
  })
})

// Failures for prev/next navigation
const failures = computed(() => {
  return allScenarios.value.filter((s) => s.passed === false)
})

const currentFailureIndex = computed(() => {
  return failures.value.findIndex((s) => s.scenario_id === scenarioId.value)
})

const prevFailure = computed(() => {
  const idx = currentFailureIndex.value
  return idx > 0 ? failures.value[idx - 1] : null
})

const nextFailure = computed(() => {
  const idx = currentFailureIndex.value
  return idx >= 0 && idx < failures.value.length - 1 ? failures.value[idx + 1] : null
})

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function inferFixLink(text: string): string | null {
  const lower = text.toLowerCase()
  if (lower.includes('policy') || lower.includes('strict')) return '/policies'
  if (lower.includes('rule') || lower.includes('block pattern')) return '/security-rules'
  return null
}

async function copyText(text: string | null | undefined) {
  if (text) {
    await navigator.clipboard.writeText(text)
  }
}

// ---------------------------------------------------------------------------
// Fetch
// ---------------------------------------------------------------------------

async function fetchData() {
  loading.value = true
  try {
    const [scenarioData, scenariosAll] = await Promise.all([
      benchmarkService.getScenario(runId.value, scenarioId.value),
      benchmarkService.getScenarios(runId.value),
    ])
    scenario.value = scenarioData
    allScenarios.value = scenariosAll
  } catch {
    scenario.value = null
  } finally {
    loading.value = false
  }
}

// Re-fetch when route params change (prev/next navigation)
watch([runId, scenarioId], () => {
  fetchData()
})

onMounted(() => {
  fetchData()
})
</script>

<style lang="scss" scoped>
.prompt-block,
.detail-block {
  font-family: 'Fira Code', 'Cascadia Code', monospace;
  font-size: 0.85rem;
  line-height: 1.5;
  background: rgba(var(--v-theme-surface-variant), 0.3);
  border-radius: 8px;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

.copy-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 1;
}
</style>
