<template>
  <div class="detail-row">
    <!-- Loading -->
    <div v-if="loading" class="text-center py-8">
      <v-progress-circular indeterminate color="primary" size="32" />
      <p class="text-body-2 text-medium-emphasis mt-3">Loading trace details…</p>
    </div>

    <template v-else-if="detail">
      <!-- ── SECTION 1: Summary Header ── -->
      <div class="detail-header mb-6">
        <div class="d-flex align-center ga-4 flex-wrap">
          <!-- Status -->
          <v-chip
            :color="isBlocked ? 'error' : 'success'"
            :prepend-icon="isBlocked ? 'mdi-shield-lock' : 'mdi-check-circle'"
            variant="flat"
            size="small"
          >
            {{ isBlocked ? 'BLOCKED' : 'ALLOWED' }}
          </v-chip>
          <!-- Intent -->
          <v-chip v-if="detail.intent" variant="outlined" size="small">
            {{ detail.intent }}
          </v-chip>
          <!-- Role -->
          <v-chip
            :color="detail.user_role === 'admin' ? 'warning' : 'info'"
            variant="tonal"
            size="small"
          >
            {{ detail.user_role }}
          </v-chip>
          <v-spacer />
          <!-- Key metrics inline -->
          <span class="text-caption text-medium-emphasis d-flex align-center ga-3">
            <span><v-icon size="14" class="mr-1">mdi-brain</v-icon>{{ detail.model }}</span>
            <span><v-icon size="14" class="mr-1">mdi-timer-outline</v-icon>{{ detail.total_duration_ms }}ms</span>
            <span><v-icon size="14" class="mr-1">mdi-repeat</v-icon>{{ iterations.length }} iter</span>
          </span>
        </div>
      </div>

      <!-- ── SECTION 2: User Message ── -->
      <div v-if="detail.user_message" class="detail-section mb-5">
        <div class="section-label mb-2">
          <v-icon size="16" class="mr-1">mdi-account-arrow-right</v-icon>
          User Message
        </div>
        <div class="message-block message-user">
          {{ detail.user_message }}
        </div>
      </div>

      <!-- ── SECTION 3: Final Response ── -->
      <div v-if="detail.final_response" class="detail-section mb-5">
        <div class="section-label mb-2">
          <v-icon size="16" class="mr-1">mdi-robot-outline</v-icon>
          Final Response
        </div>
        <div class="message-block message-response">
          {{ detail.final_response }}
        </div>
      </div>

      <!-- ── SECTION 4: Iterations ── -->
      <div v-if="iterations.length" class="detail-section mb-5">
        <div class="section-label mb-3">
          <v-icon size="16" class="mr-1">mdi-layers-outline</v-icon>
          Iterations ({{ iterations.length }})
        </div>
        <v-expansion-panels variant="accordion" class="iteration-panels">
          <v-expansion-panel
            v-for="(iter, idx) in iterations"
            :key="idx"
            class="iteration-panel"
          >
            <v-expansion-panel-title class="iteration-title">
              <div class="d-flex align-center ga-3 flex-grow-1">
                <v-icon size="20" color="primary">mdi-repeat</v-icon>
                <span class="text-body-2 font-weight-bold">Iteration {{ iter.iteration ?? idx + 1 }}</span>
                <v-chip v-if="iterToolCount(iter)" size="x-small" variant="tonal" color="info">
                  <v-icon start size="12">mdi-wrench</v-icon>
                  {{ iterToolCount(iter) }} tool{{ iterToolCount(iter) > 1 ? 's' : '' }}
                </v-chip>
                <v-chip v-if="iterHasBlock(iter)" size="small" variant="flat" color="error" class="font-weight-bold">
                  <v-icon start size="14">mdi-shield-lock</v-icon>
                  BLOCKED
                </v-chip>
              </div>
            </v-expansion-panel-title>
            <v-expansion-panel-text>
              <div class="pa-2">
                <!-- Pre-tool decisions -->
                <div v-if="iter.pre_tool_decisions?.length" class="iter-subsection mb-4">
                  <div class="subsection-label mb-2">
                    <v-icon size="14" class="mr-1">mdi-shield-check-outline</v-icon>
                    Pre-tool Gate
                  </div>
                  <div v-for="(d, di) in iter.pre_tool_decisions" :key="di" class="d-flex align-center ga-2 mb-2">
                    <v-chip :color="decisionColor(d.decision)" size="x-small" variant="flat">{{ d.decision }}</v-chip>
                    <span class="text-body-2">{{ d.tool }}</span>
                    <span v-if="d.reason" class="text-caption text-medium-emphasis">— {{ d.reason }}</span>
                  </div>
                </div>

                <!-- Tool executions -->
                <div v-if="iter.tool_executions?.length" class="iter-subsection mb-4">
                  <div class="subsection-label mb-2">
                    <v-icon size="14" class="mr-1">mdi-wrench</v-icon>
                    Tool Executions
                  </div>
                  <div v-for="(t, ti) in iter.tool_executions" :key="ti" class="tool-exec-row mb-3">
                    <div class="d-flex align-center ga-2">
                      <v-icon size="16" color="info">mdi-cog</v-icon>
                      <span class="text-body-2 font-weight-medium">{{ t.tool }}</span>
                      <v-chip v-if="t.duration_ms" size="x-small" variant="tonal">{{ t.duration_ms }}ms</v-chip>
                    </div>
                    <pre v-if="t.args" class="args-block text-caption pa-3 rounded-lg mt-2">{{ JSON.stringify(t.args, null, 2) }}</pre>
                  </div>
                </div>

                <!-- Post-tool decisions -->
                <div v-if="iter.post_tool_decisions?.length" class="iter-subsection mb-4">
                  <div class="subsection-label mb-2">
                    <v-icon size="14" class="mr-1">mdi-shield-search</v-icon>
                    Post-tool Gate
                  </div>
                  <div v-for="(d, di) in iter.post_tool_decisions" :key="di" class="d-flex align-center ga-2 mb-2">
                    <v-chip :color="decisionColor(d.decision)" size="x-small" variant="flat">{{ d.decision }}</v-chip>
                    <span class="text-body-2">{{ d.tool }}</span>
                    <v-chip v-if="d.pii_count" size="x-small" variant="tonal" color="warning">
                      PII: {{ d.pii_count }}
                    </v-chip>
                  </div>
                </div>

                <!-- LLM call -->
                <div v-if="iter.llm_call" class="iter-subsection mb-4">
                  <div class="subsection-label mb-2">
                    <v-icon size="14" class="mr-1">mdi-brain</v-icon>
                    LLM Call
                  </div>
                  <div class="d-flex flex-wrap ga-3">
                    <v-chip v-if="iter.llm_call.tokens_in != null" size="x-small" variant="tonal" color="teal">
                      <v-icon start size="12">mdi-arrow-down</v-icon>
                      {{ iter.llm_call.tokens_in }} in
                    </v-chip>
                    <v-chip v-if="iter.llm_call.tokens_out != null" size="x-small" variant="tonal" color="teal">
                      <v-icon start size="12">mdi-arrow-up</v-icon>
                      {{ iter.llm_call.tokens_out }} out
                    </v-chip>
                    <v-chip v-if="iter.llm_call.duration_ms" size="x-small" variant="tonal">
                      <v-icon start size="12">mdi-timer-outline</v-icon>
                      {{ iter.llm_call.duration_ms }}ms
                    </v-chip>
                  </div>
                </div>

                <!-- Firewall decision -->
                <div v-if="iter.firewall_decision" class="iter-subsection">
                  <div class="subsection-label mb-2">
                    <v-icon size="14" class="mr-1">mdi-shield-alert-outline</v-icon>
                    Firewall Decision
                  </div>
                  <div class="d-flex align-center ga-2">
                    <v-chip :color="decisionColor(iter.firewall_decision.decision)" size="small" variant="flat" class="font-weight-bold">
                      {{ iter.firewall_decision.decision }}
                    </v-chip>
                    <span v-if="iter.firewall_decision.risk_score != null" class="text-body-2">
                      Risk: <strong>{{ (iter.firewall_decision.risk_score * 100).toFixed(0) }}%</strong>
                    </span>
                  </div>
                </div>
              </div>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
      </div>

      <!-- ── SECTION 5: Metrics ── -->
      <v-row class="mb-5" no-gutters>
        <!-- Node Timings -->
        <v-col cols="12" md="6" class="pr-md-2 mb-3 mb-md-0">
          <div class="metrics-card">
            <div class="section-label mb-3">
              <v-icon size="16" class="mr-1">mdi-chart-timeline-variant</v-icon>
              Node Timings
            </div>
            <template v-if="timingEntries.length">
              <div v-for="[node, ms] in timingEntries" :key="node" class="timing-row mb-2">
                <span class="text-body-2" style="min-width: 120px;">{{ node }}</span>
                <v-progress-linear
                  :model-value="maxTiming > 0 ? (ms / maxTiming * 100) : 0"
                  color="primary"
                  height="6"
                  rounded
                  class="mx-3 flex-grow-1"
                  style="max-width: 180px;"
                />
                <span class="text-body-2 font-weight-bold">{{ ms }}ms</span>
              </div>
            </template>
            <div v-else class="empty-state">
              <v-icon size="32" color="grey-darken-1" class="mb-2">mdi-timer-off-outline</v-icon>
              <span class="text-caption text-medium-emphasis">No node timing data recorded</span>
            </div>
          </div>
        </v-col>

        <!-- Counters -->
        <v-col cols="12" md="6" class="pl-md-2">
          <div class="metrics-card">
            <div class="section-label mb-3">
              <v-icon size="16" class="mr-1">mdi-counter</v-icon>
              Counters
            </div>
            <template v-if="counterEntries.length">
              <div class="counters-grid">
                <div v-for="c in enrichedCounters" :key="c.key" class="counter-row">
                  <div class="d-flex align-center ga-2">
                    <v-icon :icon="c.icon" :color="c.color" size="18" />
                    <span class="text-body-2">
                      {{ c.label }}
                      <v-tooltip activator="parent" location="top" max-width="280">{{ c.description }}</v-tooltip>
                    </span>
                  </div>
                  <span class="text-body-2 font-weight-bold" :class="c.highlight ? 'text-error' : ''" style="font-feature-settings: 'tnum'">{{ c.value }}</span>
                </div>
              </div>
            </template>
            <div v-else class="empty-state">
              <v-icon size="32" color="grey-darken-1" class="mb-2">mdi-counter</v-icon>
              <span class="text-caption text-medium-emphasis">No counter data available</span>
            </div>
          </div>
        </v-col>
      </v-row>

      <!-- ── Errors ── -->
      <div v-if="errors.length" class="mb-5">
        <v-alert
          v-for="(err, i) in errors"
          :key="i"
          type="error"
          variant="tonal"
          density="compact"
          class="mb-2"
        >
          {{ err }}
        </v-alert>
      </div>

      <!-- ── Footer Metadata ── -->
      <div class="detail-footer">
        <span>Trace: {{ shortId(detail.trace_id) }}</span>
        <span>Session: {{ shortId(detail.session_id) }}</span>
        <span>Policy: {{ detail.policy }}</span>
        <span v-if="detail.limits_hit">
          <v-icon size="12" icon="mdi-alert" color="warning" class="mr-1" />Limit: {{ detail.limits_hit }}
        </span>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { AgentTraceDetail, TraceIteration } from '~/types/agentTrace'

