<template>
  <v-container fluid class="policies-page">
    <div class="d-flex align-center justify-space-between mb-6">
      <div>
        <h1 class="text-h5 mb-1">Policies</h1>
        <p class="text-body-2 text-medium-emphasis">
          Manage firewall policy levels with custom thresholds and scanner nodes
        </p>
      </div>
      <v-btn variant="text" icon="mdi-refresh" :loading="isLoading" @click="refetch" />
    </div>

    <!-- Loading state -->
    <div v-if="isLoading && !policies?.length">
      <v-row>
        <v-col v-for="n in 4" :key="n" cols="12" sm="6" lg="3">
          <v-skeleton-loader type="card" />
        </v-col>
      </v-row>
    </div>

    <template v-else-if="policies?.length">
      <!-- ═══ Section: Built-in Policies ═══ -->
      <div class="section-header mb-3">
        <div class="d-flex align-center ga-2">
          <v-icon icon="mdi-shield-star" size="18" class="text-medium-emphasis" />
          <span class="text-subtitle-2 font-weight-bold text-medium-emphasis text-uppercase" style="letter-spacing: 0.5px">
            Built-in Policies
          </span>
        </div>
        <p class="text-caption text-medium-emphasis mt-1 ml-7">
          System presets ordered by security level — from minimal checks to maximum protection
        </p>
      </div>

      <v-row class="mb-8">
        <v-col
          v-for="policy in presetPolicies"
          :key="policy.id"
          cols="12"
          sm="6"
          lg="3"
        >
          <policies-card
            :policy="policy"
            @edit="openEdit"
          />
        </v-col>
      </v-row>

      <!-- ═══ Section: Custom Policies ═══ -->
      <div class="section-header mb-3">
        <div class="d-flex align-center justify-space-between">
          <div class="d-flex align-center ga-2">
            <v-icon icon="mdi-tune-variant" size="18" class="text-medium-emphasis" />
            <span class="text-subtitle-2 font-weight-bold text-medium-emphasis text-uppercase" style="letter-spacing: 0.5px">
              Custom Policies
            </span>
            <v-chip v-if="customPolicies.length" size="x-small" variant="tonal" class="ml-1">
              {{ customPolicies.length }}
            </v-chip>
          </div>
          <v-btn size="small" color="primary" variant="tonal" prepend-icon="mdi-plus" @click="openCreate">
            New Policy
          </v-btn>
        </div>
      </div>

      <!-- Custom policies table -->
      <v-card v-if="customPolicies.length" variant="flat" class="custom-table-card">
        <v-table density="comfortable" hover>
          <thead>
            <tr>
              <th class="text-left">Name</th>
              <th class="text-center" style="width: 90px">Status</th>
              <th class="text-center" style="width: 90px">Scanners</th>
              <th class="text-center" style="width: 90px">Risk</th>
              <th class="text-center" style="width: 80px">Version</th>
              <th class="text-right" style="width: 60px" />
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in customPolicies" :key="p.id" class="custom-row" @click="openEdit(p)">
              <td>
                <div class="d-flex flex-column py-1">
                  <span class="text-body-2 font-weight-medium">{{ friendlyName(p) }}</span>
                  <span class="text-caption text-medium-emphasis" style="font-family: monospace; font-size: 11px">
                    {{ p.name }}
                  </span>
                </div>
              </td>
              <td class="text-center">
                <v-chip
                  :color="p.is_active ? 'success' : 'grey'"
                  size="x-small"
                  variant="tonal"
                >
                  {{ p.is_active ? 'Active' : 'Inactive' }}
                </v-chip>
              </td>
              <td class="text-center">
                <span class="text-body-2">{{ getScannerCount(p) }}</span>
              </td>
              <td class="text-center">
                <span class="text-body-2">{{ getMaxRisk(p) }}</span>
              </td>
              <td class="text-center">
                <span class="text-caption text-medium-emphasis">v{{ p.version }}</span>
              </td>
              <td class="text-right" @click.stop>
                <v-menu location="bottom end">
                  <template #activator="{ props: menuProps }">
                    <v-btn v-bind="menuProps" icon="mdi-dots-vertical" variant="text" size="x-small" />
                  </template>
                  <v-list density="compact" min-width="140">
                    <v-list-item prepend-icon="mdi-pencil" title="Edit" @click="openEdit(p)" />
                    <v-list-item prepend-icon="mdi-delete" title="Delete" class="text-error" @click="confirmDelete(p)" />
                  </v-list>
                </v-menu>
              </td>
            </tr>
          </tbody>
        </v-table>
      </v-card>

      <!-- Empty custom policies -->
      <v-card v-else variant="flat" class="custom-table-card text-center pa-8">
        <v-icon size="40" color="grey" icon="mdi-shield-plus-outline" class="mb-2" />
        <p class="text-body-2 text-medium-emphasis">
          No custom policies yet. Create one to define your own scanner configuration.
        </p>
      </v-card>
    </template>

    <!-- Fully empty state -->
    <v-card v-else variant="flat" class="text-center pa-8">
      <v-icon size="64" color="grey" icon="mdi-shield-off-outline" />
      <p class="text-h6 mt-4">No policies found</p>
    </v-card>

    <!-- Dialog -->
    <policies-dialog
      v-model="showDialog"
      :policy="editingPolicy"
      :saving="isSaving"
      @save="onSave"
    />

    <!-- Delete confirm -->
    <v-dialog v-model="showDelete" max-width="400">
      <v-card>
        <v-card-title>Delete Policy</v-card-title>
        <v-card-text>
          Deactivate policy <strong>{{ deletingPolicy?.name }}</strong>?
          Built-in policies cannot be deleted.
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="showDelete = false">Cancel</v-btn>
          <v-btn class="btn-action--danger" prepend-icon="mdi-delete" :loading="isDeleting" @click="doDelete">
            Delete
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-snackbar v-model="snackbar" :color="snackColor" timeout="3000">
      {{ snackMsg }}
    </v-snackbar>
  </v-container>
