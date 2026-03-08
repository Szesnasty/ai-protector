<template>
  <v-container fluid class="agent-page pa-0">
    <!-- Scenario context bar -->
    <div v-if="activeScenario" class="scenario-bar">
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
        <v-btn size="x-small" variant="tonal" class="mr-1" @click="showScenarios = true">
          Change
        </v-btn>
        <v-btn
          icon="mdi-close"
          size="x-small"
          variant="text"
          @click="activeScenario = null"
        />
      </div>
    </div>

    <div class="agent-page__layout">
      <div class="agent-page__chat">
        <agent-chat
          ref="agentChatRef"
          :messages="messages"
          :is-loading="isLoading"
          @send="handleManualSend"
          @open-scenarios="showScenarios = true"
        />
      </div>

      <div class="agent-page__sidebar">
        <agent-config
          :role="config.role"
          :policy="config.policy"
          :model="config.model"
          :disabled="isLoading"
          @update:role="switchRole"
          @update:policy="config.policy = $event"
          @update:model="config.model = $event"
          @new-conversation="newConversation"
        />
        <agent-trace-panel
          :trace="lastTrace"
          :decision="lastFirewallDecision"
        />
      </div>
    </div>

    <attack-scenarios-panel
      v-model="showScenarios"
      :scenarios="scenarios ?? []"
      :loading="scenariosLoading"
      @send="handleAttackSend"
    />

    <v-btn
      icon
      size="large"
      :color="showScenarios ? 'primary' : 'surface-variant'"
      class="attack-fab"
      :class="{ 'attack-fab--idle': !showScenarios }"
      elevation="8"
      @click="showScenarios = !showScenarios"
    >
      <v-icon color="red-darken-2">mdi-skull-crossbones</v-icon>
      <v-tooltip activator="parent" location="left">Attack Scenarios</v-tooltip>
    </v-btn>
  </v-container>
</template>

<script setup lang="ts">
import { ref, watch, computed, onMounted, onUnmounted } from 'vue'
import { useAgentChat } from '~/composables/useAgentChat'
import { useScenarios } from '~/composables/useScenarios'
import { useModels } from '~/composables/useModels'
import { useRememberedModel } from '~/composables/useRememberedModel'
import { decisionColor as _dc } from '~/utils/colors'
import type { ScenarioItem } from '~/types/scenarios'

const ATTACK_SUBMIT_DELAY_MS = 300

definePageMeta({ title: 'Agent Demo' })

const {
  messages,
  isLoading,
  config,
  lastTrace,
  lastFirewallDecision,
  sendMessage,
  switchRole,
  newConversation,
} = useAgentChat()

const { scenarios, isLoading: scenariosLoading } = useScenarios('agent')
const { groupedModels, refreshAvailability } = useModels()
const rememberedModel = useRememberedModel('agent')

const showScenarios = ref(false)
const activeScenario = ref<ScenarioItem | null>(null)
const agentChatRef = ref<{ setText: (s: string) => void } | null>(null)

const scenarioDecisionColor = computed(() => {
  if (!activeScenario.value) return 'grey'
  return _dc(activeScenario.value.expectedDecision)
})

/**
 * Auto-select model:
 * 1. Restore remembered model from localStorage (if still available)
 * 2. Otherwise pick first available external model
 * 3. Fallback to Ollama
 */
watch(
  groupedModels,
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

function onVisibilityChange() {
  if (document.visibilityState === 'visible') refreshAvailability()
}

onMounted(() => {
  refreshAvailability()
  window.addEventListener('visibilitychange', onVisibilityChange)
})

onUnmounted(() => {
  window.removeEventListener('visibilitychange', onVisibilityChange)
})

function handleAttackSend(prompt: string, scenario: ScenarioItem) {
  activeScenario.value = scenario
  showScenarios.value = false
  agentChatRef.value?.setText(prompt)
  setTimeout(() => sendMessage(prompt), ATTACK_SUBMIT_DELAY_MS)
}

function handleManualSend(prompt: string) {
  activeScenario.value = null
  sendMessage(prompt)
}
</script>

<style lang="scss" scoped>
.agent-page {
  height: calc(100vh - 64px);
  display: flex;
  flex-direction: column;

  &__layout {
    display: flex;
    flex: 1;
    min-height: 0;
  }

  &__chat {
    flex: 1 1 0;
    min-width: 0;
    display: flex;
    flex-direction: column;
    height: 100%;
  }

  &__sidebar {
    flex: 0 0 320px;
    height: 100%;
    overflow-y: auto;
    padding: 16px 8px 16px 16px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
}

@media (max-width: 959px) {
  .agent-page {
    &__layout {
      flex-direction: column;
      overflow-y: auto;
    }

    &__chat {
      flex: none;
      min-height: 60vh;
    }

    &__sidebar {
      flex: none;
      width: 100%;
      padding: 16px;
    }
  }
}

.attack-fab {
  position: fixed !important;
  bottom: 24px;
  right: 24px;
  z-index: 1000;
  border-radius: 50% !important;
  transition: box-shadow 0.3s ease;

  &--idle {
    animation: fab-pulse 2.8s ease-in-out infinite;
    box-shadow:
      0 0 8px 2px rgba(239, 68, 68, 0.15),
      0 0 20px 4px rgba(239, 68, 68, 0.06) !important;
  }
}

@keyframes fab-pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.08); }
}

.scenario-bar {
  flex-shrink: 0;
  background: rgba(var(--v-theme-warning), 0.06);
  border-bottom: 1px solid rgba(var(--v-theme-warning), 0.15);

  :deep(.v-chip) {
    font-size: 12px !important;
  }
}
</style>
