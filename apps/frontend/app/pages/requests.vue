<script setup lang="ts">
import { usePolicies } from '~/composables/usePolicies'
import { useRequestLog } from '~/composables/useRequestLog'

definePageMeta({ title: 'Request Log' })

const { policies } = usePolicies()
const {
  data,
  isLoading,
  filters,
  page,
  pageSize,
  sortBy,
  sortOrder,
  fetchDetail,
  resetFilters,
  hasActiveFilters,
} = useRequestLog()

const items = computed(() => data.value?.items ?? [])
const total = computed(() => data.value?.total ?? 0)
</script>

<template>
  <v-container fluid>
    <div class="d-flex align-center mb-4">
      <div>
        <h1 class="text-h5 font-weight-bold">Request Log</h1>
        <p class="text-body-2 text-medium-emphasis">
          {{ total }} request{{ total === 1 ? '' : 's' }} recorded
        </p>
      </div>
      <v-spacer />
      <v-chip v-if="hasActiveFilters" variant="tonal" size="small" class="mr-2">
        Filtered
      </v-chip>
    </div>

    <requests-filters
      v-model="filters"
      :policies="policies ?? undefined"
      :has-active="hasActiveFilters"
      @clear="resetFilters"
    />

    <requests-table
      :items="items"
      :total="total"
      :loading="isLoading"
      v-model:page="page"
      v-model:page-size="pageSize"
      v-model:sort-by="sortBy"
      v-model:sort-order="sortOrder"
      :fetch-detail="fetchDetail"
    />
  </v-container>
</template>