</template>

<script setup lang="ts">
import type { Policy } from '~/types/api'

definePageMeta({ title: 'Policies' })

const {
  policies, isLoading, refetch,
  createPolicy, updatePolicy, deletePolicy,
  isCreating, isUpdating, isDeleting,
} = usePolicies()

const BUILTIN = new Set(['fast', 'balanced', 'strict', 'paranoid'])
const POLICY_ORDER: Record<string, number> = { fast: 0, balanced: 1, strict: 2, paranoid: 3 }

const presetPolicies = computed(() =>
  [...(policies.value ?? [])]
    .filter(p => BUILTIN.has(p.name))
    .sort((a, b) => (POLICY_ORDER[a.name] ?? 99) - (POLICY_ORDER[b.name] ?? 99)),
)

const customPolicies = computed(() =>
  [...(policies.value ?? [])]
    .filter(p => !BUILTIN.has(p.name))
    .sort((a, b) => a.name.localeCompare(b.name)),
)

function friendlyName(p: Policy): string {
  if (p.description && p.description !== 'A test policy' && p.description.length > 0) {
    // Capitalize first letter, truncate long descriptions
    const desc = p.description.charAt(0).toUpperCase() + p.description.slice(1)
    return desc.length > 50 ? desc.slice(0, 47) + '…' : desc
  }
  // Fallback: humanize the cfg- name
  return p.name
}

function getScannerCount(p: Policy): number {
  const config = p.config as { nodes?: string[] } | undefined
  return config?.nodes?.length ?? 0
}

function getMaxRisk(p: Policy): string {
  const config = p.config as { thresholds?: { max_risk?: number } } | undefined
  return config?.thresholds?.max_risk?.toFixed(2) ?? '—'
}

const showDialog = ref(false)
const editingPolicy = ref<Policy | null>(null)
const isSaving = computed(() => isCreating.value || isUpdating.value)

const showDelete = ref(false)
const deletingPolicy = ref<Policy | null>(null)

const snackbar = ref(false)
const snackMsg = ref('')
const snackColor = ref('success')

function flash(msg: string, color = 'success') {
  snackMsg.value = msg
  snackColor.value = color
  snackbar.value = true
}

function openCreate() {
  editingPolicy.value = null
  showDialog.value = true
}

function openEdit(policy: Policy) {
  editingPolicy.value = policy
  showDialog.value = true
}

function confirmDelete(policy: Policy) {
  deletingPolicy.value = policy
  showDelete.value = true
}

async function onSave(data: { name: string; description: string; config: Record<string, unknown>; is_active: boolean }) {
  try {
    if (editingPolicy.value) {
      await updatePolicy({ id: editingPolicy.value.id, body: data })
      flash('Policy updated')
    } else {
      await createPolicy(data)
      flash('Policy created')
    }
    showDialog.value = false
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Save failed'
    flash(String(msg), 'error')
  }
}

async function doDelete() {
  if (!deletingPolicy.value) return
  try {
    await deletePolicy(deletingPolicy.value.id)
    flash('Policy deactivated')
    showDelete.value = false
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Delete failed'
    flash(String(msg), 'error')
  }
}
</script>

<style lang="scss" scoped>
.policies-page {
  .section-header {
    padding-top: 4px;
  }

  .custom-table-card {
    border-radius: 12px !important;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25), 0 0 0 1px rgba(255, 255, 255, 0.06) !important;
    overflow: hidden;
  }

  .custom-row {
    cursor: pointer;
    transition: background 0.15s ease;

    &:hover {
      background: rgba(var(--v-theme-on-surface), 0.04) !important;
    }
  }
}
</style>
