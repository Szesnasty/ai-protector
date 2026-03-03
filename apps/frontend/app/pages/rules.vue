<template>
  <v-container fluid>
    <h1 class="text-h5 mb-1">Security Rules</h1>
    <p class="text-body-2 text-medium-emphasis mb-4">
      Custom pattern rules (regex / plain text). Applied to all scanning policies.
      ML scanners (LLM Guard, Presidio) run independently.
    </p>

    <!-- Toolbar -->
    <div class="d-flex ga-2 mb-4">
      <v-btn color="primary" prepend-icon="mdi-plus" @click="openCreate">
        Add Rule
      </v-btn>
      <v-btn variant="outlined" prepend-icon="mdi-import" @click="showImport = true">
        Import
      </v-btn>
      <v-btn variant="outlined" prepend-icon="mdi-export" :loading="exporting" @click="doExport">
        Export
      </v-btn>
      <v-spacer />
      <v-btn variant="text" icon="mdi-refresh" :loading="loadingRules" @click="loadRules" />
    </div>

    <!-- Rules table -->
    <rules-table
      :rules="rules"
      :loading="loadingRules"
      @edit="openEdit"
      @delete="confirmDelete"
      @test="openTest"
    />

    <!-- Create/Edit dialog -->
    <rules-dialog
      v-model="showDialog"
      :rule="editingRule"
      :saving="saving"
      @save="onSave"
    />

    <!-- Bulk import dialog -->
    <rules-bulk-import
      v-model="showImport"
      :importing="importing"
      @import="onBulkImport"
    />

    <!-- Test dialog -->
    <rules-test-dialog
      v-model="showTest"
      :focus-rule="testingRule"
      :testing="testRunning"
      :results="testResults"
      @test="onTestRun"
    />

    <!-- Delete confirm -->
    <v-dialog v-model="showDeleteConfirm" max-width="400">
      <v-card>
        <v-card-title>Delete Rule</v-card-title>
        <v-card-text>
          Are you sure you want to delete rule
          <strong class="text-mono">"{{ deletingRule?.phrase }}"</strong>?
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="showDeleteConfirm = false">Cancel</v-btn>
          <v-btn color="error" variant="flat" :loading="deleting" @click="onDelete">Delete</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Snackbar -->
    <v-snackbar v-model="snackbar" :color="snackbarColor" timeout="3000">
      {{ snackbarText }}
    </v-snackbar>
  </v-container>
</template>

<script setup lang="ts">
import type { Rule, RuleCreate, RuleTestResult, RuleUpdate } from '~/types/api'

// ── Rules API ─────────────────────────────────────────────
const { listRules, createRule, updateRule, deleteRule, bulkImport, exportRules, testRules } =
  useRulesApi()

const rules = ref<Rule[]>([])
const loadingRules = ref(false)

async function loadRules() {
  loadingRules.value = true
  try {
    rules.value = await listRules()
  }
  catch {
    showSnackbar('Failed to load rules', 'error')
  }
  finally {
    loadingRules.value = false
  }
}

onMounted(() => loadRules())

// ── Create / Edit ─────────────────────────────────────────
const showDialog = ref(false)
const editingRule = ref<Rule | null>(null)
const saving = ref(false)

function openCreate() {
  editingRule.value = null
  showDialog.value = true
}

function openEdit(rule: Rule) {
  editingRule.value = rule
  showDialog.value = true
}

async function onSave(data: RuleCreate | RuleUpdate) {
  saving.value = true
  try {
    if (editingRule.value) {
      await updateRule(editingRule.value.id, data as RuleUpdate)
      showSnackbar('Rule updated')
    }
    else {
      await createRule(data as RuleCreate)
      showSnackbar('Rule created')
    }
    showDialog.value = false
    await loadRules()
  }
  catch {
    showSnackbar('Failed to save rule', 'error')
  }
  finally {
    saving.value = false
  }
}

// ── Delete ────────────────────────────────────────────────
const showDeleteConfirm = ref(false)
const deletingRule = ref<Rule | null>(null)
const deleting = ref(false)

function confirmDelete(rule: Rule) {
  deletingRule.value = rule
  showDeleteConfirm.value = true
}

async function onDelete() {
  if (!deletingRule.value) return
  deleting.value = true
  try {
    await deleteRule(deletingRule.value.id)
    showSnackbar('Rule deleted')
    showDeleteConfirm.value = false
    await loadRules()
  }
  catch {
    showSnackbar('Failed to delete rule', 'error')
  }
  finally {
    deleting.value = false
  }
}

// ── Bulk Import ───────────────────────────────────────────
const showImport = ref(false)
const importing = ref(false)

async function onBulkImport(importRules: RuleCreate[]) {
  importing.value = true
  try {
    const result = await bulkImport(importRules)
    showSnackbar(`Imported ${result.created} rules (${result.skipped} skipped)`)
    showImport.value = false
    await loadRules()
  }
  catch {
    showSnackbar('Import failed', 'error')
  }
  finally {
    importing.value = false
  }
}

// ── Export ─────────────────────────────────────────────────
const exporting = ref(false)

async function doExport() {
  exporting.value = true
  try {
    const data = await exportRules()
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'security-rules.json'
    a.click()
    URL.revokeObjectURL(url)
    showSnackbar('Export downloaded')
  }
  catch {
    showSnackbar('Export failed', 'error')
  }
  finally {
    exporting.value = false
  }
}

// ── Test ──────────────────────────────────────────────────
const showTest = ref(false)
const testingRule = ref<Rule | null>(null)
const testRunning = ref(false)
const testResults = ref<RuleTestResult[] | null>(null)

function openTest(rule: Rule) {
  testingRule.value = rule
  testResults.value = null
  showTest.value = true
}

async function onTestRun(text: string) {
  testRunning.value = true
  try {
    testResults.value = await testRules(text)
  }
  catch {
    showSnackbar('Test failed', 'error')
  }
  finally {
    testRunning.value = false
  }
}

// ── Snackbar ──────────────────────────────────────────────
const snackbar = ref(false)
const snackbarText = ref('')
const snackbarColor = ref('success')

function showSnackbar(text: string, color = 'success') {
  snackbarText.value = text
  snackbarColor.value = color
  snackbar.value = true
}
</script>

<style scoped>
.text-mono {
  font-family: 'Roboto Mono', monospace;
}
</style>
