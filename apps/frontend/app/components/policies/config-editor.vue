<template>
  <v-card variant="outlined" class="mb-4">
    <v-card-title class="text-subtitle-1">Scanner Nodes</v-card-title>
    <v-card-text>
      <div class="d-flex flex-wrap ga-2">
        <v-tooltip v-for="node in AVAILABLE_NODES" :key="node.id" location="top">
          <template #activator="{ props: tip }">
            <v-chip
              v-bind="tip"
              :color="isEnabled(node.id) ? 'primary' : undefined"
              :variant="isEnabled(node.id) ? 'flat' : 'outlined'"
              :prepend-icon="node.icon"
              @click="toggleNode(node.id)"
            >
              {{ node.label }}
            </v-chip>
          </template>
          <span>{{ node.tooltip }}</span>
        </v-tooltip>
      </div>
    </v-card-text>

    <v-divider />

    <v-card-title class="text-subtitle-1">Risk Thresholds</v-card-title>
    <v-card-text>
      <div v-for="slider in THRESHOLD_SLIDERS" :key="slider.key" class="mb-2">
        <div class="d-flex justify-space-between text-body-2 mb-1">
          <span class="d-flex align-center ga-1">
            {{ slider.label }}
            <v-tooltip location="top">
              <template #activator="{ props: tip }">
                <v-icon v-bind="tip" size="x-small" color="grey">mdi-information-outline</v-icon>
              </template>
              <span style="max-width: 280px; display: block;">{{ slider.tooltip }}</span>
            </v-tooltip>
          </span>
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
          <span class="d-flex align-center ga-1">
            {{ slider.label }}
            <v-tooltip location="top">
              <template #activator="{ props: tip }">
                <v-icon v-bind="tip" size="x-small" color="grey">mdi-information-outline</v-icon>
              </template>
              <span style="max-width: 280px; display: block;">{{ slider.tooltip }}</span>
            </v-tooltip>
          </span>
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
      <div class="d-flex align-center ga-1 mb-2">
        <span class="text-body-2">PII Action</span>
        <v-tooltip location="top">
          <template #activator="{ props: tip }">
            <v-icon v-bind="tip" size="x-small" color="grey">mdi-information-outline</v-icon>
          </template>
          <span style="max-width: 280px; display: block;">How to handle detected PII. Flag — log only. Mask — replace with placeholders like &lt;PERSON&gt;. Block — reject the request entirely.</span>
        </v-tooltip>
      </div>
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
  { id: 'llm_guard', label: 'LLM Guard', icon: 'mdi-shield-search', tooltip: 'ProtectAI ML scanners: prompt injection (DeBERTa), toxicity, secrets leakage, banned substrings, invisible Unicode characters.' },
  { id: 'presidio', label: 'Presidio PII', icon: 'mdi-account-lock', tooltip: 'Microsoft Presidio PII detection — identifies PERSON, EMAIL, PHONE, CREDIT_CARD, SSN, IP, IBAN and more using spaCy NER + regex.' },
  { id: 'nemo_guardrails', label: 'NeMo Guardrails', icon: 'mdi-shield-lock', tooltip: 'NVIDIA NeMo Guardrails — Colang-based semantic intent matching for 11 attack categories (role bypass, tool abuse, exfiltration, social engineering, etc.). Zero LLM calls, ~7ms per scan.' },
  { id: 'ml_judge', label: 'ML Judge', icon: 'mdi-brain', tooltip: 'Additional ML-based risk judge (placeholder — not yet implemented).' },
  { id: 'output_filter', label: 'Output Filter', icon: 'mdi-filter', tooltip: 'Post-LLM output filtering — removes PII, secrets, and data leaks from LLM responses before sending to the user.' },
  { id: 'memory_hygiene', label: 'Memory Hygiene', icon: 'mdi-broom', tooltip: 'Sanitizes conversation history — strips PII and sensitive data from session memory before storage.' },
  { id: 'logging', label: 'Logging', icon: 'mdi-text-box-outline', tooltip: 'Full audit logging to PostgreSQL and Langfuse for observability, compliance, and analytics.' },
  { id: 'canary', label: 'Canary', icon: 'mdi-bird', tooltip: 'Canary token injection to detect data leakage (placeholder — not yet implemented).' },
]

const THRESHOLD_SLIDERS = [
  { key: 'max_risk', label: 'Max Risk', tooltip: 'Maximum aggregated risk score allowed before the request is blocked. Lower = stricter. A score above this threshold triggers BLOCK.' },
  { key: 'injection_threshold', label: 'Injection Threshold', tooltip: 'LLM Guard prompt injection detection sensitivity. Lower = more sensitive to injection attempts. Used by the PromptInjection DeBERTa scanner.' },
  { key: 'toxicity_threshold', label: 'Toxicity Threshold', tooltip: 'LLM Guard toxicity detection sensitivity. Lower = catches milder toxicity. Used by the Toxicity scanner for hateful, violent, or offensive content.' },
]

const WEIGHT_SLIDERS = [
  { key: 'injection_weight', label: 'Injection Weight', tooltip: 'How much a prompt injection detection contributes to the total risk score. 0 = ignored, 1 = full weight. Default: 0.80.' },
  { key: 'toxicity_weight', label: 'Toxicity Weight', tooltip: 'How much a toxicity detection contributes to the total risk score. 0 = ignored, 1 = full weight. Default: 0.50.' },
  { key: 'secrets_weight', label: 'Secrets Weight', tooltip: 'Risk score added when API keys, passwords, or tokens are detected in the prompt. 0 = ignored, 1 = full weight. Default: 0.60.' },
  { key: 'invisible_weight', label: 'Invisible Weight', tooltip: 'Risk score added when invisible Unicode characters (zero-width spaces, etc.) are detected — often used for prompt injection. Default: 0.40.' },
  { key: 'pii_per_entity_weight', label: 'PII per Entity Weight', tooltip: 'Risk score added per PII entity found (PERSON, EMAIL, etc.). Accumulates with each entity. Default: 0.10 per entity.' },
  { key: 'pii_max_weight', label: 'PII Max Weight', tooltip: 'Maximum total risk score that PII detection can contribute regardless of entity count. Caps the PII risk accumulation. Default: 0.50.' },
  { key: 'nemo_weight', label: 'NeMo Weight', tooltip: 'How much a NeMo Guardrails attack detection (role bypass, tool abuse, exfiltration, etc.) contributes to the total risk score. Multiplied by the rail confidence (0.85). Default: 0.70.' },
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
