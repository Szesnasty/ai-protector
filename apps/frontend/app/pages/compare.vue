<template>
  <v-container fluid class="compare-page pa-0">
    <!-- Top config bar -->
    <div class="compare-page__config">
      <div class="d-flex align-center flex-wrap ga-3 px-4 py-2">
        <v-icon size="20" color="primary">mdi-compare</v-icon>
        <span class="text-subtitle-2 font-weight-bold">Compare Playground</span>

        <v-divider vertical class="mx-1" />

        <v-select
          v-model="config.policy"
          :items="policyItems"
          :loading="policiesLoading"
          :disabled="isBusy"
          label="Policy"
          variant="outlined"
          density="compact"
          hide-details
          style="max-width: 180px"
        />

        <v-select
          v-model="config.model"
          :items="modelItems"
          :loading="modelsLoading"
          :disabled="isBusy || !hasExternalModels"
          label="Model"
          variant="outlined"
          density="compact"
          item-title="title"
          item-value="value"
          hide-details
          style="max-width: 240px"
        />

        <!-- Phase indicator -->
        <v-chip
          v-if="phase !== 'idle'"
          :color="phase === 'protected' ? 'info' : 'warning'"
          size="small"
          variant="tonal"
          class="ml-2"
        >
          <v-progress-circular indeterminate size="12" width="2" class="mr-1" />
          {{ phase === 'protected' ? 'Running: Protected…' : 'Running: Direct…' }}
        </v-chip>

        <v-spacer />

        <v-btn
          v-if="isBusy"
          size="small"
          variant="tonal"
          color="error"
          prepend-icon="mdi-stop"
          @click="abort"
        >
          Stop
        </v-btn>

        <v-btn
          size="small"
          variant="tonal"
          prepend-icon="mdi-delete"
          :disabled="isBusy"
          @click="clear"
        >
          Clear
        </v-btn>
      </div>
      <v-divider />

      <!-- No API key banner -->
      <v-alert
        v-if="!hasAvailableModel"
        type="warning"
        variant="tonal"
        density="compact"
        class="mx-4 mt-2 mb-0"
        prominent
      >
        <strong>No external API keys configured.</strong>
        Compare requires an external LLM provider (OpenAI, Anthropic, Google, or Mistral).
        Go to <nuxt-link to="/settings" class="text-decoration-underline">Settings</nuxt-link> to add an API key.
      </v-alert>

      <!-- Error banner -->
      <v-alert
        v-if="error"
        type="error"
        variant="tonal"
        density="compact"
        closable
        class="mx-4 mt-2 mb-0"
        @click:close="dismissError"
      >
        {{ error }}
      </v-alert>


      <v-divider />
    </div>

    <!-- Scenario context bar -->
    <div v-if="activeScenario" class="compare-page__scenario-bar">
      <div class="d-flex align-center ga-2 px-4 py-2">
        <v-icon size="16" color="warning">mdi-bullseye-arrow</v-icon>
        <span class="text-caption text-medium-emphasis">Scenario:</span>
        <span class="text-caption font-weight-bold">{{ activeScenario.label }}</span>
        <v-chip
          :color="scenarioDecisionColor"
          size="x-small"
          label
          variant="flat"
          class="ml-1"
        >
          Expected: {{ activeScenario.expectedDecision }}
        </v-chip>
        <div v-if="activeScenario.tags.length" class="d-flex ga-1 ml-1">
          <v-chip
            v-for="tag in activeScenario.tags"
            :key="tag"
            size="x-small"
            variant="outlined"
            label
          >
            {{ tag }}
          </v-chip>
        </div>
        <v-spacer />
        <v-btn
          icon="mdi-close"
          size="x-small"
          variant="text"
          @click="activeScenario = null"
        />
      </div>
      <v-divider />
    </div>

    <!-- Parity summary bar (benign compare) -->
    <div v-if="showParityBar" class="compare-page__parity-bar">
      <div class="d-flex align-center ga-2 px-4 py-2">
        <v-icon size="16" color="success">mdi-check-circle</v-icon>
        <span class="text-caption font-weight-bold" style="color: rgb(var(--v-theme-success))">Same safe result</span>
        <span class="text-caption text-medium-emphasis">&mdash;</span>
        <span class="text-caption text-medium-emphasis">Protected path added security checks with no behavior change</span>
      </div>
      <v-divider />
    </div>

    <!-- Two-column panels -->
    <div v-if="hasMessages" class="compare-page__panels">
      <div class="compare-page__panel">
        <compare-panel
          variant="protected"
          :messages="protectedMessages"
          :is-streaming="isProtectedStreaming"
          :decision="protectedDecision"
          :timing="timings.protected"
          :compare-mode="compareMode"
        />
      </div>

      <v-divider vertical />

      <div class="compare-page__panel">
        <compare-panel
          variant="direct"
          :messages="directMessages"
          :is-streaming="isDirectStreaming"
          :timing="timings.direct"
          :endpoint-url="directEndpointUrl"
          :is-direct-browser="isDirectBrowser"
          :compare-mode="compareMode"
        />
      </div>
    </div>

    <!-- Empty state -->
    <div v-else class="compare-page__panels compare-page__empty">
      <div class="text-center">
        <v-icon size="56" color="grey-darken-1" class="mb-3">mdi-compare</v-icon>
        <p class="text-h6 text-grey-lighten-1 mb-1">Compare Protected vs Direct</p>
        <p class="text-body-2 text-medium-emphasis mb-5" style="max-width: 480px">
          Run a prompt injection or jailbreak scenario to see how AI Protector
          blocks threats while the direct path lets them through.
        </p>
        <div class="d-flex flex-wrap justify-center ga-2">
          <v-chip
            prepend-icon="mdi-needle"
            variant="tonal"
            color="error"
            @click="showScenarios = true"
          >
            Prompt injection
          </v-chip>
          <v-chip
            prepend-icon="mdi-database-alert"
            variant="tonal"
            color="warning"
            @click="showScenarios = true"
          >
            Data leak
          </v-chip>
          <v-chip
            prepend-icon="mdi-lock-open-variant"
            variant="tonal"
            color="error"
            @click="showScenarios = true"
          >
            Jailbreak
          </v-chip>
          <v-chip
            prepend-icon="mdi-file-document-alert"
            variant="tonal"
            color="warning"
            @click="showScenarios = true"
          >
            Resume manipulation
          </v-chip>
        </div>
        <p class="text-caption text-medium-emphasis mt-4">
          Or type any prompt below to compare safe request parity.
        </p>
      </div>
    </div>

    <!-- Shared input at the bottom -->
    <div class="compare-page__input">
      <v-divider />
      <div class="px-4 py-2">
        <playground-chat-input
          ref="chatInputRef"
          :disabled="isBusy || !hasAvailableModel || !selectedModelAvailable"
          @send="handleManualSend"
        />
      </div>
    </div>

    <!-- Attack scenarios panel -->
    <attack-scenarios-panel
      v-model="showScenarios"
      :scenarios="scenarios ?? []"
      :loading="scenariosLoading"
      @send="handleAttackSend"
    />

    <v-btn
      icon
      size="large"
      :color="showScenarios ? 'error' : 'surface-variant'"
      class="compare-page__fab"
      elevation="8"
      @click="showScenarios = !showScenarios"
    >
      <v-icon color="red-lighten-1">mdi-skull-crossbones</v-icon>
      <v-tooltip activator="parent" location="left">Attack Scenarios</v-tooltip>
    </v-btn>
  </v-container>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useCompareChat } from '~/composables/useCompareChat'
