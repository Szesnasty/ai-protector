<template>
  <v-card>
    <v-card-title class="text-subtitle-1">Top Risk Flags</v-card-title>
    <v-card-text>
      <v-skeleton-loader v-if="loading" type="list-item-three-line@5" />
      <v-list v-else-if="data?.length" density="compact">
        <v-list-item v-for="(flag, i) in data" :key="flag.flag" class="px-0">
          <template #prepend>
            <span class="text-body-2 text-medium-emphasis mr-2" style="min-width: 20px;">{{ i + 1 }}.</span>
          </template>
          <v-list-item-title class="text-body-2">{{ formatFlagName(flag.flag) }}</v-list-item-title>
          <template #append>
            <span class="text-body-2 font-weight-bold mr-2">{{ flag.count }}</span>
            <span class="text-caption text-medium-emphasis">({{ (flag.pct * 100).toFixed(1) }}%)</span>
          </template>
          <v-progress-linear
            :model-value="flag.pct * 100"
            :color="flagColor(flag.flag)"
            height="4"
            class="mt-1"
          />
        </v-list-item>
      </v-list>
      <div v-else class="text-center text-medium-emphasis py-8">No flags recorded</div>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import type { RiskFlagCount } from '~/types/api'
import { analyticsFlagColor } from '~/utils/colors'

defineProps<{
  data: RiskFlagCount[] | null | undefined
  loading: boolean
}>()

function formatFlagName(flag: string): string {
  return flag
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase())
    .replace(/Pii/g, 'PII')
}

function flagColor(flag: string): string {
  return analyticsFlagColor(flag)
}
</script>
