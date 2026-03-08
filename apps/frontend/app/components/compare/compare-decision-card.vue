<template>
  <div class="compare-decision-card pa-3" :class="`card--${decision.decision.toLowerCase()}`">
    <!-- Action badge -->
    <div class="d-flex align-center ga-2 mb-2">
      <v-icon :icon="actionIcon" :color="decisionColor" size="18" />
      <span class="text-caption font-weight-bold" :style="{ color: `rgb(var(--v-theme-${decisionColor}))` }">
        {{ actionLabel }}
      </span>
      <v-spacer />
      <v-chip
        :color="decisionColor"
        size="small"
        label
        variant="flat"
        class="font-weight-bold"
      >
        {{ decision.decision }}
      </v-chip>
    </div>

    <!-- Blocked reason (prominent) -->
    <div v-if="decision.decision === 'BLOCK' && decision.blockedReason" class="blocked-reason mb-2">
      <v-icon icon="mdi-shield-alert" size="14" class="mr-1" />
      <span class="text-caption">{{ decision.blockedReason }}</span>
    </div>

    <!-- Intent + Risk compact row -->
    <div class="d-flex ga-4 mb-2">
      <div class="flex-grow-1">
        <span class="text-caption text-medium-emphasis d-block" style="font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px">Intent</span>
        <span class="text-body-2 font-weight-medium">{{ decision.intent }}</span>
      </div>
      <div style="min-width: 100px">
        <span class="text-caption text-medium-emphasis d-block" style="font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px">Risk</span>
        <div class="d-flex align-center ga-1">
          <v-progress-linear
            :model-value="decision.riskScore * 100"
            :color="riskColor"
            height="5"
            rounded
            style="max-width: 60px"
          />
          <span class="text-caption font-weight-medium">{{ (decision.riskScore * 100).toFixed(0) }}%</span>
        </div>
      </div>
    </div>

    <!-- Risk Flags -->
    <div v-if="hasFlags" class="d-flex flex-wrap ga-1">
      <v-chip
        v-for="(score, flag) in decision.riskFlags"
        :key="String(flag)"
        :color="flagColor(Number(score))"
        size="x-small"
        label
        variant="tonal"
      >
        {{ flag }}: {{ Number(score).toFixed(2) }}
      </v-chip>
    </div>
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

const actionIcon = computed(() => {
  switch (props.decision.decision) {
    case 'BLOCK': return 'mdi-shield-alert'
    case 'MODIFY': return 'mdi-shield-edit'
    default: return 'mdi-shield-check'
  }
})

const actionLabel = computed(() => {
  switch (props.decision.decision) {
    case 'BLOCK': return 'Threat blocked before reaching model'
    case 'MODIFY': return 'Prompt sanitized before forwarding'
    default: return 'Request passed security scan'
  }
})

function flagColor(score: number): string {
  return _fc('', score)
}
</script>

<style lang="scss" scoped>
.compare-decision-card {
  background: rgba(var(--v-theme-surface-variant), 0.15);

  &.card--block {
    border-left: 3px solid rgb(var(--v-theme-error));
    background: rgba(var(--v-theme-error), 0.04);
  }

  &.card--modify {
    border-left: 3px solid rgb(var(--v-theme-warning));
    background: rgba(var(--v-theme-warning), 0.04);
  }

  &.card--allow {
    border-left: 3px solid rgb(var(--v-theme-success));
    background: rgba(var(--v-theme-success), 0.04);
  }

  .blocked-reason {
    display: flex;
    align-items: center;
    color: rgb(var(--v-theme-error));
    padding: 4px 8px;
    background: rgba(var(--v-theme-error), 0.06);
    border-radius: 4px;
  }

  :deep(.v-chip) {
    font-size: 12px !important;
  }
}
</style>
