<template>
  <v-card variant="flat" class="agent-config">
    <v-card-title class="text-subtitle-1">
      <v-icon start size="20">mdi-cog</v-icon>
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
        hide-details
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
        hide-details
        item-title="title"
        item-value="value"
        class="mb-4"
        @update:model-value="$emit('update:model', $event)"
      />

      <v-select
        :model-value="policy"
        :items="policyItems"
        :loading="isPoliciesLoading"
        :disabled="disabled"
        label="Policy"
        variant="outlined"
        density="compact"
        hide-details
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
import { useAppMode } from '~/composables/useAppMode'
import { sortedPolicyItems } from '~/utils/policyOrder'

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
const { isDemo: _isDemo } = useAppMode()

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
  mock: 'Demo',
}

/** Only show models that are available (Ollama always + providers with key). */
const modelItems = computed(() =>
  (groupedModels.value ?? [])
    .filter((m) => m.available)
    .map((m) => ({
      title: `${m.name}  ·  ${PROVIDER_LABELS[m.provider] ?? m.provider}`,
      value: m.id,
    })),
)

const policyItems = computed(() => sortedPolicyItems(policies.value ?? []))
</script>

<style lang="scss" scoped>
.agent-config {
  padding: 8px 0;
  border-radius: 12px !important;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25), 0 0 0 1px rgba(255, 255, 255, 0.12) !important;
  background: rgb(var(--v-theme-surface));
}
</style>
