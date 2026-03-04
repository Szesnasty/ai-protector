<template>
  <v-card variant="flat" class="agent-config">
    <v-card-title class="text-subtitle-1">
      <v-icon start>mdi-cog</v-icon>
      Agent Config
    </v-card-title>

    <v-card-text>
      <v-select
        :model-value="role"
        :items="roleItems"
        :disabled="disabled"
        label="User Role"
        variant="outlined"
        density="compact"
        class="mb-4"
        @update:model-value="$emit('update:role', $event)"
      />

      <v-select
        :model-value="model"
        :items="modelItems"
        :loading="isModelsLoading"
        :disabled="disabled"
        label="Model"
        variant="outlined"
        density="compact"
        class="mb-4"
        @update:model-value="$emit('update:model', $event)"
      >
        <template #item="{ item, props: itemProps }">
          <v-list-item
            v-bind="itemProps"
            :disabled="item.raw.disabled"
            :subtitle="item.raw.disabled ? 'Add key in Settings' : item.raw.providerLabel"
          />
        </template>
      </v-select>

      <v-select
        :model-value="policy"
        :items="policyItems"
        :loading="isPoliciesLoading"
        :disabled="disabled"
        label="Policy"
        variant="outlined"
        density="compact"
        clearable
        class="mb-4"
        @update:model-value="$emit('update:policy', $event)"
      />

      <v-btn
        block
        variant="outlined"
        color="secondary"
        :disabled="disabled"
        prepend-icon="mdi-refresh"
        @click="$emit('new-conversation')"
      >
        New Conversation
      </v-btn>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { usePolicies } from '~/composables/usePolicies'
import { useModels } from '~/composables/useModels'

defineProps<{
  role: 'customer' | 'admin'
  policy: string | null
  model: string
  disabled?: boolean
}>()

defineEmits<{
  'update:role': [value: 'customer' | 'admin']
  'update:policy': [value: string | null]
  'update:model': [value: string]
  'new-conversation': []
}>()

const { policies, isLoading: isPoliciesLoading } = usePolicies()
const { groupedModels, isLoading: isModelsLoading } = useModels()

const roleItems = [
  { title: 'Customer', value: 'customer' },
  { title: 'Admin', value: 'admin' },
]

const PROVIDER_LABELS: Record<string, string> = {
  openai: 'OpenAI',
  anthropic: 'Anthropic',
  google: 'Google AI',
  mistral: 'Mistral',
  ollama: 'Ollama (local)',
}

const modelItems = computed(() =>
  (groupedModels.value ?? []).map((m) => ({
    title: m.name,
    value: m.id,
    disabled: !m.available,
    providerLabel: PROVIDER_LABELS[m.provider] ?? m.provider,
  })),
)

const policyItems = computed(() =>
  (policies.value ?? []).map((p) => ({
    title: p.name,
    value: p.name,
  })),
)
</script>

<style lang="scss" scoped>
.agent-config {
  padding: 8px 0;
}
</style>