const props = defineProps<{
  detail: AgentTraceDetail | null
  loading: boolean
}>()

const iterations = computed<TraceIteration[]>(() =>
  props.detail?.iterations ?? [],
)

const isBlocked = computed(() => {
  if (!props.detail) return false
  return iterations.value.some((iter) => iterHasBlock(iter))
})

const errors = computed<string[]>(() =>
  props.detail?.errors ?? [],
)

const timingEntries = computed(() =>
  Object.entries(props.detail?.node_timings ?? {})
    .sort(([, a], [, b]) => b - a),
)

const maxTiming = computed(() =>
  timingEntries.value.length ? Math.max(...timingEntries.value.map(([, v]) => v)) : 1,
)

const counterEntries = computed(() =>
  Object.entries(props.detail?.counters ?? {}),
)

interface CounterMeta {
  key: string
  label: string
  icon: string
  color: string
  description: string
  value: number | string
  highlight: boolean
}

const COUNTER_META: Record<string, { label: string; icon: string; color: string; description: string; highlightIf?: (v: number) => boolean }> = {
  iterations: {
    label: 'Iterations',
    icon: 'mdi-repeat',
    color: 'primary',
    description: 'Number of agent loop iterations (tool planning → execution → LLM call cycles)',
  },
  tool_calls: {
    label: 'Tool calls',
    icon: 'mdi-wrench',
    color: 'info',
    description: 'Total number of tools executed by the agent (e.g. searchKnowledgeBase, getOrderStatus)',
  },
  tool_calls_blocked: {
    label: 'Tools blocked',
    icon: 'mdi-shield-off-outline',
    color: 'error',
    description: 'Tool calls rejected by the RBAC policy — the user\'s role did not have permission for this tool',
    highlightIf: (v) => v > 0,
  },
  tokens_in: {
    label: 'Tokens in',
    icon: 'mdi-arrow-down',
    color: 'teal',
    description: 'Input tokens sent to the LLM (prompt + conversation history + tool results)',
  },
  tokens_out: {
    label: 'Tokens out',
    icon: 'mdi-arrow-up',
    color: 'teal',
    description: 'Output tokens generated by the LLM in its response',
  },
  estimated_cost: {
    label: 'Est. cost',
    icon: 'mdi-currency-usd',
    color: 'amber',
    description: 'Estimated API cost for this request based on token pricing for the selected model',
  },
}

