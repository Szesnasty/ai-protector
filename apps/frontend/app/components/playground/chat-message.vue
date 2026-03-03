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

      <!-- Pipeline decision details -->
      <div v-if="decision" class="decision-details px-4 pb-3">
        <v-divider class="mb-2" />

        <div class="d-flex align-center ga-2 mb-2">
          <v-chip
            :color="decisionColor"
            size="x-small"
            label
          >
            {{ decision.decision }}
          </v-chip>
          <span class="text-caption text-medium-emphasis">
            Intent: {{ decision.intent }}
          </span>
          <v-spacer />
          <span class="text-caption font-weight-medium" :class="riskTextColor">
            Risk {{ (decision.riskScore * 100).toFixed(0) }}%
          </span>
        </div>

        <v-progress-linear
          :model-value="decision.riskScore * 100"
          :color="riskColor"
          height="4"
          rounded
          class="mb-2"
        />

        <div v-if="hasFlags" class="d-flex flex-wrap ga-1 mb-1">
          <v-chip
            v-for="(score, flag) in decision.riskFlags"
            :key="String(flag)"
            :color="flagColor(Number(score))"
            size="x-small"
            label
            variant="outlined"
          >
            {{ flag }}: {{ Number(score).toFixed(2) }}
          </v-chip>
        </div>

        <v-alert
          v-if="decision.decision === 'BLOCK' && decision.blockedReason"
          type="error"
          density="compact"
          variant="tonal"
          class="mt-1"
        >
          {{ decision.blockedReason }}
        </v-alert>
      </div>
    </v-card>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ChatMessage } from '~/types/api'

const props = defineProps<{
  message: ChatMessage
}>()

const decision = computed(() => props.message.decision ?? null)
const isBlocked = computed(() => props.message.content?.startsWith('⛔'))

const icon = computed(() => {
  if (isBlocked.value) return 'mdi-shield-alert'
  return props.message.role === 'user' ? 'mdi-account-circle' : 'mdi-robot'
})

const cardColor = computed(() => {
  if (isBlocked.value) return 'error'
  return props.message.role === 'user' ? 'surface-variant' : 'primary'
})

const decisionColor = computed(() => {
  switch (decision.value?.decision) {
    case 'ALLOW': return 'success'
    case 'MODIFY': return 'warning'
    case 'BLOCK': return 'error'
    default: return 'grey'
  }
})

const riskColor = computed(() => {
  const score = decision.value?.riskScore ?? 0
  if (score >= 0.7) return 'error'
  if (score >= 0.3) return 'warning'
  return 'success'
})

const riskTextColor = computed(() => {
  const score = decision.value?.riskScore ?? 0
  if (score >= 0.7) return 'text-error'
  if (score >= 0.3) return 'text-warning'
  return 'text-success'
})

const hasFlags = computed(() =>
  decision.value?.riskFlags && Object.keys(decision.value.riskFlags).length > 0,
)

function flagColor(score: number): string {
  if (score >= 0.7) return 'error'
  if (score >= 0.3) return 'warning'
  return 'grey'
}
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

.decision-details {
  font-size: 0.8rem;
}
</style>
