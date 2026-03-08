<template>
  <v-dialog
    :model-value="modelValue"
    max-width="700"
    :retain-focus="false"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <v-card>
      <v-card-title>
        <div class="d-flex align-center ga-2">
          {{ isBuiltin ? 'View Policy' : isEdit ? 'Edit Policy' : 'Create Policy' }}
          <v-chip v-if="isBuiltin" size="x-small" variant="tonal" prepend-icon="mdi-lock">
            Read-only
          </v-chip>
        </div>
      </v-card-title>
      <v-card-text>
        <v-text-field
          v-model="form.name"
          label="Name"
          variant="outlined"
          density="compact"
          :disabled="isBuiltin"
          :rules="[v => !!v || 'Required']"
          class="mb-3"
        />
        <v-textarea
          v-model="form.description"
          label="Description"
          variant="outlined"
          density="compact"
          rows="2"
          auto-grow
          :disabled="isBuiltin"
          class="mb-3"
        />
        <v-switch
          v-model="form.is_active"
          label="Active"
          color="primary"
          density="compact"
          hide-details
          :disabled="isBuiltin"
          class="mb-4"
        />

        <policies-config-editor v-model="form.config" :disabled="isBuiltin" />
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="$emit('update:modelValue', false)">
          {{ isBuiltin ? 'Close' : 'Cancel' }}
        </v-btn>
        <v-btn
          v-if="!isBuiltin"
          class="btn-action"
          :loading="saving"
          :disabled="!form.name"
          prepend-icon="mdi-content-save"
          @click="save"
        >
          Save
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import type { Policy } from '~/types/api'

const props = defineProps<{
  modelValue: boolean
  policy: Policy | null
  saving: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [val: boolean]
  save: [data: { name: string; description: string; config: Record<string, unknown>; is_active: boolean }]
}>()

const BUILTIN = new Set(['fast', 'balanced', 'strict', 'paranoid'])
const isEdit = computed(() => !!props.policy)
const isBuiltin = computed(() => !!props.policy && BUILTIN.has(props.policy.name))

const form = ref({
  name: '',
  description: '',
  config: { nodes: [] as string[], thresholds: {} as Record<string, unknown> },
  is_active: true,
})

watch(() => props.modelValue, (open) => {
  if (open && props.policy) {
    form.value = {
      name: props.policy.name,
      description: props.policy.description ?? '',
      config: JSON.parse(JSON.stringify(props.policy.config ?? { nodes: [], thresholds: {} })),
      is_active: props.policy.is_active,
    }
  } else if (open) {
    form.value = {
      name: '',
      description: '',
      config: { nodes: [], thresholds: {} },
      is_active: true,
    }
  }
})

function save() {
  emit('save', { ...form.value })
}
</script>
