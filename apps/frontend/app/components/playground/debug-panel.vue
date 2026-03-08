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
      <div class="debug-panel__row mb-3">
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
        class="mt-2"
      >
        {{ decision.blockedReason }}
      </v-alert>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { PipelineDecision } from '~/types/api'

const props = defineProps<{
  decision: PipelineDecision | null
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
  const score = props.decision?.riskScore ?? 0
  if (score >= 0.7) return 'error'
  if (score >= 0.3) return 'warning'
  return 'success'
})

const hasFlags = computed(() =>
  props.decision?.riskFlags && Object.keys(props.decision.riskFlags).length > 0,
)

function flagColor(score: number): string {
  if (score >= 0.7) return 'error'
  if (score >= 0.3) return 'warning'
  return 'grey'
}
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
}
</style>
