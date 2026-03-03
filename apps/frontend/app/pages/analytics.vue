<script setup lang="ts">
import { useAnalytics } from '~/composables/useAnalytics'

definePageMeta({ title: 'Analytics' })

const {
  selectedRange,
  timeRanges,
  summary,
  summaryLoading,
  timeline,
  timelineLoading,
  byPolicy,
  byPolicyLoading,
  topFlags,
  topFlagsLoading,
  intents,
  intentsLoading,
  refreshAll,
  isRefreshing,
} = useAnalytics()
</script>

<template>
  <v-container fluid>
    <!-- Header -->
    <div class="d-flex align-center justify-space-between mb-4">
      <div>
        <h1 class="text-h4 font-weight-bold">Analytics</h1>
        <p class="text-body-2 text-medium-emphasis">
          Firewall performance and threat overview
        </p>
      </div>
      <div class="d-flex align-center ga-2">
        <v-btn-toggle v-model="selectedRange" mandatory variant="outlined" density="compact">
          <v-btn v-for="r in timeRanges" :key="r.value" :value="r.value" size="small">
            {{ r.label }}
          </v-btn>
        </v-btn-toggle>
        <v-btn icon="mdi-refresh" variant="text" :loading="isRefreshing" @click="refreshAll" />
      </div>
    </div>

    <!-- KPI Cards -->
    <analytics-kpi-cards :summary="summary" :loading="summaryLoading" class="mb-6" />

    <!-- Timeline Chart -->
    <v-card class="mb-6">
      <v-card-title class="text-subtitle-1">Request Volume</v-card-title>
      <v-card-text>
        <analytics-timeline-chart :data="timeline" :loading="timelineLoading" />
      </v-card-text>
    </v-card>

    <!-- Breakdown panels -->
    <v-row class="mb-4">
      <v-col cols="12" md="6">
        <analytics-policy-chart :data="byPolicy" :loading="byPolicyLoading" />
      </v-col>
      <v-col cols="12" md="6">
        <analytics-flags-list :data="topFlags" :loading="topFlagsLoading" />
      </v-col>
    </v-row>
    <v-row>
      <v-col cols="12" md="6">
        <analytics-intent-chart :data="intents" :loading="intentsLoading" />
      </v-col>
    </v-row>
  </v-container>
</template>
