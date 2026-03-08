<template>
  <div ref="listRef" class="chat-message-list">
    <div v-if="messages.length === 0" class="chat-message-list__empty">
      <v-icon size="48" color="grey-darken-1">mdi-shield-search</v-icon>
      <p class="text-h6 font-weight-medium">
        Test the firewall against real attack scenarios
      </p>
      <p class="text-body-2 text-medium-emphasis" style="max-width: 420px; text-align: center;">
        Run a prompt injection, data leak, jailbreak, or resume manipulation scenario and inspect the decision step by step.
      </p>
      <div class="d-flex flex-wrap justify-center ga-2 mt-1">
        <v-chip prepend-icon="mdi-needle" variant="tonal" color="error" @click="emit('open-scenarios')">
          Prompt injection
        </v-chip>
        <v-chip prepend-icon="mdi-database-alert" variant="tonal" color="warning" @click="emit('open-scenarios')">
          Data leak
        </v-chip>
        <v-chip prepend-icon="mdi-lock-open-variant" variant="tonal" color="error" @click="emit('open-scenarios')">
          Jailbreak
        </v-chip>
        <v-chip prepend-icon="mdi-file-document-alert" variant="tonal" color="warning" @click="emit('open-scenarios')">
          Resume manipulation
        </v-chip>
      </div>
      <p class="text-caption text-medium-emphasis mt-2">
        Or enter any prompt below to test the pipeline manually.
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

const emit = defineEmits<{
  'open-scenarios': []
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
