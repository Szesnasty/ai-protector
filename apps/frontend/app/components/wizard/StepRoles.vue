<template>
  <v-card flat>
    <v-card-title class="text-h6 d-flex align-center justify-space-between">
      <span>Define Roles</span>
      <v-btn size="small" color="primary" prepend-icon="mdi-plus" @click="openAdd">
        Add Role
      </v-btn>
    </v-card-title>
    <v-card-subtitle>Define roles and assign tool permissions</v-card-subtitle>

    <v-card-text>
      <!-- Preset banner -->
      <v-alert
        v-if="!roles.length && !isLoading && tools.length"
        type="info"
        variant="tonal"
        class="mb-4"
        prominent
      >
        <div class="d-flex align-center justify-space-between flex-wrap ga-2">
          <div>
            <p class="text-body-2 font-weight-bold mb-1">Quick start with a preset</p>
            <p class="text-body-2 text-medium-emphasis mb-0">
              Load matching roles for your tools, or create custom roles from scratch.
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
                :loading="presetLoading"
              >
                Load preset
              </v-btn>
            </template>
            <v-list density="compact">
              <v-list-item
                v-for="preset in rolePresets"
                :key="preset.name"
                @click="loadRolePreset(preset)"
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

      <div v-else-if="!roles.length" class="text-center py-8">
        <v-icon icon="mdi-account-key" size="48" color="primary" class="mb-3" />
        <p class="text-body-2 text-medium-emphasis">No roles defined yet</p>
      </div>

      <template v-else>
        <!-- Roles list -->
        <v-list lines="two" class="mb-4">
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
              <v-chip size="x-small" class="mr-2">
                {{ role.permissions.length }} tools
              </v-chip>
              <v-btn icon="mdi-pencil" size="x-small" variant="text" @click="openEdit(role)" />
              <v-btn icon="mdi-delete" size="x-small" variant="text" color="error" @click="confirmDelete(role)" />
            </template>
          </v-list-item>
        </v-list>

        <!-- Permission matrix -->
        <v-divider class="mb-4" />
        <p class="text-subtitle-2 mb-3">Permission Matrix</p>

        <div v-if="matrix" class="matrix-wrapper">
          <v-table density="compact" class="permission-matrix">
            <thead>
              <tr>
                <th class="text-left">Role / Tool</th>
                <th v-for="tool in matrix.tools" :key="tool" class="text-center">
                  {{ tool }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="role in matrix.roles" :key="role">
                <td class="font-weight-medium">{{ role }}</td>
                <td v-for="tool in matrix.tools" :key="tool" class="text-center">
                  <v-icon
                    v-if="matrix.matrix[role]?.[tool] === 'confirm'"
                    icon="mdi-shield-check"
                    color="amber"
                    size="18"
                  />
                  <v-icon
                    v-else
                    :icon="matrix.matrix[role]?.[tool] === 'allow' ? 'mdi-check-circle' : 'mdi-close-circle'"
                    :color="matrix.matrix[role]?.[tool] === 'allow' ? 'green' : 'red'"
                    size="18"
                  />
                </td>
              </tr>
            </tbody>
          </v-table>
        </div>
      </template>
    </v-card-text>

    <!-- Add/Edit dialog -->
    <v-dialog v-model="dialog" max-width="500" persistent>
      <v-card>
        <v-card-title>{{ editingRole ? 'Edit Role' : 'Add Role' }}</v-card-title>
        <v-card-text>
          <v-form v-model="dialogValid">
            <v-text-field
              v-model="roleForm.name"
              label="Role name"
              :rules="[(v: string) => !!v?.trim() || 'Required']"
              variant="outlined"
              class="mb-2"
            />
            <v-textarea
              v-model="roleForm.description"
              label="Description"
              variant="outlined"
              rows="2"
              class="mb-2"
            />
            <v-select
              v-model="roleForm.inherits_from"
              :items="inheritOptions"
              label="Inherits from (optional)"
              variant="outlined"
              clearable
            />

            <template v-if="tools.length">
              <v-divider class="my-3" />
              <p class="text-subtitle-2 mb-2">Allowed tools</p>
              <v-checkbox
                v-for="tool in tools"
                :key="tool.id"
                v-model="selectedToolIds"
                :label="tool.name"
                :value="tool.id"
                density="compact"
                hide-details
              />
            </template>
          </v-form>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="dialog = false">Cancel</v-btn>
          <v-btn
            color="primary"
            :loading="isCreating || isUpdating"
            :disabled="!dialogValid"
            @click="saveRole"
          >
            {{ editingRole ? 'Update' : 'Add' }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Delete confirm -->
    <v-dialog v-model="deleteDialog" max-width="400">
      <v-card>
        <v-card-title>Delete role?</v-card-title>
        <v-card-text>
          Are you sure you want to delete <strong>{{ deletingRole?.name }}</strong>?
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
import { computed, ref, watch } from 'vue'
import { useAgentRoles } from '~/composables/useAgentRoles'
import { useAgentTools } from '~/composables/useAgentTools'
import type { RoleCreate, RoleRead } from '~/types/wizard'

// ─── Role Presets ───
interface RolePresetDef {
  name: string
  description: string
  roles: { name: string; description: string; inherits_from_name?: string; tool_names: string[] }[]
}

const rolePresets: RolePresetDef[] = [
  {
    name: 'E-commerce (user + admin)',
    description: 'user — read-only; admin — full access (inherits user)',
    roles: [
      { name: 'user', description: 'Standard user — read-only access to orders and products', tool_names: ['getOrders', 'searchProducts'] },
      { name: 'admin', description: 'Administrator — full access including PII and write operations', inherits_from_name: 'user', tool_names: ['getUsers', 'updateOrder', 'updateUser'] },
    ],
  },
]

const presetLoading = ref(false)

const loadRolePreset = async (preset: RolePresetDef) => {
  presetLoading.value = true
  try {
    const createdRoles = new Map<string, string>() // name → id

    for (const r of preset.roles) {
      const inheritsId = r.inherits_from_name ? (createdRoles.get(r.inherits_from_name) ?? null) : null
      const created = await createRole({ name: r.name, description: r.description, inherits_from: inheritsId })
      createdRoles.set(r.name, created.id)

      // Set permissions for tools that exist, using correct scopes based on access_type
      const matchedTools = r.tool_names
        .map(n => tools.value.find(t => t.name === n))
        .filter((t): t is NonNullable<typeof t> => !!t)
      if (matchedTools.length) {
        await setPermissions({
          roleId: created.id,
          body: {
            permissions: matchedTools.map(t => ({
              tool_id: t.id,
              scopes: t.access_type === 'write' ? ['read', 'write'] : ['read'],
            })),
          },
        })
      }
    }
    await refetchMatrix()
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

const { roles, matrix, isLoading, isCreating, isUpdating, isDeleting, createRole, updateRole, deleteRole, setPermissions, refetchMatrix } =
  useAgentRoles(() => props.agentId)
const { tools } = useAgentTools(() => props.agentId)

watch(roles, (r) => emit('valid', r.length > 0), { immediate: true })
watch(tools, () => refetchMatrix(), { deep: true })

const dialog = ref(false)
const dialogValid = ref(false)
const editingRole = ref<RoleRead | null>(null)
const selectedToolIds = ref<string[]>([])

const roleForm = ref<RoleCreate>({
  name: '',
  description: '',
  inherits_from: null,
})

const inheritOptions = computed(() =>
  roles.value
    .filter(r => r.id !== editingRole.value?.id)
    .map(r => ({ title: r.name, value: r.id })),
)

const openAdd = () => {
  editingRole.value = null
  roleForm.value = { name: '', description: '', inherits_from: null }
  selectedToolIds.value = []
  dialog.value = true
}

const openEdit = (role: RoleRead) => {
  editingRole.value = role
  roleForm.value = { name: role.name, description: role.description, inherits_from: role.inherits_from }
  selectedToolIds.value = role.permissions.map(p => p.tool_id)
  dialog.value = true
}

const saveRole = async () => {
  try {
    let roleId: string
    if (editingRole.value) {
      const updated = await updateRole({ roleId: editingRole.value.id, body: { ...roleForm.value } })
      roleId = updated.id
    }
    else {
      const created = await createRole({ ...roleForm.value })
      roleId = created.id
    }

    // Set permissions for selected tools, using correct scopes based on access_type
    const toolMap = new Map(tools.value.map(t => [t.id, t]))
    await setPermissions({
      roleId,
      body: {
        permissions: selectedToolIds.value.map(tid => {
          const tool = toolMap.get(tid)
          return { tool_id: tid, scopes: tool?.access_type === 'write' ? ['read', 'write'] : ['read'] }
        }),
      },
    })

    await refetchMatrix()
    dialog.value = false
  }
  catch {
    // error handled by vue-query
  }
}

// Delete
const deleteDialog = ref(false)
const deletingRole = ref<RoleRead | null>(null)

const confirmDelete = (role: RoleRead) => {
  deletingRole.value = role
  deleteDialog.value = true
}

const doDelete = async () => {
  if (!deletingRole.value) return
  await deleteRole(deletingRole.value.id)
  await refetchMatrix()
  deleteDialog.value = false
}
</script>

<style lang="scss" scoped>
.matrix-wrapper {
  overflow-x: auto;
}

.permission-matrix {
  th, td {
    white-space: nowrap;
  }
}
</style>
