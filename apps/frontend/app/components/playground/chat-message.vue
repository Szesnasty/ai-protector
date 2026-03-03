<template>
  <div
    class="chat-message"
    :class="`chat-message--${message.role}`"
  >
    <v-avatar size="32" class="chat-message__avatar">
      <v-icon>{{ icon }}</v-icon>
    </v-avatar>

    <v-card
      :color="cardColor"
      variant="tonal"
      class="chat-message__bubble"
    >
      <v-card-text class="text-body-1">
        {{ message.content }}
      </v-card-text>
    </v-card>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ChatMessage } from '~/types/api'

const props = defineProps<{
  message: ChatMessage
}>()

const isBlocked = computed(() => props.message.content?.startsWith('⛔'))

const icon = computed(() => {
  if (isBlocked.value) return 'mdi-shield-alert'
  return props.message.role === 'user' ? 'mdi-account-circle' : 'mdi-robot'
})

const cardColor = computed(() => {
  if (isBlocked.value) return 'error'
  return props.message.role === 'user' ? 'surface-variant' : 'primary'
})
</script>

<style lang="scss" scoped>
.chat-message {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;

  &--user {
    flex-direction: row-reverse;
  }

  &__avatar {
    flex-shrink: 0;
  }

  &__bubble {
    max-width: 75%;
  }
}
</style>
