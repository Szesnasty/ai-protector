<template>
  <v-card variant="flat" class="config-sidebar">
    <v-card-title class="text-subtitle-1">
      <v-icon class="main-icon" start>mdi-cog</v-icon>
      Configuration
    </v-card-title>

    <v-card-text>
      <v-select
        :model-value="config.policy"
        :items="policyItems"
        :loading="isLoading"
        :disabled="disabled"
        label="Policy level"
        variant="outlined"
        density="compact"
        hide-details
        class="mb-4"
        @update:model-value="updateField('policy', $event)"
      />

      <v-select
        :model-value="config.model"
        :items="modelItems"
        :loading="modelsLoading"
        :disabled="disabled"
        label="Model"
        variant="outlined"
        density="compact"
        hide-details
        item-title="title"
        item-value="value"
        class="mb-4"
        @update:model-value="updateField('model', $event)"
      />

      <p v-if="isDemo" class="text-caption text-medium-emphasis mt-n2 mb-4">
        <v-icon size="x-small">mdi-key</v-icon>
        Paste an API key in <router-link to="/settings">Settings</router-link> to use real models.
      </p>

      <v-slider
        :model-value="config.temperature"
        :disabled="disabled"
        label="Temperature"
        :min="0"
        :max="2"
        :step="0.1"
        thumb-label
        hide-details
        class="mb-4"
        @update:model-value="updateField('temperature', $event)"
      />

      <v-text-field
        :model-value="config.maxTokens"
        :disabled="disabled"
        label="Max tokens"
        placeholder="Default (model limit)"
        type="number"
        min="1"
        variant="outlined"
        density="compact"
        hide-details
        @update:model-value="updateField('maxTokens', $event ? Math.max(1, Number($event)) : null)"
      />
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { usePolicies } from '~/composables/usePolicies'
import { useModels } from '~/composables/useModels'
import { useAppMode } from '~/composables/useAppMode'
import { sortedPolicyItems } from '~/utils/policyOrder'

interface Config {
  policy: string
  model: string
  temperature: number
  maxTokens: number | null
}

const props = defineProps<{
  config: Config
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:config': [config: Config]
}>()

const { policies, isLoading } = usePolicies()
const { groupedModels, isLoading: modelsLoading } = useModels()
const { isDemo } = useAppMode()

const policyItems = computed(() => sortedPolicyItems(policies.value ?? []))

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

function updateField<K extends keyof Config>(key: K, value: Config[K]) {
  emit('update:config', { ...props.config, [key]: value })
}
</script>

<style lang="scss" scoped>
.config-sidebar {
  padding: 8px 0;
  border-radius: 12px !important;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25), 0 0 0 1px rgba(255, 255, 255, 0.12) !important;
  background: rgb(var(--v-theme-surface));

  .main-icon {
    font-size: 24px;
  }
}
</style>
