<template>
  <v-container fluid class="agent-detail-page">
    <!-- Header -->
    <div v-if="agent" class="d-flex align-center justify-space-between mb-4">
      <div class="d-flex align-center">
        <v-btn icon="mdi-arrow-left" variant="text" @click="navigateTo('/agents')" />
        <div class="ml-2">
          <h1 class="text-h5">{{ agent.name }}</h1>
          <v-breadcrumbs :items="breadcrumbs" density="compact" class="pa-0" />
        </div>
      </div>
      <div class="d-flex ga-2 align-center">
        <v-chip :color="riskColor(agent.risk_level)" variant="tonal" size="small">
          {{ agent.risk_level ?? 'TBD' }}
        </v-chip>
        <v-chip :color="rolloutColor(agent.rollout_mode)" variant="tonal" size="small">
          {{ agent.rollout_mode }}
        </v-chip>
        <v-btn size="small" variant="text" icon="mdi-pencil" @click="navigateTo(`/agents/${agent.id}/edit`)" />
        <v-btn size="small" variant="text" icon="mdi-delete" color="red" @click="showDeleteDialog = true" />
      </div>
    </div>

    <!-- Delete confirmation dialog -->
    <v-dialog v-model="showDeleteDialog" max-width="440">
      <v-card>
        <v-card-title class="text-h6">Delete Agent</v-card-title>
        <v-card-text>
          Are you sure you want to delete <strong>{{ agent?.name }}</strong>?
          This action cannot be undone.
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="showDeleteDialog = false">Cancel</v-btn>
          <v-btn color="red" variant="flat" :loading="isDeleting" @click="doDelete">Delete</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <div v-if="loading" class="text-center py-12">
      <v-progress-circular indeterminate size="48" />
    </div>

    <template v-else-if="agent">
      <v-tabs v-model="activeTab" density="compact" class="mb-4">
        <v-tab value="overview">Overview</v-tab>
        <v-tab value="tools">Tools</v-tab>
        <v-tab value="roles">Roles</v-tab>
        <v-tab value="config">Config</v-tab>
        <v-tab value="kit">Integration Kit</v-tab>
        <v-tab value="validation">Validation</v-tab>
        <v-tab value="traces">Traces</v-tab>
        <v-tab value="incidents">Incidents</v-tab>
      </v-tabs>

      <v-tabs-window v-model="activeTab">
        <!-- Overview -->
        <v-tabs-window-item value="overview">
          <v-row>
            <v-col cols="12" md="6">
              <v-card variant="outlined" class="pa-4">
                <h3 class="text-subtitle-1 mb-3">Agent Details</h3>
                <v-list density="compact">
                  <v-list-item>
                    <template #title>Description</template>
                    <template #subtitle>{{ agent.description || '—' }}</template>
                  </v-list-item>
                  <v-list-item>
                    <template #title>Framework</template>
                    <template #subtitle>{{ agent.framework }}</template>
                  </v-list-item>
                  <v-list-item>
                    <template #title>Environment</template>
                    <template #subtitle>{{ agent.environment }}</template>
                  </v-list-item>
                  <v-list-item>
                    <template #title>Team</template>
                    <template #subtitle>{{ agent.team || '—' }}</template>
                  </v-list-item>
                  <v-list-item>
                    <template #title>Status</template>
                    <template #subtitle>{{ agent.status }}</template>
                  </v-list-item>
                  <v-list-item>
                    <template #title>Created</template>
                    <template #subtitle>{{ new Date(agent.created_at).toLocaleString() }}</template>
                  </v-list-item>
                </v-list>
              </v-card>
            </v-col>
            <v-col cols="12" md="6">
              <v-card variant="outlined" class="pa-4">
                <h3 class="text-subtitle-1 mb-3">Rollout</h3>
                <div class="d-flex align-center ga-2 mb-4">
                  <span class="text-body-2">Current mode:</span>
                  <v-chip :color="rolloutColor(agent.rollout_mode)" variant="tonal">
                    {{ agent.rollout_mode }}
                  </v-chip>
                </div>

                <template v-if="readiness">
                  <div v-if="readiness.blockers.length" class="mb-3">
                    <p class="text-caption text-medium-emphasis mb-1">Blockers:</p>
                    <v-alert
                      v-for="(b, i) in readiness.blockers"
                      :key="i"
                      type="warning"
                      variant="tonal"
                      density="compact"
                      class="mb-1"
                    >
                      {{ b }}
                    </v-alert>
                  </div>

                  <div class="d-flex ga-2">
                    <v-btn
                      v-for="target in readiness.can_promote_to"
                      :key="target"
                      size="small"
                      :color="rolloutColor(target)"
                      variant="tonal"
                      :loading="isPromoting"
                      @click="doPromote(target)"
                    >
                      Promote to {{ target }}
                    </v-btn>
                    <v-btn
                      v-if="agent.rollout_mode !== 'observe'"
                      size="small"
                      variant="text"
                      @click="doPromote(agent.rollout_mode === 'enforce' ? 'warn' : 'observe')"
                    >
                      Demote
                    </v-btn>
                  </div>
                </template>

                <div class="mt-4">
                  <h4 class="text-subtitle-2 mb-2">Risk Factors</h4>
                  <v-chip v-if="agent.is_public_facing" size="x-small" class="mr-1 mb-1" color="orange">Public</v-chip>
                  <v-chip v-if="agent.has_write_actions" size="x-small" class="mr-1 mb-1" color="amber">Write actions</v-chip>
                  <v-chip v-if="agent.touches_pii" size="x-small" class="mr-1 mb-1" color="red">PII</v-chip>
                  <v-chip v-if="agent.handles_secrets" size="x-small" class="mr-1 mb-1" color="red">Secrets</v-chip>
                  <v-chip v-if="agent.calls_external_apis" size="x-small" class="mr-1 mb-1" color="amber">External APIs</v-chip>
                </div>
              </v-card>
            </v-col>
          </v-row>
        </v-tabs-window-item>

        <!-- Tools -->
        <v-tabs-window-item value="tools">
          <v-card variant="outlined">
            <v-list v-if="tools.length" lines="two">
              <v-list-item
                v-for="tool in tools"
                :key="tool.id"
                :title="tool.name"
                :subtitle="tool.description || 'No description'"
              >
                <template #prepend>
                  <v-icon icon="mdi-wrench" />
                </template>
                <template #append>
                  <v-chip :color="sensitivityColor(tool.sensitivity)" size="x-small" class="mr-2">
                    {{ tool.sensitivity }}
                  </v-chip>
                  <v-chip size="x-small" variant="tonal">{{ tool.access_type }}</v-chip>
                </template>
              </v-list-item>
            </v-list>
            <div v-else class="text-center py-8 text-medium-emphasis">
              No tools registered
            </div>
          </v-card>
        </v-tabs-window-item>

        <!-- Roles -->
        <v-tabs-window-item value="roles">
          <v-card variant="outlined">
            <v-list v-if="roles.length" lines="two">
              <v-list-item
                v-for="role in roles"
                :key="role.id"
                :title="role.name"
                :subtitle="role.description || 'No description'"
              >
                <template #prepend>
                  <v-icon icon="mdi-shield-account" />
                </template>
                <template #append>
                  <v-chip size="x-small" variant="tonal">
                    {{ effectivePermCount(role) }} tools
                  </v-chip>
                </template>
              </v-list-item>
            </v-list>
            <div v-else class="text-center py-8 text-medium-emphasis">
              No roles defined
            </div>

            <!-- Permission Matrix -->
            <template v-if="permMatrix">
              <v-divider />
              <div class="pa-4">
                <p class="text-subtitle-2 mb-3">Permission Matrix</p>
                <v-table density="compact">
                  <thead>
                    <tr>
                      <th>Role / Tool</th>
                      <th v-for="tool in permMatrix.tools" :key="tool" class="text-center">{{ tool }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="role in permMatrix.roles" :key="role">
                      <td class="font-weight-medium">{{ role }}</td>
                      <td v-for="tool in permMatrix.tools" :key="tool" class="text-center">
                        <v-icon
                          :icon="permMatrix.matrix[role]?.[tool] === 'allow' ? 'mdi-check-circle' : 'mdi-close-circle'"
                          :color="permMatrix.matrix[role]?.[tool] === 'allow' ? 'green' : 'red'"
                          size="18"
                        />
                      </td>
                    </tr>
                  </tbody>
                </v-table>
              </div>
            </template>
          </v-card>
        </v-tabs-window-item>

        <!-- Config -->
        <v-tabs-window-item value="config">
          <v-card variant="outlined" class="pa-4">
            <div class="d-flex justify-space-between mb-3">
              <h3 class="text-subtitle-1">Generated Configuration</h3>
              <v-btn size="small" variant="tonal" prepend-icon="mdi-refresh" :loading="configGenerating" @click="regenerateConfig">
                Re-generate
              </v-btn>
            </div>
            <template v-if="config">
              <v-tabs v-model="configTab" density="compact" class="mb-2">
                <v-tab value="rbac">RBAC</v-tab>
                <v-tab value="limits">Limits</v-tab>
                <v-tab value="policy">Policy</v-tab>
              </v-tabs>
              <v-card variant="outlined" class="config-preview pa-3">
                <pre class="text-caption">{{ configContent }}</pre>
              </v-card>
            </template>
            <div v-else class="text-center py-8 text-medium-emphasis">
              No configuration generated yet
            </div>
          </v-card>
        </v-tabs-window-item>

        <!-- Integration Kit -->
        <v-tabs-window-item value="kit">
          <v-card variant="outlined" class="pa-4">
            <div class="d-flex justify-space-between mb-3">
              <h3 class="text-subtitle-1">Integration Kit</h3>
              <div class="d-flex ga-2">
                <v-btn size="small" variant="tonal" prepend-icon="mdi-refresh" :loading="kitGenerating" @click="regenerateKit">
                  Re-generate
                </v-btn>
                <v-btn v-if="kit" size="small" variant="tonal" prepend-icon="mdi-download" @click="downloadKit">
                  Download ZIP
                </v-btn>
              </div>
            </div>
            <template v-if="kit?.files">
              <v-tabs v-model="kitTab" density="compact" class="mb-2">
                <v-tab v-for="fname in Object.keys(kit.files)" :key="fname" :value="fname">
                  {{ fname }}
                </v-tab>
              </v-tabs>
              <v-card variant="outlined" class="config-preview pa-3">
                <pre class="text-caption">{{ kit.files[kitTab] ?? '' }}</pre>
              </v-card>
            </template>
            <div v-else class="text-center py-8 text-medium-emphasis">
              No integration kit generated yet
            </div>
          </v-card>
        </v-tabs-window-item>

        <!-- Validation -->
        <v-tabs-window-item value="validation">
          <v-card variant="outlined" class="pa-4">
            <div class="d-flex justify-space-between mb-3">
              <h3 class="text-subtitle-1">Validation Results</h3>
              <v-btn size="small" color="primary" prepend-icon="mdi-play" :loading="validationRunning" @click="runValidation">
                {{ latestValidation ? 'Re-run' : 'Run Validation' }}
              </v-btn>
            </div>
            <template v-if="latestValidation">
              <v-card
                :color="latestValidation.passed === latestValidation.total ? 'success' : 'error'"
                variant="tonal"
                class="mb-4 pa-3 text-center"
              >
                <div class="text-h4 font-weight-bold">{{ latestValidation.passed }}/{{ latestValidation.total }}</div>
                <div>{{ latestValidation.passed === latestValidation.total ? 'All tests passed' : `${latestValidation.failed} failed` }}</div>
              </v-card>
              <v-list density="compact">
                <v-list-item
                  v-for="(r, i) in validationTests"
                  :key="i"
                >
                  <template #prepend>
                    <v-icon
                      :icon="r.passed ? 'mdi-check-circle' : 'mdi-close-circle'"
                      :color="r.passed ? 'green' : 'red'"
                      size="18"
                      class="mr-3"
                    />
                  </template>
                  <v-list-item-title>{{ r.name }}</v-list-item-title>
                  <v-list-item-subtitle>
                    <span class="text-medium-emphasis">{{ r.category }}</span>
                    <span v-if="!r.passed" class="ml-2">— expected {{ r.expected }}, got {{ r.actual }}</span>
                    <span v-if="r.recommendation" class="ml-2 text-warning">• {{ r.recommendation }}</span>
                  </v-list-item-subtitle>
                </v-list-item>
              </v-list>
            </template>
            <div v-else class="text-center py-8 text-medium-emphasis">
              No validation runs yet
            </div>
          </v-card>
        </v-tabs-window-item>

        <!-- Traces -->
        <v-tabs-window-item value="traces">
          <v-card variant="outlined" class="pa-4">
            <h3 class="text-subtitle-1 mb-3">Agent Traces</h3>
            <v-data-table
              v-if="traces.length"
              :headers="traceHeaders"
              :items="traces"
              :items-per-page="20"
              density="compact"
            >
              <template #item.decision="{ item }">
                <v-chip
                  :color="decisionColor(item.decision)"
                  size="x-small"
                  variant="tonal"
                >
                  {{ item.decision }}
                </v-chip>
              </template>
              <template #item.gate="{ item }">
                <v-chip size="x-small" variant="tonal">{{ item.gate }}</v-chip>
              </template>
              <template #item.timestamp="{ item }">
                {{ new Date(item.timestamp).toLocaleString() }}
              </template>
            </v-data-table>
            <div v-else class="text-center py-8 text-medium-emphasis">
              No traces recorded yet
            </div>
          </v-card>
        </v-tabs-window-item>

        <!-- Incidents -->
        <v-tabs-window-item value="incidents">
          <v-card variant="outlined" class="pa-4">
            <h3 class="text-subtitle-1 mb-3">Incidents</h3>
            <v-data-table
              v-if="incidents.length"
              :headers="incidentHeaders"
              :items="incidents"
              :items-per-page="20"
              density="compact"
            >
              <template #item.severity="{ item }">
                <v-chip :color="severityColor(item.severity)" size="x-small" variant="tonal">
                  {{ item.severity }}
                </v-chip>
              </template>
              <template #item.status="{ item }">
                <v-select
                  :model-value="item.status"
                  :items="incidentStatuses"
                  variant="plain"
                  density="compact"
                  hide-details
                  style="max-width: 160px"
                  @update:model-value="(v: string) => updateIncidentStatus(item.id, v as IncidentStatus)"
                />
              </template>
              <template #item.first_seen="{ item }">
                {{ new Date(item.first_seen).toLocaleString() }}
              </template>
            </v-data-table>
            <div v-else class="text-center py-8 text-medium-emphasis">
              No incidents recorded yet
            </div>
          </v-card>
        </v-tabs-window-item>
      </v-tabs-window>
    </template>

    <v-alert v-else-if="error" type="error" variant="tonal">
      Failed to load agent
    </v-alert>
  </v-container>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useAgents } from '~/composables/useAgents'
