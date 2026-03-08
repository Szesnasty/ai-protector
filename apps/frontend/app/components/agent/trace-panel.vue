<template>
  <v-card variant="flat" class="agent-trace-panel">
    <!-- Agent Trace section -->
    <v-card-title class="text-subtitle-1">
      <v-icon class="main-icon" start>mdi-chart-timeline-variant</v-icon>
      Agent Trace
    </v-card-title>

    <v-card-text v-if="!trace" class="text-grey text-body-2">
      Send a message to see agent trace.
    </v-card-text>

    <v-card-text v-else>
      <div class="trace-row mb-3">
        <span class="text-caption text-grey">Intent</span>
        <v-chip size="small" label>{{ trace.intent }}</v-chip>
      </div>

      <div class="trace-row mb-3">
        <span class="text-caption text-grey">Role</span>
        <span class="text-body-2 font-weight-medium">{{ trace.user_role }}</span>
      </div>

      <div v-if="trace.allowed_tools.length" class="mb-3">
        <span class="text-caption text-grey d-block mb-1">Role tool access</span>
        <div class="d-flex flex-wrap ga-1">
          <v-chip
            v-for="tool in trace.allowed_tools"
            :key="tool"
            size="x-small"
            label
            variant="outlined"
          >
            {{ tool }}
          </v-chip>
        </div>
      </div>

      <div class="trace-row mb-3">
        <span class="text-caption text-grey">Iterations</span>
        <span class="text-body-2 font-weight-medium">{{ trace.iterations }}</span>
      </div>

      <div class="trace-row mb-3">
        <span class="text-caption text-grey">Latency</span>
        <span class="text-body-2 font-weight-medium">{{ trace.latency_ms }} ms</span>
      </div>
    </v-card-text>

    <v-divider />

    <!-- Firewall Decision section -->
    <v-card-title class="text-subtitle-1">
      <v-icon class="main-icon" start>mdi-shield-search</v-icon>
      Firewall Decision
    </v-card-title>

    <v-card-text v-if="!decision || decision.decision === 'UNKNOWN'" class="text-grey text-body-2">
      No firewall decision yet.
    </v-card-text>

    <v-card-text v-else>
      <div class="trace-row mb-3">
        <span class="text-caption text-grey">Decision</span>
        <v-chip :color="decisionColor" size="small" label>
          {{ decision.decision }}
        </v-chip>
      </div>

      <div class="trace-row mb-3">
        <span class="text-caption text-grey">Intent</span>
        <span class="text-body-2 font-weight-medium">{{ decision.intent }}</span>
      </div>

      <div class="mb-3">
        <div class="d-flex justify-space-between mb-1">
          <span class="text-caption text-grey">Risk score</span>
          <span class="text-body-2 font-weight-medium">
            {{ (decision.risk_score * 100).toFixed(0) }}%
          </span>
        </div>
        <v-progress-linear
          :model-value="decision.risk_score * 100"
          :color="riskColor"
          height="8"
          rounded
        />
      </div>

      <div v-if="hasFlags" class="mb-3">
        <span class="text-caption text-grey d-block mb-1">Risk flags</span>
        <div class="d-flex flex-wrap ga-1">
          <v-chip
            v-for="(score, flag) in decision.risk_flags"
            :key="String(flag)"
            :color="flagColor(Number(score))"
            size="x-small"
            label
          >
            {{ flag }}: {{ Number(score).toFixed(2) }}
          </v-chip>
        </div>
      </div>

      <v-alert
        v-if="decision.decision === 'BLOCK' && decision.blocked_reason"
        type="error"
        density="compact"
        variant="tonal"
        class="mt-2 block-alert"
      >
        <div class="font-weight-bold text-body-2 mb-1">
          Blocked — {{ blockedLabel }}
        </div>
        <div class="text-caption">
          {{ decision.blocked_reason }}
        </div>
      </v-alert>

      <!-- Triggered controls -->
      <div v-if="triggeredControls.length" class="mt-4">
        <span class="text-caption text-grey d-block mb-1">Triggered controls</span>
        <div class="d-flex flex-wrap ga-1">
          <v-chip
            v-for="ctrl in triggeredControls"
            :key="ctrl"
            color="error"
            size="x-small"
            label
            variant="outlined"
          >
            {{ ctrl }}
          </v-chip>
        </div>
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { AgentTrace, FirewallDecision } from '~/types/agent'
import { decisionColor as _dc, riskColor as _rc, flagColor as _fc } from '~/utils/colors'

const props = defineProps<{
  trace: AgentTrace | null
  decision: FirewallDecision | null
}>()

const decisionColor = computed(() => _dc(props.decision?.decision))

const riskColor = computed(() => _rc(props.decision?.risk_score))

const hasFlags = computed(() =>
  props.decision?.risk_flags && Object.keys(props.decision.risk_flags).length > 0,
)

function flagColor(score: number): string {
  return _fc('', score)
}

const blockedLabel = computed(() => {
  const intent = props.decision?.intent ?? 'unknown'
  const labels: Record<string, string> = {
    prompt_injection: 'prompt injection attempt',
    jailbreak: 'jailbreak attempt',
    agent_exfiltration: 'attempted data exfiltration',
    data_leak: 'data leak attempt',
    social_engineering: 'social engineering attempt',
    system_sabotage: 'system sabotage attempt',
    pii_leak: 'PII exposure detected',
    harmful_content: 'harmful content detected',
    off_topic: 'off-topic request blocked',
    suspicious_intent: 'suspicious intent detected',
    order_query: 'order query',
    excessive_agency: 'excessive agency attempt',
  }
  return labels[intent] ?? intent.replace(/_/g, ' ')
})

const triggeredControls = computed(() => {
  if (!props.decision || props.decision.decision !== 'BLOCK') return []
  const controls: string[] = []
  const reason = props.decision.blocked_reason ?? ''
  const intent = props.decision.intent ?? ''

  if (intent.includes('injection') || intent.includes('jailbreak')) controls.push('NeMo Guardrails')
  if (intent.includes('pii') || reason.toLowerCase().includes('pii')) controls.push('Presidio PII')
  if (intent.includes('exfiltration') || intent.includes('data_leak')) controls.push('Data boundary')
  if (reason.toLowerCase().includes('custom rule') || reason.toLowerCase().includes('keyword')) controls.push('Custom rules')

  const flags = Object.keys(props.decision.risk_flags ?? {})
  if (flags.some(f => f.includes('suspicious'))) controls.push('Intent classifier')
  if (flags.some(f => f.includes('toxicity') || f.includes('harm'))) controls.push('LLM Guard')
  if (intent.includes('excessive_agency') || intent.includes('agent')) controls.push('Agent firewall')

  if (controls.length === 0) controls.push('Security pipeline')
  return [...new Set(controls)]
})
</script>

<style lang="scss" scoped>
.agent-trace-panel {
  padding: 8px 0;
  border-radius: 12px !important;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25), 0 0 0 1px rgba(255, 255, 255, 0.12) !important;
  background: rgb(var(--v-theme-surface));
  flex: 1;
  min-height: 0;
  overflow-y: auto;

  .main-icon {
    font-size: 24px;
  }

  :deep(.v-chip) {
    font-size: 12px !important;
  }

  .block-alert {
    border-left: 3px solid rgb(var(--v-theme-error));
  }
}

.trace-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
