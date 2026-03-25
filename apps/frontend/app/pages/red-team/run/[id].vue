<template>
  <v-container fluid class="progress-page">
    <!-- ═══════════════════ Header ═══════════════════ -->
    <div class="mb-5">
      <div class="d-flex align-center mb-2">
        <v-btn
          icon="mdi-arrow-left"
          variant="text"
          size="small"
          class="mr-2"
          :to="'/red-team'"
        />
        <h1 class="text-h5 font-weight-bold">
          {{ headerTitle }}
        </h1>
        <v-chip
          v-if="runClassification"
          :color="runClassification.color"
          :prepend-icon="runClassification.icon"
          variant="tonal"
          size="small"
          class="ml-3"
          label
        >
          {{ runClassification.label }}
        </v-chip>
      </div>
      <div class="d-flex align-center flex-wrap ga-3 text-body-2 text-medium-emphasis">
        <span class="d-flex align-center">
          <v-icon size="16" class="mr-1">mdi-bullseye-arrow</v-icon>
          {{ targetLabel }}
        </span>
        <span class="header-sep">·</span>
        <span class="d-flex align-center">
          <v-icon size="16" class="mr-1">mdi-package-variant-closed</v-icon>
          {{ humanPack(runDetail?.pack ?? '') }}
        </span>
        <span class="header-sep">·</span>
        <span>{{ runDetail?.total_applicable ?? '...' }} scenarios</span>
      </div>
      <div v-if="endpointUrl" class="mt-1 d-flex align-center text-body-2" style="font-family: monospace; color: #1565c0;">
        <v-icon size="16" class="mr-1" color="blue-darken-2">mdi-link-variant</v-icon>
        {{ endpointUrl }}
      </div>
    </div>

    <!-- ═══════════════════ Banners ═══════════════════ -->
    <v-alert
      v-if="disconnected"
      type="warning"
      variant="tonal"
      density="compact"
      class="mb-4"
      data-testid="reconnect-banner"
    >
      Connection lost. Attempting to reconnect...
    </v-alert>

    <v-alert
      v-if="consecutiveFailures >= 3 && !isTerminal"
      type="error"
      variant="tonal"
      density="compact"
      class="mb-4"
      data-testid="target-failure-banner"
    >
      Target stopped responding after {{ completed }} of {{ total }} scenarios. Partial results saved.
      <template #append>
        <v-btn
          variant="text"
          size="small"
          color="error"
          :to="`/red-team/results/${runId}`"
        >
          View Partial Results
        </v-btn>
      </template>
    </v-alert>

    <!-- ═══════════════════ Progress area ═══════════════════ -->
    <v-card variant="flat" class="mb-4 pa-4 progress-card">
      <!-- Run state message -->
      <p class="text-body-2 text-medium-emphasis mb-2">
        {{ runStateMessage }}
      </p>

      <v-progress-linear
        :model-value="progressPercent"
        :color="consecutiveFailures >= 3 ? 'error' : 'primary'"
        height="10"
        rounded
        class="mb-3"
        data-testid="progress-bar"
      />

      <div class="d-flex align-center justify-space-between">
        <span class="text-body-2 font-weight-medium">
          {{ completed }} of {{ total }} scenarios completed
        </span>
        <span class="text-body-2 text-medium-emphasis">
          <template v-if="isTerminal">Completed in {{ elapsedFormatted }}</template>
          <template v-else>
            Elapsed: {{ elapsedFormatted }}
            <template v-if="etaFormatted">&nbsp;·&nbsp;~{{ etaFormatted }} remaining</template>
          </template>
        </span>
      </div>

      <!-- Currently running scenario -->
      <div v-if="currentScenario && !isTerminal" class="currently-running mt-3">
        <v-icon size="14" class="mr-1 spin-icon" color="primary">mdi-loading</v-icon>
        <span class="text-caption">Currently running:</span>
        <span class="text-caption font-weight-medium ml-1">{{ currentScenario }}</span>
      </div>
    </v-card>

    <!-- ═══════════════════ Summary strip ═══════════════════ -->
    <div v-if="feedItems.length > 0" class="summary-strip mb-4">
      <div
        v-for="s in summaryCountsFiltered"
        :key="s.status"
        class="summary-chip"
        :style="{ '--chip-color': s.meta.color }"
      >
        <v-icon :color="s.meta.vuetifyColor" size="16" class="mr-1">{{ s.meta.mdiIcon }}</v-icon>
        <span class="text-body-2">
          <strong>{{ s.count }}</strong>
          {{ isBaseline ? s.meta.baselineLabel : s.meta.label }}
        </span>
      </div>
    </div>

    <!-- ═══════════════════ Live feed ═══════════════════ -->
    <v-card variant="flat" class="mb-4 feed-card">
      <v-card-title class="text-subtitle-1 pa-4 pb-2 d-flex align-center">
        <v-icon size="20" class="mr-2">mdi-format-list-bulleted</v-icon>
        Live Feed
        <v-spacer />
        <span class="text-caption text-medium-emphasis">{{ feedItems.length }} events</span>
      </v-card-title>

      <v-divider />

      <div
        ref="feedListEl"
        class="feed-list"
        data-testid="live-feed"
      >
        <!-- Empty state -->
        <div v-if="feedItems.length === 0" class="feed-empty text-medium-emphasis text-body-2 pa-6 text-center">
          <v-icon size="32" class="mb-2" color="grey">mdi-timer-sand</v-icon>
          <p class="mb-0">Waiting for scenarios to begin...</p>
        </div>

        <!-- Feed rows -->
        <div
          v-for="item in feedItems"
          :key="item.key"
          class="feed-row"
          :class="[
            `feed-row--${item.status}`,
            { 'feed-row--clickable': item.status !== 'running' },
          ]"
        >
          <div class="feed-row__icon">
            <v-icon
              :color="item.resultMeta.vuetifyColor"
              :class="{ 'spin-icon': item.status === 'running' }"
              size="20"
            >
              {{ item.resultMeta.mdiIcon }}
            </v-icon>
          </div>
          <div class="feed-row__body">
            <div class="feed-row__title text-body-2">
              <span class="feed-row__id text-medium-emphasis">{{ item.scenarioId }}</span>
              <span v-if="item.title" class="feed-row__sep text-medium-emphasis"> · </span>
              <span class="font-weight-medium">{{ item.title }}</span>
            </div>
            <div class="feed-row__detail text-caption" :style="{ color: item.resultMeta.color }">
              {{ item.resultLabel }}
              <span v-if="item.latencyMs" class="text-medium-emphasis"> · {{ item.latencyMs }}ms</span>
            </div>
          </div>
        </div>
      </div>
    </v-card>

    <!-- ═══════════════════ Completed state ═══════════════════ -->
    <v-card v-if="isTerminal" variant="tonal" color="success" class="mb-4 pa-4 text-center completed-card">
      <v-icon size="36" class="mb-2" color="success">mdi-check-circle</v-icon>
      <p class="text-body-1 font-weight-medium mb-1">
        Benchmark complete
      </p>
      <p class="text-body-2 text-medium-emphasis mb-3">
        All scenarios have been evaluated. Review the results to see what got through.
      </p>
      <v-btn
        color="success"
        variant="flat"
        :to="`/red-team/results/${runId}`"
        prepend-icon="mdi-chart-box-outline"
        size="large"
      >
        View Results
      </v-btn>
    </v-card>

    <!-- ═══════════════════ Cancel button ═══════════════════ -->
    <div v-if="!isTerminal" class="d-flex justify-center">
      <v-btn
        color="error"
        variant="outlined"
        prepend-icon="mdi-stop-circle-outline"
        :loading="isCancelling"
        data-testid="cancel-btn"
        @click="showCancelDialog = true"
      >
        Cancel Benchmark
      </v-btn>
    </div>

    <!-- Cancel confirmation dialog -->
    <v-dialog v-model="showCancelDialog" max-width="400">
      <v-card>
        <v-card-title>Cancel Benchmark?</v-card-title>
        <v-card-text>
          Partial results will be saved. You can view them after cancelling.
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="showCancelDialog = false">Keep Running</v-btn>
          <v-btn color="error" variant="flat" :loading="isCancelling" @click="onConfirmCancel">
            Cancel Benchmark
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup lang="ts">
import { api } from '~/services/api'
import {
  humanPack,
  classifyRun as classifyRunType,
  liveResultMeta,
  classifyScenarioResult,
  humanSkipReason,
  type RunClassification,
  type LiveResultStatus,
  type LiveResultMeta,
} from '~/utils/redTeamLabels'

