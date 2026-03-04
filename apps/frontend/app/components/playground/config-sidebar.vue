<template>
  <v-card variant="flat" class="config-sidebar">
    <v-card-title class="text-subtitle-1">
      <v-icon start>mdi-cog</v-icon>
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
        class="mb-4"
        @update:model-value="updateField('model', $event)"
      >
        <template #item="{ item, props: itemProps }">
          <v-list-item
            v-bind="itemProps"
            :disabled="item.raw.disabled"
            :subtitle="item.raw.disabled ? 'Add key in Settings' : item.raw.providerLabel"
          />
        </template>
      </v-select>

      <v-slider
        :model-value="config.temperature"
        :disabled="disabled"
        label="Temperature"
        :min="0"
        :max="2"
        :step="0.1"
        thumb-label
        class="mb-4"
        @update:model-value="updateField('temperature', $event)"
      />

      <v-text-field
        :model-value="config.maxTokens"
        :disabled="disabled"
        label="Max tokens"
        placeholder="Default (model limit)"
        type="number"
        variant="outlined"
        density="compact"
        @update:model-value="updateField('maxTokens', $event ? Number($event) : null)"
      />
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { usePolicies } from '~/composables/usePolicies'
import { useModels } from '~/composables/useModels'

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

const policyItems = computed(() =>
  (policies.value ?? []).map((p) => ({
    title: p.name,
    value: p.name,
  })),
)

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

function updateField<K extends keyof Config>(key: K, value: Config[K]) {
  emit('update:config', { ...props.config, [key]: value })
}
</script>

<style lang="scss" scoped>
.config-sidebar {
  padding: 8px 0;
}
</style>
