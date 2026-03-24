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

        <div class="d-flex align-center mb-2">
          <span class="text-h5 mr-3">{{ scenario.scenario_id }}</span>
          <v-chip
            :color="scenario.passed ? 'success' : 'error'"
            variant="tonal"
            size="small"
            :prepend-icon="scenario.passed ? 'mdi-check-circle' : 'mdi-close-circle'"
            data-testid="status-chip"
          >
            {{ scenario.passed ? 'Passed' : 'Failed' }}
          </v-chip>
        </div>

        <div class="d-flex flex-wrap ga-3 text-body-2 text-medium-emphasis">
          <span>
            <v-icon icon="mdi-tag" size="x-small" class="mr-1" />
            {{ scenario.category }}
          </span>
          <span>
            <v-icon icon="mdi-alert" size="x-small" class="mr-1" />
            {{ scenario.severity }}
          </span>
          <span v-if="scenario.latency_ms !== null">
            <v-icon icon="mdi-timer-outline" size="x-small" class="mr-1" />
            {{ scenario.latency_ms }}ms
          </span>
          <span>
            Expected: <strong>{{ scenario.expected }}</strong>
            → Got: <strong>{{ scenario.actual ?? 'N/A' }}</strong>
          </span>
        </div>
      </div>

      <!-- Result summary — always visible -->
      <v-alert
        :type="scenario.passed ? 'success' : 'error'"
        variant="tonal"
        class="mb-6"
        data-testid="result-summary"
      >
        <strong>{{ verdictText }}</strong>
      </v-alert>

      <!-- Attack prompt -->
      <h2 class="text-h6 mb-2">Attack Prompt</h2>
      <v-card variant="flat" class="mb-6">
        <v-card-text class="pa-0 position-relative">
          <v-btn
            icon="mdi-content-copy"
            variant="text"
            size="x-small"
            class="copy-btn"
            data-testid="copy-prompt-btn"
            @click="copyPrompt"
          />
          <pre class="prompt-block pa-4" data-testid="attack-prompt">{{ scenario.prompt }}</pre>
        </v-card-text>
      </v-card>

      <!-- Why it got through -->
      <template v-if="whyItPasses">
        <h2 class="text-h6 mb-2">Why It Got Through</h2>
        <v-card variant="flat" class="mb-6 pa-4" data-testid="why-section">
          <p class="text-body-2">{{ whyItPasses }}</p>
        </v-card>
      </template>

      <!-- How to fix it -->
      <template v-if="fixHints.length > 0">
        <h2 class="text-h6 mb-2">How to Fix It</h2>
        <v-card variant="flat" class="mb-6 pa-4" data-testid="fix-section">
          <v-list density="compact">
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

      <!-- Technical Details — collapsed by default -->
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
import { api } from '~/services/api'

definePageMeta({ layout: 'default' })

const route = useRoute()
const runId = computed(() => route.params.id as string)
const scenarioId = computed(() => route.params.sid as string)

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ScenarioDetail {
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
  detector_detail: Record<string, unknown> | null
  pipeline_result: Record<string, unknown> | null
  latency_ms: number | null
}

interface FixHint {
  text: string
  link: string | null
}

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

const loading = ref(true)
const scenario = ref<ScenarioDetail | null>(null)
const technicalPanel = ref<string | undefined>(undefined)

// ---------------------------------------------------------------------------
// Computed
// ---------------------------------------------------------------------------

const verdictText = computed(() => {
  if (!scenario.value) return ''
  if (scenario.value.passed) {
    return 'BLOCKED — your agent stopped this attack'
  }
  return 'ALLOWED — this attack got through'
})

// Extract why_it_passes from detector_detail (scenario metadata)
const whyItPasses = computed(() => {
  const detail = scenario.value?.detector_detail
  if (!detail) return null
  return (detail as Record<string, unknown>).why_it_passes as string | null ?? null
})

// Extract fix_hints from detector_detail
const fixHints = computed<FixHint[]>(() => {
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

function inferFixLink(text: string): string | null {
  const lower = text.toLowerCase()
  if (lower.includes('policy') || lower.includes('strict')) return '/policies'
  if (lower.includes('rule') || lower.includes('block pattern')) return '/security-rules'
  return null
}

async function copyPrompt() {
  if (scenario.value?.prompt) {
    await navigator.clipboard.writeText(scenario.value.prompt)
  }
}

// ---------------------------------------------------------------------------
// Fetch
// ---------------------------------------------------------------------------

async function fetchData() {
  loading.value = true
  try {
    const res = await api.get<ScenarioDetail>(
      `/v1/benchmark/runs/${runId.value}/scenarios/${scenarioId.value}`,
    )
    scenario.value = res.data
  } catch {
    scenario.value = null
  } finally {
    loading.value = false
  }
}

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
