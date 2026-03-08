<template>
  <v-card variant="outlined" class="pa-4">
    <div v-if="loading" class="text-center py-4">
      <v-progress-circular indeterminate color="primary" />
      <p class="text-body-2 text-medium-emphasis mt-2">Loading trace…</p>
    </div>

    <template v-else-if="detail">
      <!-- User Message -->
      <div class="mb-4" v-if="detail.user_message">
        <div class="text-overline text-medium-emphasis mb-1">User Message</div>
        <v-code tag="pre" class="pa-3 text-body-2" style="white-space: pre-wrap; word-break: break-word;">{{ detail.user_message }}</v-code>
      </div>

      <!-- Final Response -->
      <div class="mb-4" v-if="detail.final_response">
        <div class="text-overline text-medium-emphasis mb-1">Final Response</div>
        <v-code tag="pre" class="pa-3 text-body-2" style="white-space: pre-wrap; word-break: break-word; max-height: 200px; overflow-y: auto;">{{ detail.final_response }}</v-code>
      </div>

      <!-- Iterations -->
      <div v-if="iterations.length" class="mb-4">
        <div class="text-overline text-medium-emphasis mb-2">
          Iterations ({{ iterations.length }})
        </div>
        <v-expansion-panels variant="accordion">
          <v-expansion-panel
            v-for="(iter, idx) in iterations"
            :key="idx"
          >
            <v-expansion-panel-title>
              <div class="d-flex align-center ga-2">
                <v-icon size="16">mdi-repeat</v-icon>
                <span class="text-body-2 font-weight-medium">Iteration {{ iter.iteration ?? idx + 1 }}</span>
                <v-chip v-if="iterToolCount(iter)" size="x-small" variant="tonal" color="info">
                  {{ iterToolCount(iter) }} tool{{ iterToolCount(iter) > 1 ? 's' : '' }}
                </v-chip>
                <v-chip v-if="iterHasBlock(iter)" size="x-small" variant="flat" color="error">
                  BLOCKED
                </v-chip>
              </div>
            </v-expansion-panel-title>
            <v-expansion-panel-text>
              <!-- Pre-tool decisions -->
              <div v-if="iter.pre_tool_decisions?.length" class="mb-3">
                <div class="text-caption font-weight-bold mb-1">Pre-tool Gate</div>
                <div v-for="(d, di) in iter.pre_tool_decisions" :key="di" class="d-flex align-center ga-2 mb-1">
                  <v-chip :color="decisionColor(d.decision)" size="x-small" variant="flat">{{ d.decision }}</v-chip>
                  <span class="text-caption">{{ d.tool }}</span>
                  <span v-if="d.reason" class="text-caption text-medium-emphasis">— {{ d.reason }}</span>
                </div>
              </div>

              <!-- Tool executions -->
              <div v-if="iter.tool_executions?.length" class="mb-3">
                <div class="text-caption font-weight-bold mb-1">Tool Executions</div>
                <div v-for="(t, ti) in iter.tool_executions" :key="ti" class="mb-2">
                  <div class="d-flex align-center ga-2">
                    <v-icon size="14">mdi-wrench</v-icon>
                    <span class="text-caption font-weight-medium">{{ t.tool }}</span>
                    <span v-if="t.duration_ms" class="text-caption text-medium-emphasis">{{ t.duration_ms }}ms</span>
                  </div>
                  <pre v-if="t.args" class="text-caption pa-2 bg-surface-variant rounded mt-1" style="white-space: pre-wrap; max-height: 100px; overflow-y: auto;">{{ JSON.stringify(t.args, null, 2) }}</pre>
                </div>
              </div>

              <!-- Post-tool decisions -->
              <div v-if="iter.post_tool_decisions?.length" class="mb-3">
                <div class="text-caption font-weight-bold mb-1">Post-tool Gate</div>
                <div v-for="(d, di) in iter.post_tool_decisions" :key="di" class="d-flex align-center ga-2 mb-1">
                  <v-chip :color="decisionColor(d.decision)" size="x-small" variant="flat">{{ d.decision }}</v-chip>
                  <span class="text-caption">{{ d.tool }}</span>
                  <span v-if="d.pii_count" class="text-caption text-medium-emphasis">PII: {{ d.pii_count }}</span>
                </div>
              </div>

              <!-- LLM call -->
              <div v-if="iter.llm_call" class="mb-3">
                <div class="text-caption font-weight-bold mb-1">LLM Call</div>
                <div class="d-flex flex-wrap ga-3 text-caption">
                  <span v-if="iter.llm_call.tokens_in != null">In: {{ iter.llm_call.tokens_in }} tokens</span>
                  <span v-if="iter.llm_call.tokens_out != null">Out: {{ iter.llm_call.tokens_out }} tokens</span>
                  <span v-if="iter.llm_call.duration_ms">{{ iter.llm_call.duration_ms }}ms</span>
                </div>
              </div>

              <!-- Firewall decision -->
              <div v-if="iter.firewall_decision">
                <div class="text-caption font-weight-bold mb-1">Firewall Decision</div>
                <div class="d-flex align-center ga-2">
                  <v-chip :color="decisionColor(iter.firewall_decision.decision)" size="x-small" variant="flat">
                    {{ iter.firewall_decision.decision }}
                  </v-chip>
                  <span v-if="iter.firewall_decision.risk_score != null" class="text-caption">
                    Risk: {{ (iter.firewall_decision.risk_score * 100).toFixed(0) }}%
                  </span>
                </div>
              </div>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
      </div>

      <v-row>
        <!-- Node Timings -->
        <v-col cols="12" md="6">
          <div class="text-overline text-medium-emphasis mb-2">Node Timings</div>
          <template v-if="timingEntries.length">
            <div v-for="[node, ms] in timingEntries" :key="node" class="d-flex align-center mb-1">
              <span class="text-caption" style="min-width: 130px;">{{ node }}</span>
              <v-progress-linear
                :model-value="maxTiming > 0 ? (ms / maxTiming * 100) : 0"
                color="primary"
                height="8"
                rounded
                style="max-width: 200px;"
                class="mr-2"
              />
              <span class="text-caption font-weight-bold">{{ ms }}ms</span>
            </div>
          </template>
          <span v-else class="text-body-2 text-medium-emphasis">None</span>
        </v-col>

        <!-- Counters -->
        <v-col cols="12" md="6">
          <div class="text-overline text-medium-emphasis mb-2">Counters</div>
          <template v-if="counterEntries.length">
            <div v-for="c in enrichedCounters" :key="c.key" class="d-flex align-center mb-2">
              <v-icon :icon="c.icon" :color="c.color" size="16" class="mr-2 flex-shrink-0" />
              <div class="d-flex justify-space-between flex-grow-1">
                <span class="text-caption">
                  {{ c.label }}
                  <v-tooltip activator="parent" location="top" max-width="280">
                    {{ c.description }}
                  </v-tooltip>
                </span>
                <span class="text-caption font-weight-bold" :class="c.highlight ? 'text-error' : ''">{{ c.value }}</span>
              </div>
            </div>
          </template>
          <span v-else class="text-body-2 text-medium-emphasis">None</span>
        </v-col>
      </v-row>

      <!-- Errors -->
      <div v-if="errors.length" class="mt-3">
        <v-alert
          v-for="(err, i) in errors"
          :key="i"
          type="error"
          variant="tonal"
          density="compact"
          class="mb-1"
        >
          {{ err }}
        </v-alert>
      </div>

      <!-- Metadata -->
      <v-divider class="my-3" />
      <div class="d-flex flex-wrap ga-3 text-caption text-medium-emphasis">
        <span>Trace: <strong>{{ shortId(detail.trace_id) }}</strong></span>
        <span>Session: <strong>{{ shortId(detail.session_id) }}</strong></span>
        <span>Model: <strong>{{ detail.model }}</strong></span>
        <span>Policy: <strong>{{ detail.policy }}</strong></span>
        <span>Duration: <strong>{{ detail.total_duration_ms }}ms</strong></span>
        <span v-if="detail.limits_hit">
          <v-icon size="14" icon="mdi-alert" color="warning" class="mr-1" />Limit: {{ detail.limits_hit }}
        </span>
      </div>
    </template>
  </v-card>
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
