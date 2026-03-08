<template>
  <v-card variant="flat" class="debug-panel">
    <v-card-title class="text-subtitle-1">
      <v-icon class="main-icon" start>mdi-bug</v-icon>
      Pipeline Debug
    </v-card-title>

    <v-card-text v-if="!decision" class="text-grey text-body-2">
      Send a message to see pipeline results.
    </v-card-text>

    <v-card-text v-else>
      <!-- Decision badge -->
      <div v-if="decision.decision === 'BLOCK'" class="block-verdict mb-3">
        <div class="d-flex align-center ga-2">
          <v-icon icon="mdi-shield-off" color="error" size="20" />
          <span class="text-body-1 font-weight-bold text-error">BLOCKED</span>
        </div>
        <div v-if="decision.blockedReason" class="text-caption mt-1" style="color: rgba(var(--v-theme-error), 0.8);">
          {{ blockedLabel }}
        </div>
      </div>
      <div v-else class="debug-panel__row mb-3">
        <span class="text-caption text-grey">Decision</span>
        <v-chip
          :color="decisionColor"
          size="small"
          label
        >
          {{ decision.decision }}
        </v-chip>
      </div>

      <!-- Intent -->
      <div class="debug-panel__row mb-3">
        <span class="text-caption text-grey">Intent</span>
        <span class="text-body-2 font-weight-medium">{{ decision.intent }}</span>
      </div>

      <!-- Risk Score -->
      <div class="mb-3">
        <div class="d-flex justify-space-between mb-1">
          <span class="text-caption text-grey">Risk score</span>
          <span class="text-body-2 font-weight-medium">
            {{ (decision.riskScore * 100).toFixed(0) }}%
          </span>
        </div>
        <v-progress-linear
          :model-value="decision.riskScore * 100"
          :color="riskColor"
          height="8"
          rounded
        />
      </div>

      <!-- Risk Flags -->
      <div v-if="hasFlags" class="mb-3">
        <span class="text-caption text-grey d-block mb-1">Risk flags</span>
        <div class="d-flex flex-wrap ga-1">
          <v-chip
            v-for="(score, flag) in decision.riskFlags"
            :key="String(flag)"
            :color="flagColor(Number(score))"
            size="x-small"
            label
          >
            {{ flag }}: {{ Number(score).toFixed(2) }}
          </v-chip>
        </div>
      </div>

      <!-- Blocked reason -->
      <v-alert
        v-if="decision.decision === 'BLOCK' && decision.blockedReason"
        type="error"
        density="compact"
        variant="tonal"
        class="mt-2 block-alert"
      >
        <div class="font-weight-bold text-body-2 mb-1">
          Blocked — {{ blockedLabel }}
        </div>
        <div class="text-caption">
          {{ decision.blockedReason }}
        </div>
      </v-alert>

      <!-- Triggered controls -->
      <div v-if="triggeredControls.length" class="mt-3">
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
import type { PipelineDecision } from '~/types/api'
import { decisionColor as _dc, riskColor as _rc, flagColor as _fc } from '~/utils/colors'

const props = defineProps<{
  decision: PipelineDecision | null
}>()

const decisionColor = computed(() => _dc(props.decision?.decision))

const riskColor = computed(() => _rc(props.decision?.riskScore))

const hasFlags = computed(() =>
  props.decision?.riskFlags && Object.keys(props.decision.riskFlags).length > 0,
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
  }
  return labels[intent] ?? intent.replace(/_/g, ' ')
})

const triggeredControls = computed(() => {
  if (!props.decision || props.decision.decision !== 'BLOCK') return []
  const controls: string[] = []
  const reason = props.decision.blockedReason ?? ''
  const intent = props.decision.intent ?? ''

  // Derive from intent
  if (intent.includes('injection') || intent.includes('jailbreak')) controls.push('NeMo Guardrails')
  if (intent.includes('pii') || reason.toLowerCase().includes('pii')) controls.push('Presidio PII')
  if (intent.includes('exfiltration') || intent.includes('data_leak')) controls.push('Data boundary')
  if (reason.toLowerCase().includes('custom rule') || reason.toLowerCase().includes('keyword')) controls.push('Custom rules')

  // Derive from risk flags
  const flags = Object.keys(props.decision.riskFlags ?? {})
  if (flags.some(f => f.includes('suspicious'))) controls.push('Intent classifier')
  if (flags.some(f => f.includes('toxicity') || f.includes('harm'))) controls.push('LLM Guard')

  // Always at least show the intent-based control
  if (controls.length === 0) controls.push('Security pipeline')
  return [...new Set(controls)]
})
</script>

<style lang="scss" scoped>
.debug-panel {
  padding: 8px 0;
  border-radius: 12px !important;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25), 0 0 0 1px rgba(255, 255, 255, 0.12) !important;
  background: rgb(var(--v-theme-surface));

  .main-icon{
    font-size: 24px;
  }
  &__row {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  :deep(.v-chip) {
    font-size: 12px !important;
  }

  .block-alert {
    border-left: 3px solid rgb(var(--v-theme-error));
  }
}

.block-verdict {
  padding: 8px 12px;
  background: rgba(var(--v-theme-error), 0.08);
  border-radius: 8px;
  border-left: 3px solid rgb(var(--v-theme-error));
}
</style>