import { useAgentTools } from '~/composables/useAgentTools'
import { useAgentRoles } from '~/composables/useAgentRoles'
import { useAgentConfig } from '~/composables/useAgentConfig'
import { useAgentKit } from '~/composables/useAgentKit'
import { useAgentValidation } from '~/composables/useAgentValidation'
import { useAgentRollout } from '~/composables/useAgentRollout'
import { useAgentTracesList, useAgentIncidents } from '~/composables/useWizardTraces'
import type { AgentRead, RoleRead, RolloutMode, Sensitivity, IncidentSeverity, IncidentStatus } from '~/types/wizard'

definePageMeta({ title: 'Agent Detail' })

const route = useRoute()
const agentId = computed(() => route.params.id as string)

const loading = ref(true)
const agent = ref<AgentRead | null>(null)
const error = ref(false)
const activeTab = ref('overview')
const showDeleteDialog = ref(false)

const { getAgent, deleteAgent, isDeleting } = useAgents()
const { tools } = useAgentTools(() => agentId.value)
const { roles, matrix: permMatrix } = useAgentRoles(() => agentId.value)
const { config, generate: genConfig, isGenerating: configGenerating } = useAgentConfig(() => agentId.value)
const { kit, generate: genKit, isGenerating: kitGenerating, download: downloadKit } = useAgentKit(() => agentId.value)
const { latest: latestValidation, run: runVal, isRunning: validationRunning } = useAgentValidation(() => agentId.value)
const { readiness, promote, isPromoting } = useAgentRollout(() => agentId.value)
const { traces } = useAgentTracesList(() => agentId.value)
const { incidents, updateIncident } = useAgentIncidents(() => agentId.value)