const enrichedCounters = computed<CounterMeta[]>(() => {
  return counterEntries.value.map(([key, val]) => {
    const meta = COUNTER_META[key]
    const numVal = typeof val === 'number' ? val : Number(val) || 0
    return {
      key,
      label: meta?.label ?? key,
      icon: meta?.icon ?? 'mdi-counter',
      color: meta?.color ?? 'grey',
      description: meta?.description ?? key,
      value: key === 'estimated_cost' ? `$${numVal.toFixed(4)}` : val,
      highlight: meta?.highlightIf?.(numVal) ?? false,
    }
  })
})

function iterToolCount(iter: TraceIteration): number {
  return iter.tool_executions?.length ?? 0
}

function iterHasBlock(iter: TraceIteration): boolean {
  const preToolBlock = (iter.pre_tool_decisions ?? []).some((d) => d.decision === 'BLOCK')
  const firewallBlock = iter.firewall_decision?.decision === 'BLOCK'
  return preToolBlock || firewallBlock
}

function decisionColor(d: string) {
  if (d === 'ALLOW') return 'success'
  if (d === 'MODIFY') return 'warning'
  if (d === 'BLOCK') return 'error'
  if (d === 'REDACT') return 'orange'
  return 'grey'
}

function shortId(id: unknown): string {
  const s = String(id ?? '')
  return s.length > 12 ? `${s.slice(0, 8)}…` : s
}
</script>

