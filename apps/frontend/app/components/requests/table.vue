<template>
  <v-data-table-server
    v-model:items-per-page="localPageSize"
    v-model:page="localPage"
    v-model:expanded="expanded"
    :headers="headers"
    :items="items"
    :items-length="total"
    :loading="loading"
    :sort-by="localSortBy"
    item-value="id"
    show-expand
    density="comfortable"
    hover
    class="elevation-1 rounded"
    @update:sort-by="onSort"
  >
    <!-- Time -->
    <template #item.created_at="{ item }">
      <span class="text-caption text-no-wrap">{{ formatTime(item.created_at) }}</span>
    </template>

    <!-- Client -->
    <template #item.client_id="{ item }">
      <span class="text-caption font-weight-medium">{{ truncate(item.client_id, 12) }}</span>
    </template>

    <!-- Policy -->
    <template #item.policy_name="{ item }">
      <v-chip size="x-small" variant="tonal" color="primary">{{ item.policy_name || '—' }}</v-chip>
    </template>

    <!-- Intent -->
    <template #item.intent="{ item }">
      <v-chip v-if="item.intent" size="x-small" variant="outlined">{{ item.intent }}</v-chip>
      <span v-else class="text-medium-emphasis">—</span>
    </template>

    <!-- Decision -->
    <template #item.decision="{ item }">
      <v-chip
        :color="decisionColor(item.decision)"
        size="small"
        variant="flat"
        class="font-weight-bold"
      >
        {{ item.decision }}
      </v-chip>
    </template>

    <!-- Risk -->
    <template #item.risk_score="{ item }">
      <div class="d-flex align-center ga-2" style="min-width: 100px;">
        <v-progress-linear
          :model-value="(item.risk_score ?? 0) * 100"
          :color="riskColor(item.risk_score)"
          height="6"
          rounded
          style="max-width: 80px;"
        />
        <span class="text-caption">{{ item.risk_score != null ? item.risk_score.toFixed(2) : '—' }}</span>
      </div>
    </template>

    <!-- Latency -->
    <template #item.latency_ms="{ item }">
      <span class="text-caption">{{ item.latency_ms != null ? `${item.latency_ms}ms` : '—' }}</span>
    </template>

    <!-- Tokens -->
    <template #item.tokens_in="{ item }">
      <span class="text-caption">
        {{ item.tokens_in ?? '—' }}→{{ item.tokens_out ?? '—' }}
      </span>
    </template>

    <!-- Expanded row -->
    <template #expanded-row="{ columns, item }">
      <tr>
        <td :colspan="columns.length" class="pa-0">
          <requests-detail-row
            :detail="detailCache[item.id] ?? null"
            :loading="loadingDetails[item.id] ?? false"
          />
        </td>
      </tr>
    </template>

    <!-- No data -->
    <template #no-data>
      <div class="text-center py-6">
        <v-icon icon="mdi-text-search-variant" size="48" color="grey-lighten-1" />
        <p class="text-body-2 text-medium-emphasis mt-2">No requests found</p>
      </div>
    </template>
  </v-data-table-server>
</template>

<script setup lang="ts">
import type { RequestRead, RequestDetail } from '~/types/api'

const props = defineProps<{
  items: RequestRead[]
  total: number
  loading: boolean
  page: number
  pageSize: number
  sortBy: string
  sortOrder: 'asc' | 'desc'
  fetchDetail: (id: string) => Promise<RequestDetail>
}>()

const emit = defineEmits<{
  'update:page': [val: number]
  'update:pageSize': [val: number]
  'update:sortBy': [val: string]
  'update:sortOrder': [val: 'asc' | 'desc']
}>()

const headers = [
  { title: 'Time', key: 'created_at', sortable: true, width: '130px' },
  { title: 'Client', key: 'client_id', sortable: false, width: '120px' },
  { title: 'Policy', key: 'policy_name', sortable: false, width: '110px' },
  { title: 'Intent', key: 'intent', sortable: true, width: '100px' },
  { title: 'Decision', key: 'decision', sortable: true, width: '100px' },
  { title: 'Risk', key: 'risk_score', sortable: true, width: '140px' },
  { title: 'Latency', key: 'latency_ms', sortable: true, width: '90px' },
  { title: 'Tokens', key: 'tokens_in', sortable: false, width: '90px' },
]

const expanded = ref<string[]>([])
const detailCache = ref<Record<string, RequestDetail>>({})
const loadingDetails = ref<Record<string, boolean>>({})

const localPage = computed({
  get: () => props.page,
  set: (v) => emit('update:page', v),
})

const localPageSize = computed({
  get: () => props.pageSize,
  set: (v) => emit('update:pageSize', v),
})

const localSortBy = computed(() => [
  { key: props.sortBy, order: props.sortOrder },
])

function onSort(sortBy: Array<{ key: string; order: string }>) {
  const first = sortBy[0]
  if (first) {
    emit('update:sortBy', first.key)
    emit('update:sortOrder', first.order as 'asc' | 'desc')
  }
}

// Lazy‐load detail when row expands
watch(expanded, async (ids) => {
  for (const id of ids) {
    if (!detailCache.value[id] && !loadingDetails.value[id]) {
      loadingDetails.value[id] = true
      try {
        detailCache.value[id] = await props.fetchDetail(id)
      } catch (e) {
        console.error('Failed to load detail', id, e)
      } finally {
        loadingDetails.value[id] = false
      }
    }
  }
})

function formatTime(iso: string) {
  const d = new Date(iso)
  return d.toLocaleString('pl-PL', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function truncate(s: string, len: number) {
  return s.length > len ? `${s.slice(0, len)}…` : s
}

function decisionColor(d: string) {
  if (d === 'ALLOW') return 'success'
  if (d === 'MODIFY') return 'warning'
  if (d === 'BLOCK') return 'error'
  return 'grey'
}

function riskColor(score: number | null) {
  if (score == null) return 'grey'
  if (score < 0.3) return 'success'
  if (score < 0.6) return 'warning'
  return 'error'
}
</script>
