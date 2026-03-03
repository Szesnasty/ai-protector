<template>
  <v-dialog v-model="dialog" max-width="640" :retain-focus="false">
    <v-card>
      <v-card-title>{{ isEdit ? 'Edit Rule' : 'Add Rule' }}</v-card-title>
      <v-card-text>
        <v-select
          v-model="form.category"
          :items="categoryItems"
          item-title="label"
          item-value="category"
          label="Category"
          clearable
          variant="outlined"
          density="compact"
          class="mb-2"
          @update:model-value="onCategoryChange"
        >
          <template #item="{ item, props: itemProps }">
            <v-list-item v-bind="itemProps">
              <template #subtitle>
                {{ item.raw?.description ?? '' }}
              </template>
            </v-list-item>
          </template>
        </v-select>

        <v-textarea
          v-model="form.phrase"
          label="Phrase / Pattern"
          variant="outlined"
          density="compact"
          rows="2"
          auto-grow
          class="mb-2"
        />

        <v-switch
          v-model="form.is_regex"
          label="Is Regex"
          color="primary"
          density="compact"
          hide-details
          class="mb-3"
        />

        <div class="d-flex ga-3 mb-2">
          <v-select
            v-model="form.action"
            :items="actionItems"
            label="Action"
            variant="outlined"
            density="compact"
            style="flex: 1"
          />
          <v-select
            v-model="form.severity"
            :items="severityItems"
            label="Severity"
            variant="outlined"
            density="compact"
            style="flex: 1"
          />
        </div>

        <v-text-field
          v-model="form.description"
          label="Description"
          variant="outlined"
          density="compact"
          counter="256"
        />

        <v-alert v-if="categoryDescription || categoryExamples" type="info" variant="tonal" density="compact" class="mt-2">
          <div v-if="categoryDescription" class="font-weight-medium mb-1">{{ categoryDescription }}</div>
          <div v-if="categoryExamples" class="text-caption text-medium-emphasis">Examples: {{ categoryExamples }}</div>
        </v-alert>
      </v-card-text>

      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="close">Cancel</v-btn>
        <v-btn color="primary" variant="flat" :disabled="!isValid" :loading="saving" @click="save">
          {{ isEdit ? 'Update' : 'Create' }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import type { Rule, RuleCreate, RuleUpdate } from '~/types/api'

const props = defineProps<{
  modelValue: boolean
  rule?: Rule | null
  saving?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'save': [data: RuleCreate | RuleUpdate]
}>()

const { presets, presetMap } = useRulePresets()

const dialog = computed({
  get: () => props.modelValue,
  set: (v: boolean) => emit('update:modelValue', v),
})

const isEdit = computed(() => !!props.rule)

const form = reactive({
  phrase: '',
  category: 'general' as string | null,
  is_regex: false,
  action: 'block',
  severity: 'medium',
  description: '',
})

const categoryDescription = ref('')
const categoryExamples = ref('')

const categoryItems = computed(() =>
  presets.map(p => ({ label: p.label, category: p.category, description: p.description })),
)

const actionItems = [
  { title: 'Block', value: 'block' },
  { title: 'Flag', value: 'flag' },
  { title: 'Score Boost', value: 'score_boost' },
]

const severityItems = [
  { title: 'Low', value: 'low' },
  { title: 'Medium', value: 'medium' },
  { title: 'High', value: 'high' },
  { title: 'Critical', value: 'critical' },
]

const isValid = computed(() => !!form.phrase && form.phrase.length > 0 && form.phrase.length <= 1000)

watch(() => props.rule, (rule) => {
  if (rule) {
    form.phrase = rule.phrase
    form.category = rule.category
    form.is_regex = rule.is_regex
    form.action = rule.action
    form.severity = rule.severity
    form.description = rule.description
    categoryDescription.value = ''
    categoryExamples.value = ''
  }
}, { immediate: true })

watch(() => props.modelValue, (open) => {
  if (open && !props.rule) {
    form.phrase = ''
    form.category = 'general'
    form.is_regex = false
    form.action = 'block'
    form.severity = 'medium'
    form.description = ''
    categoryDescription.value = ''
    categoryExamples.value = ''
  }
})

function onCategoryChange(category: string | null) {
  if (!category) {
    categoryDescription.value = ''
    categoryExamples.value = ''
    return
  }
  const preset = presetMap[category]
  if (!preset) {
    categoryDescription.value = ''
    categoryExamples.value = ''
    return
  }

  // Auto-fill only empty fields
  if (!form.description) form.description = preset.description
  if (form.action === 'block' && !isEdit.value) form.action = preset.action
  if (form.severity === 'medium' && !isEdit.value) form.severity = preset.severity

  categoryDescription.value = preset.description
  categoryExamples.value = preset.examples.join(', ')
}

function close() {
  dialog.value = false
}

function save() {
  emit('save', {
    phrase: form.phrase,
    category: form.category || 'general',
    is_regex: form.is_regex,
    action: form.action as RuleCreate['action'],
    severity: form.severity as RuleCreate['severity'],
    description: form.description,
  })
}
</script>
