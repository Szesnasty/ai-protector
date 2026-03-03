<template>
  <v-row>
    <v-col v-for="card in cards" :key="card.label" cols="12" sm="6" md="4" lg>
      <v-skeleton-loader v-if="loading" type="card" />
      <v-card v-else variant="outlined" class="h-100">
        <v-card-text class="d-flex align-center">
          <v-avatar :color="card.color" variant="tonal" size="48" class="mr-4">
            <v-icon :icon="card.icon" />
          </v-avatar>
          <div>
            <div class="text-caption text-medium-emphasis">{{ card.label }}</div>
            <div class="text-h5 font-weight-bold">{{ card.value }}</div>
            <div v-if="card.subtitle" class="text-caption text-medium-emphasis">{{ card.subtitle }}</div>
          </div>
        </v-card-text>
      </v-card>
    </v-col>
  </v-row>
</template>

<script setup lang="ts">
import type { AnalyticsSummary } from '~/types/api'

const props = defineProps<{
  summary: AnalyticsSummary | null | undefined
  loading: boolean
}>()

const cards = computed(() => {
  const s = props.summary
  return [
    {
      label: 'Total Requests',
      icon: 'mdi-chart-timeline-variant',
      color: 'primary',
      value: s?.total_requests ?? 0,
      subtitle: s ? `Avg risk: ${s.avg_risk.toFixed(2)}` : undefined,
    },
    {
      label: 'Block Rate',
      icon: 'mdi-shield-off',
      color: 'error',
      value: s ? `${(s.block_rate * 100).toFixed(1)}%` : '0%',
      subtitle: s ? `${s.blocked} blocked` : undefined,
    },
    {
      label: 'Modified',
      icon: 'mdi-shield-edit',
      color: 'warning',
      value: s?.modified ?? 0,
      subtitle: undefined,
    },
    {
      label: 'Allowed',
      icon: 'mdi-shield-check',
      color: 'success',
      value: s?.allowed ?? 0,
      subtitle: undefined,
    },
    {
      label: 'Avg Latency',
      icon: 'mdi-timer-outline',
      color: 'info',
      value: s ? `${s.avg_latency_ms.toFixed(0)}ms` : '0ms',
      subtitle: s?.top_intent ? `Top: ${s.top_intent}` : undefined,
    },
  ]
})
</script>
