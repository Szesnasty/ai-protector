<template>
  <div class="compare-decision-card pa-3">
    <div class="d-flex align-center justify-space-between mb-2">
      <span class="text-caption font-weight-bold text-grey">Pipeline Result</span>
      <v-chip
        :color="decisionColor"
        size="small"
        label
        class="font-weight-bold"
      >
        {{ decision.decision }}
      </v-chip>
    </div>

    <!-- Intent -->
    <div class="d-flex justify-space-between align-center mb-2">
      <span class="text-caption text-grey">Intent</span>
      <span class="text-body-2 font-weight-medium">{{ decision.intent }}</span>
    </div>

    <!-- Risk Score -->
    <div class="mb-2">
      <div class="d-flex justify-space-between mb-1">
        <span class="text-caption text-grey">Risk score</span>
        <span class="text-body-2 font-weight-medium">
          {{ (decision.riskScore * 100).toFixed(0) }}%
        </span>
      </div>
      <v-progress-linear
        :model-value="decision.riskScore * 100"
        :color="riskColor"
        height="6"
        rounded
      />
    </div>

    <!-- Risk Flags -->
    <div v-if="hasFlags" class="mb-2">
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
      class="mt-1"
    >
      {{ decision.blockedReason }}
    </v-alert>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { PipelineDecision } from '~/types/api'
import { decisionColor as _dc, riskColor as _rc, flagColor as _fc } from '~/utils/colors'

const props = defineProps<{
  decision: PipelineDecision
}>()

const decisionColor = computed(() => _dc(props.decision.decision))

const riskColor = computed(() => _rc(props.decision.riskScore))

const hasFlags = computed(() =>
  props.decision.riskFlags && Object.keys(props.decision.riskFlags).length > 0,
)

function flagColor(score: number): string {
  return _fc('', score)
}
</script>

<style lang="scss" scoped>
.compare-decision-card {
  background: rgba(var(--v-theme-surface-variant), 0.2);

  :deep(.v-chip) {
    font-size: 12px !important;
  }
}
</style>