definePageMeta({ layout: 'default' })

const route = useRoute()
const router = useRouter()
const runId = computed(() => route.params.id as string)

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

interface RunDetail {
  id: string
  pack: string
  status: string
  target_type: string
  target_config?: Record<string, string>
  total_in_pack: number
  total_applicable: number
  executed: number
  passed: number
  failed: number
  skipped: number
  score_simple?: number | null
}

interface FeedItem {
  key: string
  scenarioId: string
  title: string
  resultMeta: LiveResultMeta
  resultLabel: string
  latencyMs: number | null
  status: 'running' | 'passed' | 'failed' | 'skipped'
}

const runDetail = ref<RunDetail | null>(null)
const feedItems = ref<FeedItem[]>([])
const completed = ref(0)
const total = ref(0)
const elapsedSeconds = ref(0)
const disconnected = ref(false)
const showCancelDialog = ref(false)
const isCancelling = ref(false)
const isTerminal = ref(false)
const latencies = ref<number[]>([])
const consecutiveFailures = ref(0)
const currentScenario = ref<string | null>(null)
const feedListEl = ref<HTMLElement | null>(null)

// Summary counters
const blockedCount = ref(0)
const gotThroughCount = ref(0)
const skippedCount = ref(0)

// Timers
let elapsedTimer: ReturnType<typeof setInterval> | null = null
let eventSource: EventSource | null = null
let reconnectTimer: ReturnType<typeof setTimeout> | null = null

