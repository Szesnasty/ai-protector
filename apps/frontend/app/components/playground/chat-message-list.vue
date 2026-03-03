<template>
  <div ref="listRef" class="chat-message-list">
    <div v-if="messages.length === 0" class="chat-message-list__empty">
      <v-icon size="48" color="grey-lighten-1">mdi-chat-outline</v-icon>
      <p class="text-body-1 text-grey">
        Type a message to start testing the AI Protector pipeline.
      </p>
    </div>

    <playground-chat-message
      v-for="(msg, idx) in messages"
      :key="idx"
      :message="msg"
    />

    <v-progress-linear
      v-if="isStreaming && lastMessageEmpty"
      indeterminate
      color="primary"
      class="mt-2"
    />

    <div ref="anchorRef" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import type { ChatMessage } from '~/types/api'

const props = defineProps<{
  messages: ChatMessage[]
  isStreaming: boolean
}>()

const listRef = ref<HTMLElement | null>(null)
const anchorRef = ref<HTMLElement | null>(null)

const lastMessageEmpty = computed(() => {
  const last = props.messages[props.messages.length - 1]
  return last?.role === 'assistant' && !last.content
})

watch(
  () => props.messages.length,
  async () => {
    await nextTick()
    anchorRef.value?.scrollIntoView({ behavior: 'smooth' })
  },
)

watch(
  () => props.messages[props.messages.length - 1]?.content,
  async () => {
    if (props.isStreaming) {
      await nextTick()
      anchorRef.value?.scrollIntoView({ behavior: 'smooth' })
    }
  },
)
</script>

<style lang="scss" scoped>
.chat-message-list {
  flex: 1;
  overflow-y: auto;
  padding: 16px;

  &__empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    gap: 12px;
  }
}
</style>
