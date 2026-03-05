<template>
  <v-card variant="outlined" class="mb-4">
    <v-card-text class="d-flex flex-wrap ga-3 align-center">
      <v-text-field
        v-model="local.session_id"
        label="Session ID"
        variant="outlined"
        density="compact"
        clearable
        hide-details
        prepend-inner-icon="mdi-identifier"
        style="max-width: 220px;"
      />
      <v-select
        v-model="local.user_role"
        :items="['customer', 'admin']"
        label="Role"
        variant="outlined"
        density="compact"
        clearable
        hide-details
        style="max-width: 140px;"
      />
      <v-select
        v-model="local.has_blocks"
        :items="blockItems"
        label="Blocks"
        variant="outlined"
        density="compact"
        clearable
        hide-details
        item-title="title"
        item-value="value"
        style="max-width: 160px;"
      />
      <v-text-field
        v-model="local.date_from"
        label="From"
        type="date"
        variant="outlined"
        density="compact"
        clearable
        hide-details
        style="max-width: 160px;"
      />
      <v-text-field
        v-model="local.date_to"
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
import { onBeforeUnmount } from 'vue'
import type { AgentTraceFilters } from '~/types/agentTrace'

const props = defineProps<{
  modelValue: AgentTraceFilters
  hasActive: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [val: AgentTraceFilters]
  clear: []
}>()

const blockItems = [
  { title: 'Has blocks', value: true },
  { title: 'No blocks', value: false },
]

const local = reactive<AgentTraceFilters>({ ...props.modelValue })

let debounceTimer: ReturnType<typeof setTimeout> | null = null

watch(local, (val) => {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    emit('update:modelValue', { ...val })
  }, 400)
}, { deep: true })

watch(() => props.modelValue, (val) => {
  Object.assign(local, val)
}, { deep: true })

onBeforeUnmount(() => {
  if (debounceTimer) clearTimeout(debounceTimer)
})
</script>