// ---------------------------------------------------------------------------
// Computed
// ---------------------------------------------------------------------------

const progressPercent = computed(() => {
  if (total.value === 0) return 0
  return Math.round((completed.value / total.value) * 100)
})

const headerTitle = computed(() => {
  if (isTerminal.value) return 'Benchmark Complete'
  return `Running ${humanPack(runDetail.value?.pack ?? '')} Benchmark`
})

const targetLabel = computed(() => {
  const t = runDetail.value?.target_type
  if (t === 'demo') return 'Demo Endpoint'
  if (t === 'local_agent') return 'Local Agent'
  if (t === 'hosted_endpoint') return 'Hosted Endpoint'
  if (t === 'registered_agent') return 'Protected Agent'
  return t ?? 'Target'
})

const endpointUrl = computed(() => runDetail.value?.target_config?.endpoint_url ?? '')

const runClassification = computed<RunClassification | null>(() => {
  if (!runDetail.value) return null
  return classifyRunType(runDetail.value as unknown as import('~/services/benchmarkService').RunDetail)
})

const isBaseline = computed(() => runClassification.value?.type === 'baseline')

const elapsedFormatted = computed(() => formatDuration(elapsedSeconds.value))

const etaFormatted = computed(() => {
  if (latencies.value.length === 0 || completed.value >= total.value) return null
  const avgMs = latencies.value.reduce((a, b) => a + b, 0) / latencies.value.length
  const remaining = total.value - completed.value
  const etaSec = Math.round((remaining * avgMs) / 1000)
  return formatDuration(etaSec)
})

const runStateMessage = computed(() => {
  if (isTerminal.value) return `${humanPack(runDetail.value?.pack ?? '')} benchmark complete — all scenarios evaluated.`
  if (completed.value === 0) return `Running ${humanPack(runDetail.value?.pack ?? '')} benchmark — evaluating scenarios in real time.`
  if (consecutiveFailures.value >= 3) return 'Target may be unreachable. Waiting for recovery…'
  return `Running ${humanPack(runDetail.value?.pack ?? '')} benchmark — analyzing each response.`
})

const summaryCountsFiltered = computed(() => {
  const items: { status: LiveResultStatus; count: number; meta: LiveResultMeta }[] = []
  if (blockedCount.value > 0) items.push({ status: 'blocked', count: blockedCount.value, meta: liveResultMeta('blocked') })
  if (gotThroughCount.value > 0) items.push({ status: 'got_through', count: gotThroughCount.value, meta: liveResultMeta('got_through') })
  if (skippedCount.value > 0) items.push({ status: 'skipped', count: skippedCount.value, meta: liveResultMeta('skipped') })
  return items
})

function formatDuration(sec: number): string {
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return m > 0 ? `${m}m ${s}s` : `${s}s`
}

/**
 * Build the human-readable label for a completed scenario, respecting baseline vs protected.
 */
function buildResultLabel(passed: boolean, actual?: string | null): string {
  const status = classifyScenarioResult(passed, actual)
  const meta = liveResultMeta(status)
  return isBaseline.value ? meta.baselineLabel : meta.label
}

// ---------------------------------------------------------------------------
// SSE connection
// ---------------------------------------------------------------------------

