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
          :disabled="isLoading"
          @update:role="switchRole"
          @update:policy="config.policy = $event"
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
      :scenarios="agentScenarios"
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
      <v-icon>mdi-skull-crossbones</v-icon>
      <v-tooltip activator="parent" location="left">Attack Scenarios</v-tooltip>
    </v-btn>
  </v-container>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useAgentChat } from '~/composables/useAgentChat'
import { agentScenarios } from '~/composables/useAgentScenarios'

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

const showScenarios = ref(true)
const agentChatRef = ref<{ setText: (s: string) => void } | null>(null)

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
