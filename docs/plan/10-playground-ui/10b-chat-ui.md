# 10b — Chat UI

| | |
|---|---|
| **Parent** | [Step 10 — Playground](SPEC.md) |
| **Prev sub-step** | [10a — Chat Service & Composable](10a-chat-service.md) |
| **Next sub-step** | [10c — Config Sidebar & Debug Panel](10c-config-debug.md) |
| **Estimated time** | 2–3 hours |

---

## Goal

Build the Playground page and chat components that wire to the `useChat` composable from 10a. Users will be able to type prompts, see streamed assistant responses, and observe BLOCK messages — all rendered in a clean Vuetify-based chat interface.

> **Convention:** `<script setup lang="ts">`. Kebab-case files and template tags.
> Styles: `<style lang="scss" scoped>`.

---

## Tasks

### 1. Page route (`app/pages/playground.vue`)

- [ ] Registered automatically by Nuxt file-based routing
- [ ] Layout: two-column grid using `v-row` / `v-col`:
  - **Left (col 8–9)**: Chat area (message list + input)
  - **Right (col 3–4)**: Config sidebar + debug panel (built in 10c, slot/empty placeholder for now)
- [ ] Imports and uses `useChat()` composable
- [ ] Passes `messages`, `isStreaming`, `error` to child components

```vue
<template>
  <v-container fluid class="playground-page">
    <v-row no-gutters>
      <v-col cols="12" md="8" lg="9" class="playground-page__chat">
        <chat-message-list
          :messages="messages"
          :is-streaming="isStreaming"
        />
        <chat-input
          :disabled="isStreaming"
          @send="send"
        />
      </v-col>

      <v-col cols="12" md="4" lg="3" class="playground-page__sidebar">
        <!-- config-sidebar & debug-panel rendered in 10c -->
        <slot name="sidebar" />
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup lang="ts">
import { useChat } from '~/composables/useChat'

const { messages, isStreaming, error, send } = useChat()
</script>

<style lang="scss" scoped>
.playground-page {
  height: calc(100vh - 64px); // Below nav bar

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
```

### 2. Message list (`app/components/playground/chat-message-list.vue`)

- [ ] Props:
  ```typescript
  interface Props {
    messages: ChatMessage[]
    isStreaming: boolean
  }
  ```

- [ ] Renders each message via `<chat-message>` component
- [ ] Auto-scrolls to bottom on new message / streaming token (use `nextTick` + `scrollIntoView`)
- [ ] Show a subtle typing indicator (three-dot animation or `v-progress-linear indeterminate`) when `isStreaming` is true and last message content is still empty
- [ ] If `messages` is empty, show a centered placeholder:
  ```
  "Type a message to start testing the AI Protector pipeline."
  ```

```vue
<template>
  <div ref="listRef" class="chat-message-list">
    <div v-if="messages.length === 0" class="chat-message-list__empty">
      <v-icon size="48" color="grey-lighten-1">mdi-chat-outline</v-icon>
      <p class="text-body-1 text-grey">Type a message to start testing the AI Protector pipeline.</p>
    </div>

    <chat-message
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

// Auto-scroll when messages change
watch(
  () => props.messages.length,
  async () => {
    await nextTick()
    anchorRef.value?.scrollIntoView({ behavior: 'smooth' })
  },
)

// Also scroll during streaming (content updates)
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
```

### 3. Single message (`app/components/playground/chat-message.vue`)

- [ ] Props:
  ```typescript
  interface Props {
    message: ChatMessage
  }
  ```

- [ ] Layout: Bubble-style with role icon on the left
  - **user**: `mdi-account-circle` icon, right-aligned or muted background
  - **assistant**: `mdi-robot` icon, left-aligned
  - **blocked messages** (containing `⛔`): red-tinted background, `mdi-shield-alert` icon

- [ ] Content rendered as plain text (Markdown rendering is out of scope for MVP, can be added later)
- [ ] Visual distinction between roles (color, alignment or border)

```vue
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
```

### 4. Chat input (`app/components/playground/chat-input.vue`)

- [ ] Props:
  ```typescript
  interface Props {
    disabled?: boolean
  }
  ```

- [ ] Emits: `send(text: string)`
- [ ] Uses `v-textarea` with `rows="1"` and `auto-grow` for multiline support
- [ ] Send on **Enter** (without Shift), Shift+Enter for newline
- [ ] Send button (icon `mdi-send`) appended via `append-inner` slot
- [ ] Clears input after emit
- [ ] Disabled state: input + button grayed out while streaming

```vue
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
</script>

<style lang="scss" scoped>
.chat-input {
  padding: 12px 16px;
  border-top: 1px solid rgb(var(--v-border-color));
}
</style>
```

---

## File tree (after this sub-step)

```
app/
  pages/
    playground.vue
  components/
    playground/
      chat-message-list.vue
      chat-message.vue
      chat-input.vue
```

---

## Definition of Done

- [ ] `/playground` route renders the two-column layout
- [ ] Chat message list shows empty placeholder when no messages
- [ ] User can type a message and press Enter to send
- [ ] User message appears immediately (optimistic push from `useChat`)
- [ ] Assistant response streams in token-by-token (visible real-time text append)
- [ ] BLOCK responses show a red-tinted card with shield icon and block reason
- [ ] Chat auto-scrolls to bottom during streaming
- [ ] Typing indicator shows while waiting for first token
- [ ] Input is disabled during streaming, re-enabled on completion
- [ ] Shift+Enter creates a newline (no send)
- [ ] All `.vue` files use `<script setup lang="ts">`
- [ ] All component files are kebab-case
- [ ] All styles use `<style lang="scss" scoped>`
- [ ] `npx nuxi typecheck` passes

---

| **Prev** | **Next** |
|---|---|
| [10a — Chat Service](10a-chat-service.md) | [10c — Config Sidebar & Debug Panel](10c-config-debug.md) |
