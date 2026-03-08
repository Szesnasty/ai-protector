<template>
  <div class="agent-chat">
    <!-- Messages area -->
    <div ref="listRef" class="agent-chat__messages">
      <div v-if="messages.length === 0" class="agent-chat__empty">
        <v-icon size="48" color="primary">mdi-shield-search</v-icon>
        <p class="text-h6 font-weight-medium">
          Test the Agent Firewall
        </p>
        <p class="text-body-2 text-medium-emphasis" style="max-width: 360px; text-align: center;">
          Chat with the Customer Support Copilot to test tool-calling, RBAC, and firewall integration.
        </p>
      </div>

      <agent-message
        v-for="msg in messages"
        :key="msg.id"
        :message="msg"
      />

      <v-progress-linear
        v-if="isLoading"
        indeterminate
        color="primary"
        class="mt-2"
      />

      <div ref="anchorRef" />
    </div>

    <!-- Input area -->
    <div class="agent-chat__input">
      <v-textarea
        v-model="text"
        :disabled="isLoading"
        placeholder="Type a message…"
        variant="outlined"
        rows="1"
        auto-grow
        max-rows="6"
        hide-details
        density="comfortable"
        class="agent-chat__field"
        @keydown.enter.exact.prevent="handleSend"
      >
        <template #prepend-inner>
          <v-icon size="20" color="medium-emphasis" class="mr-1">mdi-shield-search</v-icon>
        </template>
        <template #append-inner>
          <v-btn
            icon="mdi-send"
            variant="text"
            size="small"
            :disabled="isLoading || !text.trim()"
            @click="handleSend"
          />
        </template>
      </v-textarea>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import type { AgentMessage } from '~/types/agent'

const props = defineProps<{
  messages: AgentMessage[]
  isLoading: boolean
}>()

const emit = defineEmits<{
  send: [text: string]
}>()

const text = ref('')
const listRef = ref<HTMLElement | null>(null)
const anchorRef = ref<HTMLElement | null>(null)

function handleSend() {
  const trimmed = text.value.trim()
  if (!trimmed) return
  emit('send', trimmed)
  text.value = ''
}

function setText(value: string) {
  text.value = value
}

defineExpose({ setText })

watch(
  () => props.messages.length,
  async () => {
    await nextTick()
    anchorRef.value?.scrollIntoView({ behavior: 'smooth' })
  },
)
</script>

<style lang="scss" scoped>
.agent-chat {
  display: flex;
  flex-direction: column;
  height: 100%;

  &__messages {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
  }

  &__empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    gap: 12px;
  }

  &__input {
    padding: 12px 16px;
  }
}
</style>

<style lang="scss">
.agent-chat__field.v-textarea .v-field {
  align-items: center;
}

.agent-chat__field.v-textarea .v-field__prepend-inner {
  padding-top: 0 !important;
  align-self: center;
}
</style>
