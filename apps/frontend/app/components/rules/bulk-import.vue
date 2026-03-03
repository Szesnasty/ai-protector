<template>
  <v-dialog v-model="dialog" max-width="700" persistent>
    <v-card>
      <v-card-title>Import Rules</v-card-title>
      <v-card-text>
        <v-textarea
          v-model="jsonText"
          label="Paste JSON array of rules"
          variant="outlined"
          rows="8"
          placeholder='[{"phrase": "...", "category": "general", "action": "block", "severity": "medium"}]'
          class="mb-2"
        />

        <v-file-input
          label="Or drop a .json file"
          accept=".json"
          variant="outlined"
          density="compact"
          prepend-icon="mdi-file-upload"
          class="mb-3"
          @update:model-value="onFileSelect"
        />

        <v-alert v-if="parseError" type="error" variant="tonal" density="compact" class="mb-2">
          {{ parseError }}
        </v-alert>

        <v-alert v-if="parsed.length > 0" type="info" variant="tonal" density="compact" class="mb-2">
          {{ parsed.length }} rule(s) ready to import
        </v-alert>

        <!-- Preview table -->
        <v-data-table
          v-if="parsed.length > 0"
          :headers="previewHeaders"
          :items="parsed"
          density="compact"
          items-per-page="10"
          class="elevation-1 rounded"
        />
      </v-card-text>

      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="close">Cancel</v-btn>
        <v-btn variant="text" color="secondary" :disabled="!jsonText" @click="preview">
          Preview
        </v-btn>
        <v-btn color="primary" variant="flat" :disabled="parsed.length === 0" :loading="importing" @click="doImport">
          Import {{ parsed.length }} rules
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import type { RuleCreate } from '~/types/api'

const props = defineProps<{
  modelValue: boolean
  importing?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'import': [rules: RuleCreate[]]
}>()

const dialog = computed({
  get: () => props.modelValue,
  set: v => emit('update:modelValue', v),
})

const jsonText = ref('')
const parseError = ref('')
const parsed = ref<RuleCreate[]>([])

const previewHeaders = [
  { title: 'Phrase', key: 'phrase', width: '40%' },
  { title: 'Category', key: 'category', width: '20%' },
  { title: 'Action', key: 'action', width: '15%' },
  { title: 'Severity', key: 'severity', width: '15%' },
]

function onFileSelect(files: File[] | null) {
  if (!files || files.length === 0) return
  const file = files[0]
  const reader = new FileReader()
  reader.onload = (e) => {
    jsonText.value = e.target?.result as string ?? ''
    preview()
  }
  reader.readAsText(file)
}

function preview() {
  parseError.value = ''
  parsed.value = []
  try {
    const data = JSON.parse(jsonText.value)
    if (!Array.isArray(data)) {
      parseError.value = 'JSON must be an array of rule objects'
      return
    }
    // Basic validation
    for (const item of data) {
      if (!item.phrase || typeof item.phrase !== 'string') {
        parseError.value = 'Each rule must have a "phrase" string'
        return
      }
    }
    parsed.value = data as RuleCreate[]
  }
  catch {
    parseError.value = 'Invalid JSON format'
  }
}

function close() {
  jsonText.value = ''
  parseError.value = ''
  parsed.value = []
  dialog.value = false
}

function doImport() {
  emit('import', parsed.value)
}
</script>