const configTab = ref('rbac')
const kitTab = ref('')

// Count effective (direct + inherited) permissions for a role
const effectivePermCount = (role: RoleRead) => {
  const directIds = new Set(role.permissions.map(p => p.tool_id))
  const inheritedIds = (role.inherited_permissions ?? []).map(p => p.tool_id)
  for (const id of inheritedIds) directIds.add(id)
  return directIds.size
}

// Extract test results from the validation run's results dict
const validationTests = computed(() => {
  if (!latestValidation.value) return []
  const res = latestValidation.value.results
  if (res && Array.isArray(res.tests)) return res.tests
  return []
})

const breadcrumbs = computed(() => [
  { title: 'Agents', to: '/agents' },
  { title: agent.value?.name ?? 'Agent' },
])

const configContent = computed(() => {
  if (!config.value) return ''
  const c = config.value as unknown as Record<string, string>
  const map: Record<string, string> = {
    rbac: c.rbac_yaml ?? '',
    limits: c.limits_yaml ?? '',
    policy: c.policy_yaml ?? '',
  }
  return map[configTab.value] ?? ''
})

// Colors
const riskColor = (level: string | null) =>
  ({ low: 'green', medium: 'amber', high: 'orange', critical: 'red' })[level ?? ''] ?? 'grey'

