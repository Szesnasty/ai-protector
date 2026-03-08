<template>
  <v-container fluid>
    <div class="d-flex align-center justify-space-between mb-4">
      <div>
        <h1 class="text-h5 mb-1">Policies</h1>
        <p class="text-body-2 text-medium-emphasis">
          Manage firewall policy levels with custom thresholds and scanner nodes
        </p>
      </div>
      <div class="d-flex ga-2">
        <v-btn color="primary" prepend-icon="mdi-plus" @click="openCreate">
          New Policy
        </v-btn>
        <v-btn variant="text" icon="mdi-refresh" :loading="isLoading" @click="refetch" />
      </div>
    </div>

    <!-- Loading state -->
    <v-row v-if="isLoading && !policies?.length">
      <v-col v-for="n in 4" :key="n" cols="12" sm="6" lg="3">
        <v-skeleton-loader type="card" />
      </v-col>
    </v-row>

    <!-- Policy cards -->
    <v-row v-else-if="policies?.length">
      <v-col
        v-for="policy in sortedPolicies"
        :key="policy.id"
        cols="12"
        sm="6"
        lg="3"
      >
        <policies-card
          :policy="policy"
          @edit="openEdit"
          @delete="confirmDelete"
        />
      </v-col>
    </v-row>

    <!-- Empty state -->
    <v-card v-else variant="outlined" class="text-center pa-8">
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

const POLICY_ORDER: Record<string, number> = { fast: 0, balanced: 1, strict: 2, paranoid: 3 }
const sortedPolicies = computed(() =>
  [...(policies.value ?? [])].sort((a, b) =>
    (POLICY_ORDER[a.name] ?? 99) - (POLICY_ORDER[b.name] ?? 99),
  ),
)

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