function connectSSE() {
  const baseURL = import.meta.env.NUXT_PUBLIC_API_BASE ?? 'http://localhost:8000'
  const url = `${baseURL}/v1/benchmark/runs/${runId.value}/progress`

  eventSource = new EventSource(url)
  disconnected.value = false

  eventSource.addEventListener('scenario_start', (e: MessageEvent) => {
    const data = JSON.parse(e.data)
    total.value = data.total_applicable
    currentScenario.value = data.title ? `${data.scenario_id} · ${data.title}` : data.scenario_id

    // Remove previous "running" item for same scenario
    const idx = feedItems.value.findIndex((f) => f.scenarioId === data.scenario_id && f.status === 'running')
    if (idx === -1) {
      const meta = liveResultMeta('running')
      feedItems.value.push({
        key: `start-${data.scenario_id}`,
        scenarioId: data.scenario_id,
        title: data.title || '',
        resultMeta: meta,
        resultLabel: 'Running…',
        latencyMs: null,
        status: 'running',
      })
    }
    scrollToBottom()
  })

  eventSource.addEventListener('scenario_complete', (e: MessageEvent) => {
    const data = JSON.parse(e.data)
    completed.value++
    latencies.value.push(data.latency_ms)
    currentScenario.value = null

    // Track consecutive failures
    if (data.passed) {
      consecutiveFailures.value = 0
      blockedCount.value++
    } else {
      consecutiveFailures.value++
      gotThroughCount.value++
    }

    const status = classifyScenarioResult(data.passed, data.actual)
    const meta = liveResultMeta(status)
    const label = buildResultLabel(data.passed, data.actual)

    const idx = feedItems.value.findIndex((f) => f.scenarioId === data.scenario_id && f.status === 'running')
    const item: FeedItem = {
      key: `complete-${data.scenario_id}`,
      scenarioId: data.scenario_id,
      title: data.title || '',
      resultMeta: meta,
      resultLabel: label,
      latencyMs: data.latency_ms,
      status: data.passed ? 'passed' : 'failed',
    }
    if (idx >= 0) {
      feedItems.value.splice(idx, 1, item)
    } else {
      feedItems.value.push(item)
    }
    scrollToBottom()
  })

  eventSource.addEventListener('scenario_skipped', (e: MessageEvent) => {
    const data = JSON.parse(e.data)
    completed.value++
    currentScenario.value = null
    skippedCount.value++

    const meta = liveResultMeta('skipped')
    const skipLabel = humanSkipReason(data.reason ?? 'unknown')

    const idx = feedItems.value.findIndex((f) => f.scenarioId === data.scenario_id && f.status === 'running')
    const item: FeedItem = {
      key: `skipped-${data.scenario_id}`,
      scenarioId: data.scenario_id,
      title: data.title || '',
      resultMeta: meta,
      resultLabel: `Skipped — ${skipLabel}`,
      latencyMs: null,
      status: 'skipped',
    }
    if (idx >= 0) {
      feedItems.value.splice(idx, 1, item)
    } else {
      feedItems.value.push(item)
    }
    scrollToBottom()
  })

  eventSource.addEventListener('run_complete', (e: MessageEvent) => {
    const data = JSON.parse(e.data)
    isTerminal.value = true
    completed.value = data.executed + data.skipped
    total.value = data.total_applicable
    stopTimers()
    closeSSE()

    // Give user time to see the completion state before redirecting
    setTimeout(() => {
      router.push(`/red-team/results/${runId.value}`)
    }, 4000)
  })

  eventSource.addEventListener('run_failed', (e: MessageEvent) => {
    const data = JSON.parse(e.data)
    isTerminal.value = true
    stopTimers()
    closeSSE()

    const meta = liveResultMeta('inconclusive')
    feedItems.value.push({
      key: 'run-failed',
      scenarioId: 'ERROR',
      title: 'Run failed',
      resultMeta: meta,
      resultLabel: data.error,
      latencyMs: null,
      status: 'failed',
    })
  })

  eventSource.addEventListener('run_cancelled', (_: MessageEvent) => {
    isTerminal.value = true
    stopTimers()
    closeSSE()

    setTimeout(() => {
      router.push(`/red-team/results/${runId.value}`)
    }, 1000)
  })

  eventSource.onerror = () => {
    disconnected.value = true
    closeSSE()

    reconnectTimer = setTimeout(() => {
      fallbackPoll()
    }, 3000)
  }
}

function closeSSE() {
  if (eventSource) {
    eventSource.close()
    eventSource = null
  }
}

// ---------------------------------------------------------------------------
// Fallback polling
// ---------------------------------------------------------------------------

