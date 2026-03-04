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

      <!-- Endpoint URL — must be visible to user -->
      <div class="compare-panel__endpoint mt-2">
        <code class="compare-panel__url">
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
            <v-icon start size="12">mdi-shield-off</v-icon>
            No protection
          </v-chip>
          <v-icon size="14" color="grey">mdi-arrow-right</v-icon>
          <v-chip size="x-small" color="blue-grey" variant="tonal" label>LLM</v-chip>
        </div>

        <p class="text-caption text-grey mt-1">
          {{ variant === 'protected'
            ? 'Same model & prompt — routed through NeMo Guardrails, PII Scanner, LLM Guard, and Policy Engine before reaching the LLM.'
            : 'Same model & prompt — sent directly to the LLM with zero scanning or protection.'
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
}>()

const endpoint = computed(() =>
  props.variant === 'protected'
    ? '/v1/chat/completions'
    : '/v1/chat/direct',
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
</style>