import { useScenarios } from '~/composables/useScenarios'
import { usePolicies } from '~/composables/usePolicies'
import { useModels } from '~/composables/useModels'
import { decisionColor as _dc } from '~/utils/colors'
import { useRememberedModel } from '~/composables/useRememberedModel'
import { sortedPolicyItems } from '~/utils/policyOrder'

const ATTACK_SUBMIT_DELAY_MS = 300

definePageMeta({ title: 'Compare' })

const {
  protectedMessages,
  directMessages,
  isProtectedStreaming,
  isDirectStreaming,
  protectedDecision,
  timings,
  error,
  config,
  phase,
  isBusy,
  directEndpointUrl,
  isDirectBrowser,
  send,
  clear,
  abort,
} = useCompareChat()

const { scenarios, isLoading: scenariosLoading } = useScenarios('compare')
const { policies, isLoading: policiesLoading } = usePolicies()
const { groupedModels, isLoading: modelsLoading, refreshAvailability } = useModels()

const showScenarios = ref(true)
const chatInputRef = ref<{ setText: (s: string) => void } | null>(null)
const activeScenario = ref<import('~/types/scenarios').ScenarioItem | null>(null)

const scenarioDecisionColor = computed(() => {
  if (!activeScenario.value) return 'grey'
  return _dc(activeScenario.value.expectedDecision)
})

const compareMode = computed<'neutral' | 'attack'>(() => {
  if (!protectedDecision.value) return 'neutral'
  const d = protectedDecision.value.decision
  return (d === 'BLOCK' || d === 'MODIFY') ? 'attack' : 'neutral'
})