const rolloutColor = (mode: RolloutMode) =>
  ({ observe: 'blue', warn: 'amber', enforce: 'green' })[mode] ?? 'grey'

const sensitivityColor = (s: Sensitivity) =>
  ({ low: 'green', medium: 'amber', high: 'orange', critical: 'red' })[s] ?? 'grey'

const decisionColor = (d: string) =>
  ({ ALLOW: 'green', DENY: 'red', REDACT: 'orange', WARN: 'amber' })[d] ?? 'grey'

const severityColor = (s: IncidentSeverity) =>
  ({ low: 'green', medium: 'amber', high: 'orange', critical: 'red' })[s] ?? 'grey'

// Table headers
const traceHeaders = [
  { title: 'Gate', key: 'gate', width: '100' },
  { title: 'Decision', key: 'decision', width: '100' },
  { title: 'Tool', key: 'tool_name' },
  { title: 'Role', key: 'role' },
  { title: 'Category', key: 'category', width: '100' },
  { title: 'Time', key: 'timestamp', width: '180' },
]

const incidentHeaders = [
  { title: 'Title', key: 'title' },
  { title: 'Severity', key: 'severity', width: '100' },
  { title: 'Category', key: 'category', width: '100' },
  { title: 'Status', key: 'status', width: '160' },
  { title: 'Traces', key: 'trace_count', width: '80' },
  { title: 'First Seen', key: 'first_seen', width: '180' },
]

