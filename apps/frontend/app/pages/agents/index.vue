<template>
  <v-container fluid class="agents-page">
    <div class="d-flex align-center justify-space-between mb-6">
      <div>
        <h1 class="text-h5 mb-1">Agents</h1>
        <p class="text-body-2 text-medium-emphasis">
          Register, configure and monitor your AI agents
        </p>
      </div>
      <div class="d-flex ga-2">
        <v-btn
          variant="text"
          icon="mdi-book-open-outline"
          title="Integration Guide"
          @click="navigateTo('/agents/integration-guide')"
        />
        <v-btn variant="text" icon="mdi-refresh" :loading="isLoading" @click="refetch" />
        <v-btn color="primary" prepend-icon="mdi-plus" @click="navigateTo('/agents/new')">
          New Agent
        </v-btn>
      </div>
    </div>

    <!-- Search / Filter bar -->
    <v-row class="mb-4">
      <v-col cols="12" sm="6" md="4">
        <v-text-field
          v-model="search"
          prepend-inner-icon="mdi-magnify"
          label="Search agents"
          variant="outlined"
          density="compact"
          hide-details
          clearable
        />
      </v-col>
      <v-col cols="6" sm="3" md="2">
        <v-select
          v-model="riskFilter"
          :items="riskOptions"
          label="Risk"
          variant="outlined"
          density="compact"
          hide-details
          clearable
        />
      </v-col>
      <v-col cols="6" sm="3" md="2">
        <v-select
          v-model="rolloutFilter"
          :items="rolloutOptions"
          label="Rollout"
          variant="outlined"
          density="compact"
          hide-details
          clearable
        />
      </v-col>
    </v-row>

    <!-- Loading -->
    <div v-if="isLoading && !agents.length">
      <v-row>
        <v-col v-for="n in 3" :key="n" cols="12">
          <v-skeleton-loader type="table-row" />
        </v-col>
      </v-row>
    </div>

    <!-- Empty state -->
    <v-card
      v-else-if="!agents.length"
      variant="outlined"
      class="text-center pa-12"
    >
      <v-icon icon="mdi-robot-outline" size="80" color="primary" class="mb-4" />
      <h2 class="text-h6 mb-2">No agents registered yet</h2>
      <p class="text-body-2 text-medium-emphasis mb-6">
        Register your first agent to start protecting it with AI Protector
      </p>
      <v-btn color="primary" prepend-icon="mdi-plus" @click="navigateTo('/agents/new')">
        Register your first agent
      </v-btn>
    </v-card>

    <!-- Agent table -->
    <v-card v-else variant="outlined">
      <v-data-table
        :headers="headers"
        :items="filteredAgents"
        :items-per-page="20"
        hover
        class="agents-table"
        @click:row="(_: unknown, row: { item: AgentRead }) => navigateTo(`/agents/${row.item.id}`)"
      >
        <template #item.name="{ item }">
          <div class="d-flex align-center ga-2">
            <v-icon icon="mdi-robot-outline" size="18" />
            <div>
              <div class="font-weight-medium">{{ item.name }}</div>
              <div class="text-caption text-medium-emphasis text-truncate" style="max-width: 300px">
                {{ item.description || '—' }}
              </div>
            </div>
          </div>
        </template>

        <template #item.risk_level="{ item }">
          <v-chip
            v-if="item.risk_level"
            :color="riskColor(item.risk_level)"
            size="small"
            variant="tonal"
          >
            {{ item.risk_level }}
          </v-chip>
          <span v-else class="text-medium-emphasis">—</span>
        </template>

        <template #item.rollout_mode="{ item }">
          <v-chip
            :color="rolloutColor(item.rollout_mode)"
            size="small"
            variant="tonal"
          >
            {{ item.rollout_mode }}
          </v-chip>
        </template>

        <template #item.tools="{ item }">
          {{ item.generated_config ? '✓' : '—' }}
        </template>

        <template #item.created_at="{ item }">
          <span class="text-caption">{{ formatDate(item.created_at) }}</span>
        </template>

        <template #item.actions="{ item }">
          <div class="d-flex ga-1" @click.stop>
            <v-btn size="x-small" variant="text" icon="mdi-pencil" @click="navigateTo(`/agents/${item.id}/edit`)" />
            <v-btn size="x-small" variant="text" icon="mdi-delete" color="red" @click="confirmDelete(item)" />
          </div>
        </template>
      </v-data-table>

      <!-- Delete confirmation dialog -->
      <v-dialog v-model="showDeleteDialog" max-width="440">
        <v-card>
          <v-card-title class="text-h6">Delete Agent</v-card-title>
          <v-card-text>
            Are you sure you want to delete <strong>{{ agentToDelete?.name }}</strong>?
            This action cannot be undone.
          </v-card-text>
          <v-card-actions>
            <v-spacer />
            <v-btn variant="text" @click="showDeleteDialog = false">Cancel</v-btn>
            <v-btn color="red" variant="flat" :loading="isDeleting" @click="doDelete">Delete</v-btn>
          </v-card-actions>
        </v-card>
      </v-dialog>
    </v-card>
  </v-container>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useAgents } from '~/composables/useAgents'
