<template>
  <v-card flat>
    <v-card-title class="text-h6 d-flex align-center justify-space-between">
      <span>Register Tools</span>
      <div class="d-flex ga-2">
        <v-btn size="small" variant="tonal" prepend-icon="mdi-code-json" @click="importDialog = true">
          Import
        </v-btn>
        <v-btn size="small" color="primary" prepend-icon="mdi-plus" @click="openAdd">
          Add Tool
        </v-btn>
      </div>
    </v-card-title>
    <v-card-subtitle>Define the tools your agent can call</v-card-subtitle>

    <v-card-text>
      <!-- Preset banner -->
      <v-alert
        v-if="!tools.length && !isLoading"
        type="info"
        variant="tonal"
        class="mb-4"
        prominent
      >
        <div class="d-flex align-center justify-space-between flex-wrap ga-2">
          <div>
            <p class="text-body-2 font-weight-bold mb-1">Quick start with a preset</p>
            <p class="text-body-2 text-medium-emphasis mb-0">
              Load a ready-made tool set to test with our built-in agents, or add your own tools from scratch.
            </p>
          </div>
          <v-menu>
            <template #activator="{ props: menuProps }">
              <v-btn
                v-bind="menuProps"
                color="primary"
                variant="tonal"
                prepend-icon="mdi-package-down"
                size="small"
              >
                Load preset
              </v-btn>
            </template>
            <v-list density="compact">
              <v-list-item
                v-for="preset in toolPresets"
                :key="preset.name"
                @click="loadToolPreset(preset)"
              >
                <v-list-item-title>{{ preset.name }}</v-list-item-title>
                <v-list-item-subtitle>{{ preset.description }}</v-list-item-subtitle>
              </v-list-item>
            </v-list>
          </v-menu>
        </div>
      </v-alert>

      <div v-if="isLoading" class="text-center py-8">
        <v-progress-circular indeterminate />
      </div>

      <div v-else-if="!tools.length" class="text-center py-8">
        <v-icon icon="mdi-tools" size="48" color="primary" class="mb-3" />
        <p class="text-body-2 text-medium-emphasis">No tools added yet</p>
      </div>

      <v-list v-else lines="two">
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
            <v-btn icon="mdi-pencil" size="x-small" variant="text" @click="openEdit(tool)" />
            <v-btn icon="mdi-delete" size="x-small" variant="text" color="error" @click="confirmDelete(tool)" />
          </template>
        </v-list-item>
      </v-list>
    </v-card-text>

    <!-- Add/Edit dialog -->
    <v-dialog v-model="dialog" max-width="600" persistent>
      <v-card>
        <v-card-title>{{ editingTool ? 'Edit Tool' : 'Add Tool' }}</v-card-title>
        <v-card-text>
          <v-form v-model="dialogValid">
            <v-text-field
              v-model="toolForm.name"
              label="Tool name"
              :rules="[(v: string) => !!v?.trim() || 'Required']"
              variant="outlined"
              class="mb-2"
            />
            <v-textarea
              v-model="toolForm.description"
              label="Description"
              variant="outlined"
              rows="2"
              class="mb-2"
            />
            <v-row>
              <v-col cols="6">
                <v-select
                  v-model="toolForm.sensitivity"
                  :items="sensitivityOptions"
                  label="Sensitivity"
                  variant="outlined"
                />
              </v-col>
              <v-col cols="6">
                <v-select
                  v-model="toolForm.access_type"
                  :items="accessOptions"
                  label="Access type"
                  variant="outlined"
                />
              </v-col>
            </v-row>
            <v-text-field
              v-model="toolForm.category"
              label="Category (optional)"
              variant="outlined"
              class="mb-2"
            />
            <v-row>
              <v-col cols="6">
                <v-checkbox v-model="toolForm.returns_pii" label="Returns PII" density="compact" hide-details />
              </v-col>
              <v-col cols="6">
                <v-checkbox v-model="toolForm.returns_secrets" label="Returns secrets" density="compact" hide-details />
              </v-col>
            </v-row>
          </v-form>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="dialog = false">Cancel</v-btn>
          <v-btn
            color="primary"
            :loading="isCreating || isUpdating"
            :disabled="!dialogValid"
            @click="saveTool"
          >
            {{ editingTool ? 'Update' : 'Add' }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Import dialog -->
    <v-dialog v-model="importDialog" max-width="600">
      <v-card>
        <v-card-title>Import Tools from JSON</v-card-title>
        <v-card-text>
          <v-textarea
            v-model="importJson"
            label="Paste JSON array"
            variant="outlined"
            rows="8"
            placeholder='[{"name": "read_file", "description": "Read a file", "sensitivity": "low"}]'
          />
          <v-alert v-if="importError" type="error" variant="tonal" density="compact" class="mt-2">
            {{ importError }}
          </v-alert>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="importDialog = false">Cancel</v-btn>
          <v-btn color="primary" :loading="importLoading" @click="doImport">Import</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Delete confirm -->
    <v-dialog v-model="deleteDialog" max-width="400">
      <v-card>
        <v-card-title>Delete tool?</v-card-title>
        <v-card-text>
          Are you sure you want to delete <strong>{{ deletingTool?.name }}</strong>?
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="deleteDialog = false">Cancel</v-btn>
          <v-btn color="error" :loading="isDeleting" @click="doDelete">Delete</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { useAgentTools } from '~/composables/useAgentTools'
import type { Sensitivity, ToolCreate, ToolRead } from '~/types/wizard'

// ─── Tool Presets ───
interface ToolPreset {
  name: string
  description: string
  tools: (ToolCreate & { returns_pii: boolean; returns_secrets: boolean })[]
}

const toolPresets: ToolPreset[] = [
  {
    name: 'Order Manager',
    description: '5 tools — matches built-in Python & LangGraph test agents',
    tools: [
      { name: 'getOrders', description: 'List all customer orders with status and amounts.', sensitivity: 'low', access_type: 'read', category: 'orders', returns_pii: false, returns_secrets: false },
      { name: 'getUsers', description: 'List all users. Returns PII (emails, phone numbers). Admin-only.', sensitivity: 'medium', access_type: 'read', category: 'users', returns_pii: true, returns_secrets: false },
      { name: 'searchProducts', description: 'Search products by name or category.', sensitivity: 'low', access_type: 'read', category: 'products', returns_pii: false, returns_secrets: false },
      { name: 'updateOrder', description: 'Update an order status. Requires admin role.', sensitivity: 'high', access_type: 'write', category: 'orders', returns_pii: false, returns_secrets: false },
      { name: 'updateUser', description: 'Update a user profile. Requires admin role.', sensitivity: 'high', access_type: 'write', category: 'users', returns_pii: true, returns_secrets: false },
    ],
  },
  {
    name: 'Customer Support',
    description: '5 tools — knowledge base, orders, refunds',
    tools: [
      { name: 'searchKnowledgeBase', description: 'Search product documentation and FAQ.', sensitivity: 'low', access_type: 'read', category: 'knowledge', returns_pii: false, returns_secrets: false },
      { name: 'getOrderStatus', description: 'Check order status by order ID.', sensitivity: 'low', access_type: 'read', category: 'orders', returns_pii: false, returns_secrets: false },
      { name: 'getCustomerProfile', description: 'Retrieve customer profile with PII.', sensitivity: 'medium', access_type: 'read', category: 'customers', returns_pii: true, returns_secrets: false },
      { name: 'issueRefund', description: 'Issue a refund for an order. Admin action.', sensitivity: 'high', access_type: 'write', category: 'orders', returns_pii: false, returns_secrets: false },
      { name: 'getInternalSecrets', description: 'Access internal API keys and secrets.', sensitivity: 'critical', access_type: 'read', category: 'internal', returns_pii: false, returns_secrets: true },
    ],
  },
]

const presetLoading = ref(false)

const loadToolPreset = async (preset: ToolPreset) => {
  presetLoading.value = true
  try {
    for (const t of preset.tools) {
      await createTool({ ...t })
    }
    await refetch()
  }
  finally {
    presetLoading.value = false
  }
}

const props = defineProps<{
  agentId: string
}>()

const emit = defineEmits<{
  valid: [valid: boolean]
}>()

const { tools, isLoading, isCreating, isUpdating, isDeleting, createTool, updateTool, deleteTool, refetch } =
  useAgentTools(() => props.agentId)

// Emit validity whenever tools change
watch(tools, (t) => emit('valid', t.length > 0), { immediate: true })

const dialog = ref(false)
const dialogValid = ref(false)
const editingTool = ref<ToolRead | null>(null)

const sensitivityOptions = ['low', 'medium', 'high', 'critical']
const accessOptions = ['read', 'write']

const toolForm = reactive<ToolCreate & { returns_pii: boolean; returns_secrets: boolean }>({
  name: '',
  description: '',
  sensitivity: 'low',
  access_type: 'read',
  category: null,
  returns_pii: false,
  returns_secrets: false,
})

const sensitivityColor = (s: Sensitivity) =>
  ({ low: 'green', medium: 'amber', high: 'orange', critical: 'red' })[s] ?? 'grey'

const resetForm = () => {
  toolForm.name = ''
  toolForm.description = ''
  toolForm.sensitivity = 'low'
  toolForm.access_type = 'read'
  toolForm.category = null
  toolForm.returns_pii = false
  toolForm.returns_secrets = false
}

const openAdd = () => {
  editingTool.value = null
  resetForm()
  dialog.value = true
}

const openEdit = (tool: ToolRead) => {
  editingTool.value = tool
  toolForm.name = tool.name
  toolForm.description = tool.description
  toolForm.sensitivity = tool.sensitivity
  toolForm.access_type = tool.access_type
  toolForm.category = tool.category
  toolForm.returns_pii = tool.returns_pii
  toolForm.returns_secrets = tool.returns_secrets
  dialog.value = true
}

const saveTool = async () => {
  try {
    if (editingTool.value) {
      await updateTool({ toolId: editingTool.value.id, body: { ...toolForm } })
    }
    else {
      await createTool({ ...toolForm })
    }
    dialog.value = false
  }
  catch {
    // error handled by vue-query
  }
}

// Delete
const deleteDialog = ref(false)
const deletingTool = ref<ToolRead | null>(null)

const confirmDelete = (tool: ToolRead) => {
  deletingTool.value = tool
  deleteDialog.value = true
}

const doDelete = async () => {
  if (!deletingTool.value) return
  await deleteTool(deletingTool.value.id)
  deleteDialog.value = false
}

// Import
const importDialog = ref(false)
const importJson = ref('')
const importError = ref('')
const importLoading = ref(false)

const doImport = async () => {
  importError.value = ''
  importLoading.value = true
  try {
    const parsed = JSON.parse(importJson.value)
    if (!Array.isArray(parsed)) throw new Error('Expected a JSON array')
    for (const item of parsed) {
      await createTool({
        name: item.name,
        description: item.description ?? '',
        sensitivity: item.sensitivity ?? 'low',
        access_type: item.access_type ?? 'read',
        category: item.category ?? null,
        returns_pii: item.returns_pii ?? false,
        returns_secrets: item.returns_secrets ?? false,
      })
    }
    importDialog.value = false
    importJson.value = ''
    await refetch()
  }
  catch (e: unknown) {
    importError.value = e instanceof Error ? e.message : 'Invalid JSON'
  }
  finally {
    importLoading.value = false
  }
}
</script>
