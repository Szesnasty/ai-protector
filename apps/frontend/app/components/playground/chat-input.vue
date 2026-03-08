<template>
  <div class="chat-input">
    <v-textarea
      v-model="text"
      :disabled="disabled"
      placeholder="Try a prompt injection, data leak, or jailbreak…"
      variant="outlined"
      rows="1"
      auto-grow
      max-rows="6"
      hide-details
      density="comfortable"
      class="chat-input__field"
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
}
</style>

<style lang="scss">
.chat-input__field.v-textarea .v-field {
  align-items: center;
}

.chat-input__field.v-textarea .v-field__prepend-inner {
  padding-top: 0 !important;
  align-self: center;
}
</style>