import type { AgentRead, RiskLevel, RolloutMode } from '~/types/wizard'

definePageMeta({ title: 'Agents' })

const search = ref('')
const riskFilter = ref<string | null>(null)
const rolloutFilter = ref<string | null>(null)

const riskOptions = ['low', 'medium', 'high', 'critical']
const rolloutOptions = ['observe', 'warn', 'enforce']

// Debounced search value sent to the server
const debouncedSearch = ref<string | undefined>(undefined)
let searchTimeout: ReturnType<typeof setTimeout> | null = null
watch(search, (v) => {
  if (searchTimeout) clearTimeout(searchTimeout)
  searchTimeout = setTimeout(() => {
    debouncedSearch.value = v?.trim() || undefined
  }, 300)
})

const riskLevel = computed(() => riskFilter.value || undefined)
const rolloutMode = computed(() => rolloutFilter.value || undefined)

const { agents, isLoading, refetch, deleteAgent, isDeleting } = useAgents({
  search: debouncedSearch,
  riskLevel,
  rolloutMode,
})

// No client-side filtering needed — server handles search + filters
const filteredAgents = computed(() => agents.value)

const headers = [
  { title: 'Agent', key: 'name', sortable: true },
  { title: 'Risk', key: 'risk_level', sortable: true, width: '120' },
  { title: 'Rollout', key: 'rollout_mode', sortable: true, width: '120' },
  { title: 'Config', key: 'tools', sortable: false, width: '80' },
  { title: 'Created', key: 'created_at', sortable: true, width: '160' },
  { title: '', key: 'actions', sortable: false, width: '100' },
]

const riskColor = (level: RiskLevel): string =>
  ({ low: 'green', medium: 'amber', high: 'orange', critical: 'red' })[level] ?? 'grey'

const rolloutColor = (mode: RolloutMode): string =>
  ({ observe: 'blue', warn: 'amber', enforce: 'green' })[mode] ?? 'grey'

// ─── Delete ───
const showDeleteDialog = ref(false)
const agentToDelete = ref<AgentRead | null>(null)

const confirmDelete = (agent: AgentRead) => {
  agentToDelete.value = agent
  showDeleteDialog.value = true
}

const doDelete = async () => {
  if (!agentToDelete.value) return
  try {
    await deleteAgent(agentToDelete.value.id)
    showDeleteDialog.value = false
    agentToDelete.value = null
  }
  catch { /* */ }
}

const formatDate = (iso: string): string => {
  const d = new Date(iso)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  const mins = Math.floor(diff / 60_000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days}d ago`
  return d.toLocaleDateString()
}
</script>

<style lang="scss" scoped>
.agents-table {
  :deep(tr) {
    cursor: pointer;
  }
}
</style>