async function fallbackPoll() {
  try {
    const res = await api.get<RunDetail>(`/v1/benchmark/runs/${runId.value}`)
    const run = res.data
    runDetail.value = run

    if (['completed', 'failed', 'cancelled'].includes(run.status)) {
      disconnected.value = false
      isTerminal.value = true
      stopTimers()
      if (run.status === 'completed') {
        router.push(`/red-team/results/${runId.value}`)
      }
    } else {
      connectSSE()
    }
  } catch {
    reconnectTimer = setTimeout(fallbackPoll, 5000)
  }
}

// ---------------------------------------------------------------------------
// Cancel
// ---------------------------------------------------------------------------

async function onConfirmCancel() {
  isCancelling.value = true
  showCancelDialog.value = false
  try {
    await api.delete(`/v1/benchmark/runs/${runId.value}`)
    setTimeout(() => {
      if (!isTerminal.value) {
        router.push(`/red-team/results/${runId.value}`)
      }
    }, 2000)
  } catch {
    isCancelling.value = false
  }
}

// ---------------------------------------------------------------------------
// Timers & lifecycle
// ---------------------------------------------------------------------------

function scrollToBottom() {
  nextTick(() => {
    const el = feedListEl.value ?? document.querySelector('[data-testid="live-feed"]')
    if (el) el.scrollTop = el.scrollHeight
  })
}

function stopTimers() {
  if (elapsedTimer) {
    clearInterval(elapsedTimer)
    elapsedTimer = null
  }
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
}

async function fetchRunDetail() {
  try {
    const res = await api.get<RunDetail>(`/v1/benchmark/runs/${runId.value}`)
    runDetail.value = res.data
    total.value = res.data.total_applicable
    completed.value = res.data.executed + res.data.skipped

    if (['completed', 'failed', 'cancelled'].includes(res.data.status)) {
      isTerminal.value = true
      if (res.data.status === 'completed') {
        router.push(`/red-team/results/${runId.value}`)
      }
      return
    }

    connectSSE()
    elapsedTimer = setInterval(() => {
      elapsedSeconds.value++
    }, 1000)
  } catch {
    router.push('/red-team')
  }
}

onMounted(() => {
  fetchRunDetail()
})

onBeforeUnmount(() => {
  stopTimers()
  closeSSE()
})
</script>

<style lang="scss" scoped>
.progress-page {
  max-width: 780px;
  margin: 0 auto;
}

.header-sep {
  opacity: 0.4;
}

// Progress card
.progress-card {
  border: 1px solid rgba(var(--v-border-color), 0.12);
}

// Summary strip
.summary-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  padding: 10px 16px;
  background: rgba(var(--v-theme-surface-variant), 0.35);
  border-radius: 8px;
}

.summary-chip {
  display: flex;
  align-items: center;
  gap: 2px;
}

// Feed card
.feed-card {
  border: 1px solid rgba(var(--v-border-color), 0.12);
}

.feed-list {
  max-height: 460px;
  overflow-y: auto;
  padding: 0;
}

.feed-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
}

// Feed rows
// Currently running indicator
.currently-running {
  display: flex;
  align-items: center;
  padding: 6px 10px;
  background: rgba(var(--v-theme-primary), 0.06);
  border-radius: 6px;
  border-left: 3px solid rgb(var(--v-theme-primary));
}

// Feed rows
.feed-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(var(--v-border-color), 0.08);
  transition: background 0.15s ease;

  &:last-child {
    border-bottom: none;
  }
}

.feed-row--clickable {
  cursor: pointer;

  &:hover {
    background: rgba(var(--v-theme-primary), 0.04);
  }
}

.feed-row--running {
  background: rgba(var(--v-theme-primary), 0.05);
  border-left: 3px solid rgb(var(--v-theme-primary));
  padding-left: 13px; // compensate for border
}

.feed-row--failed {
  background: rgba(var(--v-theme-error), 0.03);
}

.feed-row__icon {
  flex-shrink: 0;
  width: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding-top: 1px;
}

.feed-row__body {
  flex: 1;
  min-width: 0;
}

.feed-row__title {
  line-height: 1.5;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.feed-row__id {
  font-family: monospace;
  font-size: 0.8em;
  letter-spacing: -0.02em;
}

.feed-row__sep {
  opacity: 0.5;
}

.feed-row__detail {
  line-height: 1.5;
  margin-top: 2px;
}

// Completed card
.completed-card {
  border: 1px solid rgba(var(--v-theme-success), 0.2);
}

// Spinning loader icon
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.spin-icon {
  animation: spin 1s linear infinite;
}
</style>
