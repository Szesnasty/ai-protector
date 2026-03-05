<template>
  <v-container fluid class="agent-page pa-0">
    <v-row class="agent-page__row" style="margin: 0; gap: 0;">
      <v-col cols="12" md="8" lg="9" class="agent-page__chat">
        <agent-chat
          ref="agentChatRef"
          :messages="messages"
          :is-loading="isLoading"
          @send="sendMessage"
        />
      </v-col>

      <v-col cols="12" md="4" lg="3" class="agent-page__sidebar">
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
        <v-divider class="my-2" />
        <agent-trace-panel
          :trace="lastTrace"
          :decision="lastFirewallDecision"
        />
      </v-col>
    </v-row>

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
      class="attack-fab"
      elevation="8"
      @click="showScenarios = !showScenarios"
    >
      <v-icon color="red-lighten-1">mdi-skull-crossbones</v-icon>
      <v-tooltip activator="parent" location="left">Attack Scenarios</v-tooltip>
    </v-btn>
  </v-container>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { useAgentChat } from '~/composables/useAgentChat'
import { useScenarios } from '~/composables/useScenarios'
import { useModels } from '~/composables/useModels'
import { useRememberedModel } from '~/composables/useRememberedModel'

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

const showScenarios = ref(true)
const agentChatRef = ref<{ setText: (s: string) => void } | null>(null)

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

function handleAttackSend(prompt: string) {
  agentChatRef.value?.setText(prompt)
  setTimeout(() => sendMessage(prompt), ATTACK_SUBMIT_DELAY_MS)
}
</script>

<style lang="scss" scoped>
.agent-page {
  height: calc(100vh - 64px);

  &__row {
    height: 100%;
  }

  &__chat {
    display: flex;
    flex-direction: column;
    height: 100%;
  }

  &__sidebar {
    border-left: 1px solid rgb(var(--v-border-color));
    height: 100%;
    overflow-y: auto;
  }
}

.attack-fab {
  position: fixed !important;
  top: 80px;
  right: 24px;
  z-index: 1000;
}
</style>
