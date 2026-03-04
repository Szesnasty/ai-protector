<template>
  <div class="compare-panel" :class="[`compare-panel--${variant}`]">
    <!-- Header Badge & Endpoint Info -->
    <div class="compare-panel__header">
      <div class="compare-panel__badge">
        <v-chip
          :color="variant === 'protected' ? 'success' : 'warning'"
          size="small"
          label
          class="font-weight-bold"
        >
          <v-icon start size="16">
            {{ variant === 'protected' ? 'mdi-shield-check' : 'mdi-shield-off' }}
          </v-icon>
          {{ variant === 'protected' ? 'Protected' : 'Unprotected' }}
        </v-chip>

        <v-chip
          v-if="timing !== null && timing !== undefined"
          size="x-small"
          variant="outlined"
          class="ml-2"
        >
          <v-icon start size="12">mdi-clock-outline</v-icon>
          {{ timing }}ms
        </v-chip>
      </div>

      <!-- Code snippet — drop-in replacement demo -->
      <div class="compare-panel__code-snippet mt-2">
        <div class="code-snippet__header">
          <v-icon size="14" color="grey-lighten-1">mdi-language-python</v-icon>
          <span class="text-caption text-grey ml-1">Python — OpenAI SDK</span>
        </div>
        <pre class="code-snippet__block"><span class="c-var">client</span> = <span class="c-fn">OpenAI</span>(
  <span class="c-key">api_key</span>=<span class="c-str">"sk-..."</span>,
  <span class="c-key">base_url</span>=<span class="c-str">"{{ codeBaseUrl }}"</span>  <span class="c-comment">{{ codeComment }}</span>
)</pre>
      </div>

      <!-- Actual HTTP endpoint -->
      <div class="compare-panel__endpoint mt-1">
        <code class="compare-panel__url">
          <v-icon size="12" class="mr-1">mdi-arrow-right-bold</v-icon>
          POST {{ endpoint }}
        </code>
      </div>

      <!-- Flow explanation -->
      <div class="compare-panel__flow mt-2">
        <div v-if="variant === 'protected'" class="d-flex align-center flex-wrap ga-1">
          <v-chip size="x-small" color="blue-grey" variant="tonal" label>Prompt</v-chip>
          <v-icon size="14" color="grey">mdi-arrow-right</v-icon>
          <v-chip size="x-small" color="primary" variant="tonal" label>
            <v-icon start size="12">mdi-shield-check</v-icon>
            AI Protector Pipeline
          </v-chip>
          <v-icon size="14" color="grey">mdi-arrow-right</v-icon>
          <v-chip size="x-small" color="blue-grey" variant="tonal" label>LLM</v-chip>
        </div>
        <div v-else class="d-flex align-center flex-wrap ga-1">
          <v-chip size="x-small" color="blue-grey" variant="tonal" label>Prompt</v-chip>
          <v-icon size="14" color="grey">mdi-arrow-right</v-icon>
          <v-chip size="x-small" color="warning" variant="tonal" label>
            <v-icon start size="12">{{ isDirectBrowser ? 'mdi-web' : 'mdi-shield-off' }}</v-icon>
            {{ isDirectBrowser ? 'Browser → Provider API' : 'Proxy (no scanning)' }}
          </v-chip>
          <v-icon size="14" color="grey">mdi-arrow-right</v-icon>
          <v-chip size="x-small" color="blue-grey" variant="tonal" label>LLM</v-chip>
        </div>

        <p class="text-caption text-grey mt-1">
          {{ variant === 'protected'
            ? 'Same model & prompt — routed through NeMo Guardrails, PII Scanner, LLM Guard, and Policy Engine before reaching the LLM.'
            : isDirectBrowser
              ? 'Same model & prompt — sent directly from your browser to the provider API. No proxy. Raw model response with zero protection.'
              : 'Same model & prompt — routed through proxy with all scanning disabled. Raw LLM response with no protection applied.'
          }}
        </p>
      </div>
    </div>

    <v-divider />

    <!-- Messages -->
    <div class="compare-panel__messages">
      <playground-chat-message-list
        :messages="messages"
        :is-streaming="isStreaming"
      />
    </div>

    <!-- Decision card (only for protected) -->
    <div v-if="variant === 'protected' && decision" class="compare-panel__decision">
      <v-divider />
      <compare-compare-decision-card :decision="decision" />
    </div>

    <!-- Direct panel: no-protection indicator when response received -->
    <div v-if="variant === 'direct' && messages.length > 1 && !isStreaming" class="compare-panel__decision">
      <v-divider />
      <v-alert
        type="warning"
        variant="tonal"
        density="compact"
        class="ma-2"
      >
        <template #title>No pipeline analysis</template>
        This response was not scanned. No intent detection, risk scoring, or policy enforcement was applied.
      </v-alert>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ChatMessage, PipelineDecision } from '~/types/api'

const props = defineProps<{
  variant: 'protected' | 'direct'
  messages: ChatMessage[]
  isStreaming: boolean
  decision?: PipelineDecision | null
  timing?: number | null
  endpointUrl?: string
  isDirectBrowser?: boolean
}>()

const apiBase = import.meta.env.NUXT_PUBLIC_API_BASE ?? 'http://localhost:8000'

const endpoint = computed(() => {
  if (props.endpointUrl) return props.endpointUrl
  return props.variant === 'protected'
    ? `${apiBase}/v1/chat/completions`
    : '/v1/chat/direct'
})

/** Base URL for the code snippet. */
const codeBaseUrl = computed(() => {
  if (props.variant === 'protected') {
    return `${apiBase}/v1`
  }
  const url = props.endpointUrl ?? ''
  const idx = url.indexOf('/v1/')
  return idx >= 0 ? `${url.slice(0, idx)}/v1` : url
})

const codeComment = computed(() =>
  props.variant === 'protected'
    ? '# ← protected by AI Protector'
    : '# ← your current, unprotected code',
)
</script>

<style lang="scss" scoped>
.compare-panel {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  border: 2px solid transparent;
  border-radius: 8px;
  overflow: hidden;

  &--protected {
    border-color: rgb(var(--v-theme-success));
  }
  &--direct {
    border-color: rgb(var(--v-theme-warning));
  }

  &__header {
    padding: 12px 16px;
    flex-shrink: 0;
    background: rgba(var(--v-theme-surface-variant), 0.3);
  }

  &__badge {
    display: flex;
    align-items: center;
  }

  &__endpoint {
    background: rgba(0, 0, 0, 0.08);
    border-radius: 4px;
    padding: 4px 8px;
  }

  &__url {
    font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.02em;
  }

  &__flow {
    line-height: 1.6;
  }

  &__messages {
    flex: 1;
    overflow-y: auto;
    min-height: 0;
  }

  &__decision {
    flex-shrink: 0;
  }
}

// Dark mode endpoint background
.v-theme--dark .compare-panel__endpoint {
  background: rgba(255, 255, 255, 0.06);
}

// Code snippet (IDE-like)
.code-snippet {
  &__header {
    display: flex;
    align-items: center;
    margin-bottom: 4px;
  }

  &__block {
    font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
    font-size: 0.72rem;
    line-height: 1.6;
    margin: 0;
    padding: 8px 12px;
    background: #1e1e2e;
    color: #cdd6f4;
    border-radius: 6px;
    overflow-x: auto;
    white-space: pre;
  }
}

// Syntax-highlight classes
.c-var { color: #89b4fa; }
.c-fn { color: #f9e2af; }
.c-key { color: #a6e3a1; }
.c-str { color: #a6e3a1; }
.c-comment { color: #6c7086; font-style: italic; }
</style>
