<template>
  <v-container fluid class="agent-page pa-0">
    <v-row class="agent-page__row" style="margin: 0; gap: 0;">
      <v-col cols="12" md="8" lg="9" class="agent-page__chat">
        <agent-chat
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
  </v-container>
</template>

<script setup lang="ts">
import { useAgentChat } from '~/composables/useAgentChat'

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
</style>
