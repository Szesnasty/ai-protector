<template>
  <v-card>
    <v-card-title class="text-subtitle-1">Intent Distribution</v-card-title>
    <v-card-text>
      <v-skeleton-loader v-if="loading" type="image" height="260" />
      <div v-else-if="data?.length" style="max-width: 400px; margin: 0 auto;">
        <client-only>
          <v-chart :option="chartOption" autoresize style="height: 260px;" />
        </client-only>
      </div>
      <div v-else class="text-center text-medium-emphasis py-8">No intent data</div>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import type { IntentCount } from '~/types/api'

const VChart = defineAsyncComponent(() => import('vue-echarts'))

const props = defineProps<{
  data: IntentCount[] | null | undefined
  loading: boolean
}>()

const INTENT_COLORS = [
  '#2196F3',
  '#4CAF50',
  '#F44336',
  '#FF9800',
  '#9C27B0',
  '#00BCD4',
  '#795548',
  '#607D8B',
  '#E91E63',
  '#3F51B5',
]

const chartOption = computed(() => {
  const items = props.data ?? []
  const totalCount = items.reduce((sum, it) => sum + it.count, 0)

  return {
    tooltip: {
      trigger: 'item',
      formatter: (params: { name: string; value: number; percent: number }) =>
        `${params.name}: ${params.value} (${params.percent.toFixed(1)}%)`,
    },
    legend: {
      orient: 'vertical',
      right: 0,
      top: 'center',
      type: 'scroll',
      textStyle: { fontSize: 11 },
    },
    series: [
      {
        type: 'pie',
        radius: ['45%', '75%'],
        center: ['35%', '50%'],
        avoidLabelOverlap: true,
        label: {
          show: true,
          position: 'center',
          fontSize: 18,
          fontWeight: 'bold',
          formatter: () => String(totalCount),
          color: '#666',
        },
        emphasis: {
          label: {
            show: true,
            fontSize: 14,
            formatter: '{b}\n{c}',
          },
        },
        data: items.map((it, i) => ({
          value: it.count,
          name: it.intent,
          itemStyle: { color: INTENT_COLORS[i % INTENT_COLORS.length] },
        })),
      },
    ],
  }
})
</script>
