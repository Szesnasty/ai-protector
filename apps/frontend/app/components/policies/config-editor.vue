<template>
  <v-card variant="outlined" class="mb-4">
    <v-card-title class="text-subtitle-1">Scanner Nodes</v-card-title>
    <v-card-text>
      <div class="d-flex flex-wrap ga-2">
        <v-chip
          v-for="node in AVAILABLE_NODES"
          :key="node.id"
          :color="isEnabled(node.id) ? 'primary' : undefined"
          :variant="isEnabled(node.id) ? 'flat' : 'outlined'"
          :prepend-icon="node.icon"
          @click="toggleNode(node.id)"
        >
          {{ node.label }}
        </v-chip>
      </div>
    </v-card-text>

    <v-divider />

    <v-card-title class="text-subtitle-1">Risk Thresholds</v-card-title>
    <v-card-text>
      <div v-for="slider in THRESHOLD_SLIDERS" :key="slider.key" class="mb-2">
        <div class="d-flex justify-space-between text-body-2 mb-1">
          <span>{{ slider.label }}</span>
          <span class="font-weight-bold">{{ getThreshold(slider.key).toFixed(2) }}</span>
        </div>
        <v-slider
          :model-value="getThreshold(slider.key)"
          :min="0"
          :max="1"
          :step="0.05"
          :color="sliderColor(getThreshold(slider.key))"
          hide-details
          density="compact"
          @update:model-value="setThreshold(slider.key, $event as number)"
        />
      </div>
    </v-card-text>

    <v-divider />

    <v-card-title class="text-subtitle-1">Risk Weights</v-card-title>
    <v-card-text>
      <div v-for="slider in WEIGHT_SLIDERS" :key="slider.key" class="mb-2">
        <div class="d-flex justify-space-between text-body-2 mb-1">
          <span>{{ slider.label }}</span>
          <span class="font-weight-bold">{{ getThreshold(slider.key).toFixed(2) }}</span>
        </div>
        <v-slider
          :model-value="getThreshold(slider.key)"
          :min="0"
          :max="1"
          :step="0.05"
          color="primary"
          hide-details
          density="compact"
          @update:model-value="setThreshold(slider.key, $event as number)"
        />
      </div>
    </v-card-text>

    <v-divider />

    <v-card-title class="text-subtitle-1">PII Settings</v-card-title>
    <v-card-text>
      <v-select
        :model-value="String(thresholds.pii_action ?? 'flag')"
        :items="['flag', 'mask', 'block']"
        label="PII Action"
        variant="outlined"
        density="compact"
        hide-details
        class="mb-3"
        @update:model-value="setThreshold('pii_action', $event)"
      />
      <v-switch
        :model-value="thresholds.enable_canary ?? false"
        label="Enable canary tokens"
        color="primary"
        density="compact"
        hide-details
        @update:model-value="setThreshold('enable_canary', $event)"
      />
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
interface PolicyConfig {
  nodes: string[]
  thresholds: Record<string, unknown>
}

const props = defineProps<{ modelValue: PolicyConfig }>()
const emit = defineEmits<{ 'update:modelValue': [val: PolicyConfig] }>()

const AVAILABLE_NODES = [
  { id: 'llm_guard', label: 'LLM Guard', icon: 'mdi-shield-search' },
  { id: 'presidio', label: 'Presidio PII', icon: 'mdi-account-lock' },
  { id: 'ml_judge', label: 'ML Judge', icon: 'mdi-brain' },
  { id: 'output_filter', label: 'Output Filter', icon: 'mdi-filter' },
  { id: 'memory_hygiene', label: 'Memory Hygiene', icon: 'mdi-broom' },
  { id: 'logging', label: 'Logging', icon: 'mdi-text-box-outline' },
  { id: 'canary', label: 'Canary', icon: 'mdi-bird' },
]

const THRESHOLD_SLIDERS = [
  { key: 'max_risk', label: 'Max Risk' },
  { key: 'injection_threshold', label: 'Injection Threshold' },
  { key: 'toxicity_threshold', label: 'Toxicity Threshold' },
]

const WEIGHT_SLIDERS = [
  { key: 'injection_weight', label: 'Injection Weight' },
  { key: 'toxicity_weight', label: 'Toxicity Weight' },
  { key: 'secrets_weight', label: 'Secrets Weight' },
  { key: 'invisible_weight', label: 'Invisible Weight' },
  { key: 'pii_per_entity_weight', label: 'PII per Entity Weight' },
  { key: 'pii_max_weight', label: 'PII Max Weight' },
]

const nodes = computed(() => props.modelValue.nodes ?? [])
const thresholds = computed(() => (props.modelValue.thresholds ?? {}) as Record<string, unknown>)

function isEnabled(nodeId: string) {
  return nodes.value.includes(nodeId)
}

function toggleNode(nodeId: string) {
  const current = [...nodes.value]
  const idx = current.indexOf(nodeId)
  if (idx >= 0) current.splice(idx, 1)
  else current.push(nodeId)
  emit('update:modelValue', { ...props.modelValue, nodes: current })
}

function getThreshold(key: string): number {
  const val = thresholds.value[key]
  return typeof val === 'number' ? val : 0
}

function setThreshold(key: string, value: unknown) {
  const updated = { ...thresholds.value, [key]: value }
  emit('update:modelValue', { ...props.modelValue, thresholds: updated })
}

function sliderColor(val: number) {
  if (val < 0.5) return 'success'
  if (val < 0.8) return 'warning'
  return 'error'
}
</script>
