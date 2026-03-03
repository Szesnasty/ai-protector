<template>
  <div class="agent-message" :class="`agent-message--${message.role}`">
    <v-avatar size="32" class="agent-message__avatar">
      <v-icon>{{ icon }}</v-icon>
    </v-avatar>

    <div class="agent-message__content">
      <!-- System message -->
      <v-alert
        v-if="message.role === 'system'"
        type="info"
        density="compact"
        variant="tonal"
        class="text-body-2"
      >
        {{ message.content }}
      </v-alert>

      <!-- User / Assistant message -->
      <v-card
        v-else
        :color="cardColor"
        variant="tonal"
        class="agent-message__bubble"
      >
        <!-- Tool call chips (before response text) -->
        <div
          v-if="message.tools_called?.length"
          class="d-flex flex-wrap ga-2 px-4 pt-3"
        >
          <agent-tool-call-chip
            v-for="(tc, idx) in message.tools_called"
            :key="idx"
            :tool="tc"
          />
        </div>

        <v-card-text class="text-body-1">
          {{ message.content }}
        </v-card-text>

        <!-- Inline firewall decision -->
        <div
          v-if="message.firewall_decision && message.firewall_decision.decision !== 'UNKNOWN'"
          class="d-flex align-center ga-2 px-4 pb-3"
        >
          <v-chip :color="decisionColor" size="x-small" label>
            {{ message.firewall_decision.decision }}
          </v-chip>
          <span class="text-caption text-medium-emphasis">
            Risk {{ (message.firewall_decision.risk_score * 100).toFixed(0) }}%
          </span>
        </div>
      </v-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { AgentMessage } from '~/types/agent'

const props = defineProps<{
  message: AgentMessage
}>()

const isError = computed(() => props.message.content.startsWith('⚠️'))

const icon = computed(() => {
  switch (props.message.role) {
    case 'user': return 'mdi-account-circle'
    case 'system': return 'mdi-information'
    default:
      if (isError.value) return 'mdi-alert-circle'
      return 'mdi-robot'
  }
})

const cardColor = computed(() => {
  if (isError.value) return 'error'
  return props.message.role === 'user' ? 'surface-variant' : 'primary'
})

const decisionColor = computed(() => {
  switch (props.message.firewall_decision?.decision) {
    case 'ALLOW': return 'success'
    case 'MODIFY': return 'warning'
    case 'BLOCK': return 'error'
    default: return 'grey'
  }
})
</script>

<style lang="scss" scoped>
.agent-message {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;

  &--user {
    flex-direction: row-reverse;
  }

  &--system {
    justify-content: center;

    .agent-message__avatar {
      display: none;
    }

    .agent-message__content {
      max-width: 80%;
    }
  }

  &__avatar {
    flex-shrink: 0;
  }

  &__content {
    max-width: 75%;
  }

  &__bubble {
    max-width: 100%;
  }
}
</style>
