<template>
  <v-container fluid class="progress-page">
    <!-- Header info bar -->
    <div class="mb-4">
      <div class="d-flex align-center mb-1">
        <v-btn
          icon="mdi-arrow-left"
          variant="text"
          size="small"
          class="mr-2"
          :to="'/red-team'"
        />
        <h1 class="text-h5">
          {{ headerTitle }}
        </h1>
      </div>
      <p class="text-body-2 text-medium-emphasis">
        Target: {{ targetLabel }} &nbsp;│&nbsp; Pack: {{ humanPack(runDetail?.pack ?? '') }}
        &nbsp;│&nbsp; {{ runDetail?.total_applicable ?? '...' }} attacks
      </p>
    </div>

    <!-- Reconnection banner -->
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

    <!-- Mid-run failure banner -->
    <v-alert
      v-if="consecutiveFailures >= 3 && !isTerminal"
      type="error"
      variant="tonal"
      density="compact"
      class="mb-4"
      data-testid="target-failure-banner"
    >
      Target stopped responding after {{ completed }}/{{ total }} scenarios. Partial results saved.
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

    <!-- Progress bar -->
    <v-card variant="flat" class="mb-4 pa-4">
      <div class="d-flex align-center justify-space-between mb-2">
        <span class="text-body-2 font-weight-medium">
          {{ completed }} / {{ total }} ({{ progressPercent }}%)
        </span>
        <span class="text-body-2 text-medium-emphasis">
          {{ elapsedFormatted }}
          <template v-if="etaFormatted">&nbsp;·&nbsp;~{{ etaFormatted }} remaining</template>
        </span>
      </div>
      <v-progress-linear
        :model-value="progressPercent"
        :color="consecutiveFailures >= 3 ? 'error' : 'primary'"
        height="8"
        rounded
        data-testid="progress-bar"
      />
      <!-- Currently running scenario -->
      <p v-if="currentScenario" class="text-caption text-medium-emphasis mt-2 mb-0">
        Running now: {{ currentScenario }}
      </p>
    </v-card>

    <!-- Live feed -->
    <v-card variant="flat" class="mb-4">
      <v-card-title class="text-subtitle-1 pa-4 pb-2">Live Feed</v-card-title>
      <v-list
        ref="feedList"
        class="feed-list"
        density="compact"
        data-testid="live-feed"
      >
        <v-list-item
          v-if="feedItems.length === 0"
          class="text-medium-emphasis text-body-2"
        >
          Waiting for scenarios to begin...
        </v-list-item>
        <v-list-item
          v-for="item in feedItems"
          :key="item.key"
          :class="{ 'feed-item--running': item.status === 'running' }"
        >
          <template #prepend>
            <span class="feed-icon mr-2">{{ item.icon }}</span>
          </template>
          <v-list-item-title class="text-body-2">
            {{ item.title || item.scenarioId }}
            <span v-if="item.title" class="text-caption text-medium-emphasis ml-1">{{ item.scenarioId }}</span>
          </v-list-item-title>
          <v-list-item-subtitle class="text-caption">
            {{ item.detail }}
          </v-list-item-subtitle>
        </v-list-item>
      </v-list>
    </v-card>

    <!-- Cancel button -->
    <div class="d-flex justify-center">
      <v-btn
        v-if="!isTerminal"
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
import { humanPack } from '~/utils/redTeamLabels'

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
  icon: string
  detail: string
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
  if (isTerminal.value) return 'Benchmark Complete!'
  return 'Benchmark Running...'
})

const targetLabel = computed(() => {
  const t = runDetail.value?.target_type
  if (t === 'demo') return 'Demo Agent'
  if (t === 'local_agent') return 'Local Agent'
  if (t === 'hosted_endpoint') return 'Hosted Endpoint'
  return t ?? 'Target'
})

const elapsedFormatted = computed(() => formatDuration(elapsedSeconds.value))

