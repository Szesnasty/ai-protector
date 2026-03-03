<template>
  <v-container fluid class="playground-page pa-0">
    <v-row class="playground-page__row" style="margin: 0; gap: 0;">
      <v-col cols="12" md="8" lg="9" class="playground-page__chat">
        <playground-chat-message-list
          :messages="messages"
          :is-streaming="isStreaming"
        />
        <playground-chat-input
          ref="chatInputRef"
          :disabled="isStreaming"
          @send="send"
        />
      </v-col>

      <v-col cols="12" md="4" lg="3" class="playground-page__sidebar">
        <playground-config-sidebar
          :config="config"
          :disabled="isStreaming"
          @update:config="Object.assign(config, $event)"
        />
        <v-divider class="my-2" />
        <playground-debug-panel :decision="lastDecision" />
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
      <v-icon>mdi-skull-crossbones</v-icon>
      <v-tooltip activator="parent" location="left">Attack Scenarios</v-tooltip>
    </v-btn>
  </v-container>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useChat } from '~/composables/useChat'
import { useScenarios } from '~/composables/useScenarios'

const ATTACK_SUBMIT_DELAY_MS = 300

definePageMeta({ title: 'Playground' })

const { messages, isStreaming, lastDecision, error, config, send, clear, abort } = useChat()
const { scenarios, isLoading: scenariosLoading } = useScenarios('playground')

const showScenarios = ref(true)
const chatInputRef = ref<{ setText: (s: string) => void } | null>(null)

function handleAttackSend(prompt: string) {
  chatInputRef.value?.setText(prompt)
  setTimeout(() => send(prompt), ATTACK_SUBMIT_DELAY_MS)
}
</script>

<style lang="scss" scoped>
.playground-page {
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
