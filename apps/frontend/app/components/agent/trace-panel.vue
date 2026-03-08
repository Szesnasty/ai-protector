<template>
  <v-card variant="flat" class="agent-trace-panel">
    <!-- Agent Trace section -->
    <v-card-title class="text-subtitle-1">
      <v-icon start size="20">mdi-chart-timeline-variant</v-icon>
      Agent Trace
    </v-card-title>

    <v-card-text v-if="!trace" class="text-grey text-body-2">
      Send a message to see agent trace.
    </v-card-text>

    <v-card-text v-else>
      <div class="trace-row mb-3">
        <span class="text-caption text-grey">Intent</span>
        <v-chip color="info" size="small" label>{{ trace.intent }}</v-chip>
      </div>

      <div class="trace-row mb-3">
        <span class="text-caption text-grey">Role</span>
        <span class="text-body-2 font-weight-medium">{{ trace.user_role }}</span>
      </div>

      <div v-if="trace.allowed_tools.length" class="mb-3">
        <span class="text-caption text-grey d-block mb-1">Allowed tools</span>
        <div class="d-flex flex-wrap ga-1">
          <v-chip
            v-for="tool in trace.allowed_tools"
            :key="tool"
            size="x-small"
            label
            color="info"
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
      <v-icon start size="20">mdi-shield-search</v-icon>
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
        class="mt-2"
      >
        {{ decision.blocked_reason }}
      </v-alert>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { AgentTrace, FirewallDecision } from '~/types/agent'

const props = defineProps<{
  trace: AgentTrace | null
  decision: FirewallDecision | null
}>()

const decisionColor = computed(() => {
  switch (props.decision?.decision) {
    case 'ALLOW': return 'success'
    case 'MODIFY': return 'warning'
    case 'BLOCK': return 'error'
    default: return 'grey'
  }
})

const riskColor = computed(() => {
  const score = props.decision?.risk_score ?? 0
  if (score >= 0.7) return 'error'
  if (score >= 0.3) return 'warning'
  return 'success'
})

const hasFlags = computed(() =>
  props.decision?.risk_flags && Object.keys(props.decision.risk_flags).length > 0,
)

function flagColor(score: number): string {
  if (score >= 0.7) return 'error'
  if (score >= 0.3) return 'warning'
  return 'grey'
}
</script>

<style lang="scss" scoped>
.agent-trace-panel {
  padding: 8px 0;

  :deep(.v-chip) {
    font-size: 12px !important;
  }
}

.trace-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
