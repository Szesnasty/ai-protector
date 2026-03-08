<template>
  <v-data-table-server
    v-model:items-per-page="localPageSize"
    v-model:page="localPage"
    v-model:expanded="expanded"
    :headers="headers"
    :items="items"
    :items-length="total"
    :loading="loading"
    item-value="trace_id"
    show-expand
    density="comfortable"
    hover
    class="elevation-1 rounded-lg"
  >
    <!-- Time -->
    <template #item.timestamp="{ item }">
      <span class="text-caption text-no-wrap">{{ formatTime(item.timestamp) }}</span>
    </template>

    <!-- Role -->
    <template #item.user_role="{ item }">
      <v-chip
        size="x-small"
        variant="tonal"
      >
        {{ item.user_role }}
      </v-chip>
    </template>

    <!-- Intent -->
    <template #item.intent="{ item }">
      <v-chip v-if="item.intent" size="x-small" variant="outlined">{{ item.intent }}</v-chip>
      <span v-else class="text-medium-emphasis">—</span>
    </template>

    <!-- Model -->
    <template #item.model="{ item }">
      <span class="text-caption">{{ item.model || '—' }}</span>
    </template>

    <!-- Iterations -->
    <template #item.iterations_count="{ item }">
      <span class="text-caption">{{ item.iterations_count }}</span>
    </template>

    <!-- Tools -->
    <template #item.tool_calls_count="{ item }">
      <div class="d-flex align-center ga-1">
        <span class="text-caption">{{ item.tool_calls_count }}</span>
        <v-chip v-if="item.firewall_blocked" size="x-small" color="error" variant="flat">
          blocked
        </v-chip>
        <v-chip v-if="item.tool_calls_blocked > 0" size="x-small" color="error" variant="flat">
          {{ item.tool_calls_blocked }} blocked
        </v-chip>
      </div>
    </template>

    <!-- Duration -->
    <template #item.total_duration_ms="{ item }">
      <span class="text-caption">{{ item.total_duration_ms }}ms</span>
    </template>

    <!-- Tokens -->
    <template #item.tokens_in="{ item }">
      <span class="text-caption">{{ item.tokens_in ?? '—' }}→{{ item.tokens_out ?? '—' }}</span>
    </template>

    <!-- Status icons -->
    <template #item.status="{ item }">
      <div class="d-flex align-center ga-1">
        <span v-if="item.has_errors">
          <v-icon icon="mdi-alert-circle" color="error" size="20" />
          <v-tooltip activator="parent" location="top">Agent encountered errors during execution</v-tooltip>
        </span>
        <span v-if="item.limits_hit">
          <v-icon icon="mdi-speedometer" color="warning" size="20" />
          <v-tooltip activator="parent" location="top">Rate or budget limit was reached</v-tooltip>
        </span>
        <span v-if="item.firewall_blocked">
          <v-icon icon="mdi-shield-lock" color="error" size="20" />
          <v-tooltip activator="parent" location="top">Request blocked by the LLM Firewall — prompt was rejected before reaching the model</v-tooltip>
        </span>
        <span v-if="item.tool_calls_blocked > 0">
          <v-icon icon="mdi-shield-off" color="error" size="20" />
          <v-tooltip activator="parent" location="top">{{ item.tool_calls_blocked }} tool call{{ item.tool_calls_blocked > 1 ? 's' : '' }} blocked by security policy</v-tooltip>
        </span>
        <span v-if="!item.has_errors && !item.limits_hit && !item.firewall_blocked && item.tool_calls_blocked === 0">
          <v-icon icon="mdi-check-circle" color="success" size="20" />
          <v-tooltip activator="parent" location="top">Request completed successfully — no security issues detected</v-tooltip>
        </span>
      </div>
    </template>

    <!-- Actions -->
    <template #item.actions="{ item }">
      <v-btn
        icon="mdi-download"
        size="x-small"
        variant="text"
        :loading="exportingId === item.trace_id"
        @click.stop="exportTrace(item.trace_id)"
      >
        <v-icon size="20">mdi-download</v-icon>
        <v-tooltip activator="parent" location="top">Export JSON</v-tooltip>
      </v-btn>
    </template>

    <!-- Expanded row -->
    <template #expanded-row="{ columns, item }">
      <tr>
        <td :colspan="columns.length" class="pa-0">
          <agent-traces-detail-row
            :detail="detailCache[item.trace_id] ?? null"
            :loading="loadingDetails[item.trace_id] ?? false"
          />
        </td>
      </tr>
    </template>

    <!-- No data -->
    <template #no-data>
      <div class="text-center py-6">
        <v-icon icon="mdi-chart-timeline-variant" size="48" color="grey-lighten-1" />
        <p class="text-body-2 text-medium-emphasis mt-2">No agent traces found</p>
        <p class="text-caption text-medium-emphasis">Send messages in the Agent Demo to generate traces</p>
      </div>
    </template>
  </v-data-table-server>
</template>

<script setup lang="ts">
import type { AgentTraceSummary, AgentTraceDetail, AgentTraceExport } from '~/types/agentTrace'

const props = defineProps<{
  items: AgentTraceSummary[]
  total: number
  loading: boolean
  page: number
  pageSize: number
  fetchDetail: (id: string) => Promise<AgentTraceDetail>
  fetchExport: (id: string) => Promise<AgentTraceExport>
}>()

const emit = defineEmits<{
  'update:page': [val: number]
  'update:pageSize': [val: number]
}>()

const headers = [
  { title: 'Time', key: 'timestamp', sortable: false, width: '130px' },
  { title: 'Role', key: 'user_role', sortable: false, width: '90px' },
  { title: 'Intent', key: 'intent', sortable: false, width: '120px' },
  { title: 'Model', key: 'model', sortable: false, width: '130px' },
  { title: 'Iters', key: 'iterations_count', sortable: false, width: '60px' },
  { title: 'Tools', key: 'tool_calls_count', sortable: false, width: '120px' },
  { title: 'Duration', key: 'total_duration_ms', sortable: false, width: '90px' },
  { title: 'Tokens', key: 'tokens_in', sortable: false, width: '90px' },
  { title: '', key: 'status', sortable: false, width: '60px' },
  { title: '', key: 'actions', sortable: false, width: '50px' },
]

const expanded = ref<string[]>([])
const detailCache = ref<Record<string, AgentTraceDetail>>({})
const loadingDetails = ref<Record<string, boolean>>({})
const exportingId = ref<string | null>(null)

const localPage = computed({
  get: () => props.page,
  set: (v) => emit('update:page', v),
})

const localPageSize = computed({
  get: () => props.pageSize,
  set: (v) => emit('update:pageSize', v),
})

// Lazy-load detail when row expands
watch(expanded, async (ids) => {
  for (const id of ids) {
    if (!detailCache.value[id] && !loadingDetails.value[id]) {
      loadingDetails.value[id] = true
      try {
        detailCache.value[id] = await props.fetchDetail(id)
      } catch (e) {
        console.error('Failed to load trace detail', id, e)
      } finally {
        loadingDetails.value[id] = false
      }
    }
  }
})

async function exportTrace(traceId: string) {
  exportingId.value = traceId
  try {
    const data = await props.fetchExport(traceId)
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `trace-${traceId.slice(0, 8)}.json`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    console.error('Export failed', e)
  } finally {
    exportingId.value = null
  }
}

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
</script>
