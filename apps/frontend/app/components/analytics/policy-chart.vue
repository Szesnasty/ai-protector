<template>
  <v-card>
    <v-card-title class="text-subtitle-1">Block Rate by Policy</v-card-title>
    <v-card-text>
      <v-skeleton-loader v-if="loading" type="image" height="160" />
      <template v-else-if="data?.length">
        <client-only>
          <v-chart :option="chartOption" autoresize style="height: 160px;" />
        </client-only>
        <v-table density="compact" class="mt-3 text-caption">
          <thead>
            <tr>
              <th>Policy</th>
              <th class="text-right">Total</th>
              <th class="text-right">Blocked</th>
              <th class="text-right">Block Rate</th>
              <th class="text-right">Avg Risk</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in data" :key="p.policy_id">
              <td>
                <v-chip :color="policyColor(p.policy_name)" size="x-small" variant="tonal">{{ p.policy_name }}</v-chip>
              </td>
              <td class="text-right">{{ p.total }}</td>
              <td class="text-right">{{ p.blocked }}</td>
              <td class="text-right">{{ (p.block_rate * 100).toFixed(1) }}%</td>
              <td class="text-right">{{ p.avg_risk.toFixed(2) }}</td>
            </tr>
          </tbody>
        </v-table>
      </template>
      <div v-else class="text-center text-medium-emphasis py-8">No policy data</div>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import type { PolicyStatsRow } from '~/types/api'
import { CHART, policyColor } from '~/utils/colors'

const VChart = defineAsyncComponent(() => import('vue-echarts'))

const props = defineProps<{
  data: PolicyStatsRow[] | null | undefined
  loading: boolean
}>()

const COLOR_MAP: Record<string, string> = {
  fast: CHART.policyFast,
  balanced: CHART.policyBalanced,
  strict: CHART.policyStrict,
  paranoid: CHART.policyParanoid,
}

const chartOption = computed(() => {
  const items = props.data ?? []
  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: Array<{ name: string; value: number }>) => {
        const p = params[0]
        if (!p) return ''
        const row = items.find(r => r.policy_name === p.name)
        if (!row) return p.name
        return `${p.name}: ${row.blocked}/${row.total} blocked (${(row.block_rate * 100).toFixed(1)}%)`
      },
    },
    grid: { left: 80, right: 20, top: 8, bottom: 20 },
    xAxis: {
      type: 'value',
      max: 100,
      axisLabel: { formatter: '{value}%', color: CHART.axisLabel },
      splitLine: { lineStyle: { color: CHART.gridLine } },
    },
    yAxis: {
      type: 'category',
      data: items.map(p => p.policy_name),
      inverse: true,
      axisLabel: { color: CHART.axisLabel },
    },
    series: [
      {
        type: 'bar',
        data: items.map(p => ({
          value: +(p.block_rate * 100).toFixed(1),
          itemStyle: { color: COLOR_MAP[p.policy_name] ?? CHART.policyDefault },
        })),
        barWidth: 18,
        label: {
          show: true,
          position: 'right',
          formatter: '{c}%',
          fontSize: 11,
        },
      },
    ],
  }
})
</script>