const hasMessages = computed(() => protectedMessages.value.length > 0)

/** Show parity bar when both sides completed with safe results. */
const showParityBar = computed(() =>
  compareMode.value === 'neutral'
  && protectedDecision.value?.decision === 'ALLOW'
  && protectedMessages.value.some(m => m.role === 'assistant' && m.content?.trim())
  && directMessages.value.some(m => m.role === 'assistant' && m.content?.trim()),
)

const policyItems = computed(() => sortedPolicyItems(policies.value ?? []))

const PROVIDER_LABELS: Record<string, string> = {
  openai: 'OpenAI',
  anthropic: 'Anthropic',
  google: 'Google AI',
  mistral: 'Mistral',
}

/** All models available in Compare mode. */
const allModels = computed(() => groupedModels.value ?? [])

const hasExternalModels = computed(() => allModels.value.length > 0)

const hasAvailableModel = computed(() =>
  allModels.value.some((m) => m.available),
)

/** Only show models that are available (Ollama always + providers with key). */
const modelItems = computed(() =>
  allModels.value
    .filter((m) => m.available)
    .map((m) => ({
      title: `${m.name}  ·  ${PROVIDER_LABELS[m.provider] ?? m.provider}`,
      value: m.id,
    })),
)

/** Whether the currently selected model has an API key. */
const selectedModelAvailable = computed(() => {
  if (!config.model) return false
  const m = allModels.value.find((model) => model.id === config.model)
  return m?.available ?? false
})

const rememberedModel = useRememberedModel('compare')

/**
 * Auto-select model:
 * 1. Restore remembered model from localStorage (if still available)
 * 2. Otherwise pick first available external model
 * 3. Fallback to Ollama
 */
watch(
  allModels,
  (models) => {
    const saved = rememberedModel.get()
    if (saved) {
      const mem = models.find((m) => m.id === saved && m.available)
      if (mem) { config.model = mem.id; return }
    }
    if (config.model) {
      const current = models.find((m) => m.id === config.model)
      if (current?.available) return
    }
    const firstExternal = models.find((m) => m.available && m.provider !== 'ollama')
    if (firstExternal) { config.model = firstExternal.id; return }
    const firstAny = models.find((m) => m.available)
    config.model = firstAny?.id ?? ''
  },
  { immediate: true },
)

watch(() => config.model, (id) => rememberedModel.set(id))

/**
 * Re-check API key availability when user returns to this tab
 * (e.g. after adding a key in Settings opened in another tab).
 */
function onVisibilityChange() {
  if (document.visibilityState === 'visible') refreshAvailability()
}

onMounted(() => {
  refreshAvailability() // pick up keys added since last visit
  window.addEventListener('visibilitychange', onVisibilityChange)
})

onUnmounted(() => {
  window.removeEventListener('visibilitychange', onVisibilityChange)
})

function dismissError() {
  error.value = null
}

function handleManualSend(prompt: string) {
  activeScenario.value = null
  send(prompt)
}

function handleAttackSend(prompt: string, scenario: import('~/types/scenarios').ScenarioItem) {
  activeScenario.value = scenario
  chatInputRef.value?.setText(prompt)
  setTimeout(() => send(prompt), ATTACK_SUBMIT_DELAY_MS)
}
</script>

<style lang="scss" scoped>
.compare-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 64px);

  &__config {
    flex-shrink: 0;
  }

  &__scenario-bar {
    flex-shrink: 0;
    background: rgba(var(--v-theme-warning), 0.06);
    border-bottom: 1px solid rgba(var(--v-theme-warning), 0.15);

    :deep(.v-chip) {
      font-size: 11px !important;
    }
  }

  &__parity-bar {
    flex-shrink: 0;
    background: rgba(var(--v-theme-success), 0.05);
    border-bottom: 1px solid rgba(var(--v-theme-success), 0.12);

    :deep(.v-chip) {
      font-size: 11px !important;
    }
  }

  &__empty {
    display: flex;
    align-items: center;
    justify-content: center;
    flex-direction: column;
  }

  &__explainer {
    display: flex;
    align-items: flex-start;
    background: rgba(var(--v-theme-info), 0.05);
  }

  &__panels {
    flex: 1;
    display: flex;
    min-height: 0;
    overflow: hidden;
  }

  &__panel {
    flex: 1;
    min-width: 0;
    min-height: 0;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  &__input {
    flex-shrink: 0;
  }

  &__fab {
    position: fixed !important;
    top: 80px;
    right: 24px;
    z-index: 1000;
  }
}
</style>
