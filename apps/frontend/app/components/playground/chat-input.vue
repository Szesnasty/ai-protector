<template>
  <div class="chat-input">
    <v-textarea
      v-model="text"
      :disabled="disabled"
      placeholder="Type a message…"
      variant="outlined"
      rows="1"
      auto-grow
      max-rows="6"
      hide-details
      density="comfortable"
      @keydown.enter.exact.prevent="handleSend"
    >
      <template #append-inner>
        <v-btn
          icon="mdi-send"
          variant="text"
          size="small"
          :disabled="disabled || !text.trim()"
          @click="handleSend"
        />
      </template>
    </v-textarea>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

defineProps<{
  disabled?: boolean
}>()

const emit = defineEmits<{
  send: [text: string]
}>()

const text = ref('')

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
</script>

<style lang="scss" scoped>
.chat-input {
  padding: 12px 16px;
  border-top: 1px solid rgb(var(--v-border-color));
}
</style>
