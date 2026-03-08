<template>
  <div style="height: 320px;">
    <v-skeleton-loader v-if="loading" type="image" height="320" />
    <div v-else-if="!data?.length" class="d-flex align-center justify-center h-100 text-medium-emphasis">
      No data for this time range
    </div>
    <client-only v-else>
      <v-chart :option="chartOption" autoresize style="height: 100%;" />
    </client-only>
  </div>
</template>

<script setup lang="ts">
import type { TimelineBucket } from '~/types/api'
import { CHART } from '~/utils/colors'

const VChart = defineAsyncComponent(() => import('vue-echarts'))

const props = defineProps<{
  data: TimelineBucket[] | null | undefined
  loading: boolean
}>()

function formatLabel(iso: string): string {
  const d = new Date(iso)
  const now = new Date()
  const diffH = (now.getTime() - d.getTime()) / 3_600_000
  if (diffH <= 48) {
    return d.toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit' })
  }
  return d.toLocaleDateString('pl-PL', { month: '2-digit', day: '2-digit' })
}

const chartOption = computed(() => {
  const items = props.data ?? []
  const labels = items.map(b => formatLabel(b.time))

  return {
    tooltip: {
      trigger: 'axis',
    },
    legend: {
      top: 0,
      right: 0,
      data: ['Total', 'Blocked', 'Modified'],
    },
    grid: {
      left: 40,
      right: 16,
      top: 36,
      bottom: 28,
    },
    xAxis: {
      type: 'category',
      data: labels,
      axisTick: { show: false },
      axisLine: { lineStyle: { color: CHART.axisLine } },
      axisLabel: { color: CHART.axisLabel },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      axisLine: { show: false },
      axisLabel: { color: CHART.axisLabel },
      splitLine: { lineStyle: { type: 'dashed', color: CHART.gridLine } },
    },
    series: [
      {
        name: 'Total',
        type: 'line',
        data: items.map(b => b.total),
        smooth: true,
        areaStyle: { opacity: 0.08 },
        lineStyle: { width: 2 },
        itemStyle: { color: CHART.total },
      },
      {
        name: 'Blocked',
        type: 'line',
        data: items.map(b => b.blocked),
        smooth: true,
        areaStyle: { opacity: 0.18 },
        lineStyle: { width: 3 },
        itemStyle: { color: CHART.blocked },
        symbolSize: 8,
      },
      {
        name: 'Modified',
        type: 'line',
        data: items.map(b => b.modified),
        smooth: true,
        lineStyle: { width: 2, type: 'dashed' },
        itemStyle: { color: CHART.modified },
      },
    ],
  }
})
</script>