<style scoped>
.detail-row {
  padding: 20px 24px;
  background: rgba(var(--v-theme-on-surface), 0.035);
}

/* ── Section labels ── */
.section-label {
  display: flex;
  align-items: center;
  font-size: 13px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: rgba(var(--v-theme-on-surface), 0.7);
}

.subsection-label {
  display: flex;
  align-items: center;
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.3px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

/* ── Message blocks ── */
.message-block {
  padding: 14px 18px;
  border-radius: 12px;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: 'Roboto Mono', monospace;
}

.message-user {
  background: rgba(var(--v-theme-primary), 0.10);
  border-left: 3px solid rgb(var(--v-theme-primary));
}

.message-response {
  background: rgba(var(--v-theme-on-surface), 0.07);
  border-left: 3px solid rgba(var(--v-theme-on-surface), 0.2);
  max-height: 200px;
  overflow-y: auto;
}

/* ── Iteration panels ── */
.iteration-panels {
  border-radius: 12px !important;
  overflow: hidden;
}

.iteration-panel {
  background: rgba(var(--v-theme-on-surface), 0.05) !important;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.06);
}

.iteration-title {
  min-height: 56px !important;
  padding-top: 4px !important;
  padding-bottom: 4px !important;
  transition: background 0.15s ease;
}

.iteration-title:hover {
  background: rgba(var(--v-theme-primary), 0.04);
}

.iter-subsection {
  padding: 12px 16px;
  border-radius: 10px;
  background: rgba(var(--v-theme-on-surface), 0.04);
}

.args-block {
  background: rgba(var(--v-theme-on-surface), 0.05);
  white-space: pre-wrap;
  max-height: 100px;
  overflow-y: auto;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.08);
}

/* ── Metrics cards ── */
.metrics-card {
  padding: 18px 22px;
  border-radius: 12px;
  background: rgba(var(--v-theme-on-surface), 0.05);
  border: 1px solid rgba(var(--v-theme-on-surface), 0.06);
  min-height: 120px;
}

.timing-row {
  display: flex;
  align-items: center;
}

.counters-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.counter-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  border-radius: 10px;
  background: rgba(var(--v-theme-on-surface), 0.05);
  transition: background 0.15s ease;
}

.counter-row:hover {
  background: rgba(var(--v-theme-on-surface), 0.09);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 28px 16px;
  min-height: 80px;
  opacity: 0.5;
}

/* ── Footer ── */
.detail-footer {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
  padding-top: 14px;
  border-top: 1px solid rgba(var(--v-theme-on-surface), 0.06);
  font-size: 11px;
  color: rgba(var(--v-theme-on-surface), 0.30);
  letter-spacing: 0.3px;
}

/* ── Summary header ── */
.detail-header {
  padding-bottom: 16px;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.08);
}
</style>