const etaFormatted = computed(() => {
  if (latencies.value.length === 0 || completed.value >= total.value) return null
  const avgMs = latencies.value.reduce((a, b) => a + b, 0) / latencies.value.length
  const remaining = total.value - completed.value
  const etaSec = Math.round((remaining * avgMs) / 1000)
  return formatDuration(etaSec)
})

function formatDuration(sec: number): string {
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return m > 0 ? `${m}m ${s}s` : `${s}s`
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
    currentScenario.value = data.title || data.scenario_id

    // Remove previous "running" item for same scenario
    const idx = feedItems.value.findIndex((f) => f.scenarioId === data.scenario_id && f.status === 'running')
    if (idx === -1) {
      feedItems.value.push({
        key: `start-${data.scenario_id}`,
        scenarioId: data.scenario_id,
        title: data.title || '',
        icon: '🔄',
        detail: `Running (${data.index}/${data.total_applicable})`,
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

    // Track consecutive failures for mid-run error detection
    if (data.passed) {
      consecutiveFailures.value = 0
    } else {
      consecutiveFailures.value++
    }

    // Replace the running item
    const idx = feedItems.value.findIndex((f) => f.scenarioId === data.scenario_id && f.status === 'running')
    const item: FeedItem = {
      key: `complete-${data.scenario_id}`,
      scenarioId: data.scenario_id,
      title: data.title || '',
      icon: data.passed ? '✅' : '❌',
      detail: `${data.passed ? 'Blocked' : 'Got through'} · ${data.actual} · ${data.latency_ms}ms`,
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

    // Replace running item if present
    const idx = feedItems.value.findIndex((f) => f.scenarioId === data.scenario_id && f.status === 'running')
    const skipLabel = data.reason === 'timeout' ? 'Timeout' : data.reason === 'safe_mode' ? 'Safe mode' : data.reason === 'not_applicable' ? 'Not applicable' : data.reason
    const item: FeedItem = {
      key: `skipped-${data.scenario_id}`,
      scenarioId: data.scenario_id,
      title: data.title || '',
      icon: data.reason === 'timeout' ? '⏱️' : '⚠️',
      detail: `Skipped — ${skipLabel}`,
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

    // Auto-redirect after brief delay
    setTimeout(() => {
      router.push(`/red-team/results/${runId.value}`)
    }, 1500)
  })

  eventSource.addEventListener('run_failed', (e: MessageEvent) => {
    const data = JSON.parse(e.data)
    isTerminal.value = true
    stopTimers()
    closeSSE()

    feedItems.value.push({
      key: 'run-failed',
      scenarioId: 'ERROR',
      title: '',
      icon: '💥',
      detail: data.error,
      status: 'failed',
    })
  })

  eventSource.addEventListener('run_cancelled', (_: MessageEvent) => {
    isTerminal.value = true
    stopTimers()
    closeSSE()

    // Navigate to results with partial data
    setTimeout(() => {
      router.push(`/red-team/results/${runId.value}`)
    }, 1000)
  })

  eventSource.onerror = () => {
    disconnected.value = true
    closeSSE()

    // Reconnect with backoff
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
      // Still running — try SSE again
      connectSSE()
    }
  } catch {
    // Keep retrying
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
    // SSE should receive run_cancelled, but redirect as safety net
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
    const el = document.querySelector('[data-testid="live-feed"]')
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

    // If already done, skip SSE
    if (['completed', 'failed', 'cancelled'].includes(res.data.status)) {
      isTerminal.value = true
      if (res.data.status === 'completed') {
        router.push(`/red-team/results/${runId.value}`)
      }
      return
    }

    // Start SSE + elapsed timer
    connectSSE()
    elapsedTimer = setInterval(() => {
      elapsedSeconds.value++
    }, 1000)
  } catch {
    // Run not found — back to landing
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
.feed-list {
  max-height: 400px;
  overflow-y: auto;
}

.feed-icon {
  font-size: 1rem;
  width: 24px;
  text-align: center;
}

.feed-item--running {
  background: rgba(var(--v-theme-primary), 0.05);
}
</style>
