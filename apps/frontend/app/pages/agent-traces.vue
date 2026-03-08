<script setup lang="ts">
import { useAgentTraces } from '~/composables/useAgentTraces'

definePageMeta({ title: 'Agent Traces' })

const {
  items,
  total,
  isLoading,
  filters,
  page,
  pageSize,
  fetchDetail,
  fetchExport,
  resetFilters,
  hasActiveFilters,
  refetch,
} = useAgentTraces()
</script>

<template>
  <v-container fluid>
    <div class="d-flex align-center mb-4">
      <div>
        <h1 class="text-h5 font-weight-bold">Agent Traces</h1>
        <p class="text-body-2 text-medium-emphasis">
          {{ total }} trace{{ total === 1 ? '' : 's' }} recorded
        </p>
      </div>
      <v-spacer />
      <v-chip v-if="hasActiveFilters" variant="tonal" size="small" class="mr-2">
        Filtered
      </v-chip>
      <v-btn
        icon="mdi-refresh"
        variant="text"
        size="small"
        :loading="isLoading"
        @click="refetch"
      >
        <v-icon>mdi-refresh</v-icon>
        <v-tooltip activator="parent" location="top">Refresh</v-tooltip>
      </v-btn>
    </div>

    <agent-traces-filters
      v-model="filters"
      :has-active="hasActiveFilters"
      @clear="resetFilters"
    />

    <agent-traces-table
      :items="items"
      :total="total"
      :loading="isLoading"
      v-model:page="page"
      v-model:page-size="pageSize"
      :fetch-detail="fetchDetail"
      :fetch-export="fetchExport"
    />
  </v-container>
</template>