const incidentStatuses = ['open', 'acknowledged', 'resolved', 'false_positive']

const doPromote = async (mode: RolloutMode) => {
  try {
    await promote(mode)
    // Reload agent to get updated rollout_mode
    agent.value = await getAgent(agentId.value)
  }
  catch { /* */ }
}

const regenerateConfig = async () => {
  try { await genConfig() } catch { /* */ }
}

const regenerateKit = async () => {
  try { await genKit() } catch { /* */ }
}

const runValidation = async () => {
  try { await runVal() } catch { /* */ }
}

const doDelete = async () => {
  if (!agent.value) return
  try {
    await deleteAgent(agent.value.id)
    showDeleteDialog.value = false
    navigateTo('/agents')
  }
  catch { /* */ }
}

const updateIncidentStatus = async (incidentId: string, status: IncidentStatus) => {
  try { await updateIncident({ incidentId, status }) } catch { /* */ }
}

// Load agent
onMounted(async () => {
  try {
    agent.value = await getAgent(agentId.value)
  }
  catch {
    error.value = true
  }
  finally {
    loading.value = false
  }
})
</script>

<style lang="scss" scoped>
.config-preview {
  max-height: 400px;
  overflow: auto;
  background: rgba(0, 0, 0, 0.2);

  pre {
    white-space: pre-wrap;
    word-break: break-word;
    font-family: 'Fira Code', monospace;
  }
}
</style>
