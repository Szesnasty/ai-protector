<template>
  <v-card variant="outlined" class="mb-4">
    <v-card-text class="d-flex flex-wrap ga-3 align-center">
      <v-select
        v-model="local.decision"
        :items="decisionItems"
        label="Decision"
        variant="outlined"
        density="compact"
        clearable
        hide-details
        style="max-width: 160px;"
      />
      <v-select
        v-model="local.policy_id"
        :items="policyItems"
        label="Policy"
        variant="outlined"
        density="compact"
        clearable
        hide-details
        style="max-width: 180px;"
      />
      <v-text-field
        v-model="local.intent"
        label="Intent"
        variant="outlined"
        density="compact"
        clearable
        hide-details
        style="max-width: 140px;"
      />
      <v-text-field
        v-model="local.search"
        label="Search prompt"
        variant="outlined"
        density="compact"
        clearable
        hide-details
        prepend-inner-icon="mdi-magnify"
        style="max-width: 220px;"
      />
      <v-text-field
        v-model="local.from"
        label="From"
        type="date"
        variant="outlined"
        density="compact"
        clearable
        hide-details
        style="max-width: 160px;"
      />
      <v-text-field
        v-model="local.to"
        label="To"
        type="date"
        variant="outlined"
        density="compact"
        clearable
        hide-details
        style="max-width: 160px;"
      />
      <v-btn
        v-if="hasActive"
        variant="text"
        size="small"
        prepend-icon="mdi-filter-off"
        @click="$emit('clear')"
      >
        Clear
      </v-btn>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import type { RequestFilters } from '~/types/api'
import type { Policy } from '~/types/api'

const props = defineProps<{
  modelValue: RequestFilters
  policies: Policy[] | undefined
  hasActive: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [val: RequestFilters]
  clear: []
}>()

const decisionItems = [
  { title: 'ALLOW', value: 'ALLOW' },
  { title: 'MODIFY', value: 'MODIFY' },
  { title: 'BLOCK', value: 'BLOCK' },
]

const policyItems = computed(() =>
  (props.policies ?? []).map(p => ({ title: p.name, value: p.id })),
)

const local = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

// Debounced watchers for text fields
let searchTimeout: ReturnType<typeof setTimeout>
watch(() => local.value.search, () => {
  clearTimeout(searchTimeout)
  searchTimeout = setTimeout(() => emit('update:modelValue', { ...local.value }), 300)
})

let intentTimeout: ReturnType<typeof setTimeout>
watch(() => local.value.intent, () => {
  clearTimeout(intentTimeout)
  intentTimeout = setTimeout(() => emit('update:modelValue', { ...local.value }), 300)
})
</script>
