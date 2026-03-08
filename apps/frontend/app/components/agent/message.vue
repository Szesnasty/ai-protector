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

        <!-- Pipeline decision details (matching playground style) -->
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
              Risk {{ (decision.risk_score * 100).toFixed(0) }}%
            </span>
          </div>

          <v-progress-linear
            :model-value="decision.risk_score * 100"
            :color="riskColor"
            height="4"
            rounded
            class="mb-2"
          />

          <div v-if="hasFlags" class="d-flex flex-wrap ga-1 mb-1">
            <v-chip
              v-for="(score, flag) in decision.risk_flags"
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
            v-if="decision.decision === 'BLOCK' && decision.blocked_reason"
            type="error"
            density="compact"
            variant="tonal"
            class="mt-3 block-alert"
          >
            <div class="font-weight-bold text-body-2 mb-1">
              Blocked — {{ decisionLabel }}
            </div>
            <div class="text-caption">
              {{ decision.blocked_reason }}
            </div>
          </v-alert>
        </div>
      </v-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { AgentMessage } from '~/types/agent'
import { decisionColor as _dc, riskColor as _rc, riskTextColor as _rtc, flagColor as _fc, intentLabel as _il } from '~/utils/colors'

const props = defineProps<{
  message: AgentMessage
}>()

const decision = computed(() => {
  const fd = props.message.firewall_decision
  if (!fd || fd.decision === 'UNKNOWN') return null
  return fd
})

const isBlocked = computed(() => props.message.content?.startsWith('⛔'))
const isError = computed(() => props.message.content.startsWith('⚠️'))

const icon = computed(() => {
  if (isBlocked.value) return 'mdi-shield-alert'
  switch (props.message.role) {
    case 'user': return 'mdi-account-circle'
    case 'system': return 'mdi-information'
    default:
      if (isError.value) return 'mdi-alert-circle'
      return 'mdi-robot'
  }
})

const cardColor = computed(() => {
  if (isBlocked.value || isError.value) return 'error'
  return props.message.role === 'user' ? 'surface-variant' : 'primary'
})

const decisionColor = computed(() => _dc(decision.value?.decision))

const riskColor = computed(() => _rc(decision.value?.risk_score))

const riskTextColor = computed(() => _rtc(decision.value?.risk_score))

const hasFlags = computed(() =>
  decision.value?.risk_flags && Object.keys(decision.value.risk_flags).length > 0,
)

const decisionLabel = computed(() => _il(decision.value?.intent))

function flagColor(score: number): string {
  return _fc('', score)
}
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
    border-radius: 12px !important;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25), 0 0 0 1px rgba(255, 255, 255, 0.12) !important;
  }
}

.decision-details {
  font-size: 0.8rem;

  :deep(.v-chip) {
    font-size: 12px !important;
  }

  :deep(.v-alert__prepend .v-icon) {
    color: rgb(var(--v-theme-error)) !important;
  }

  .block-alert {
    border-left: 3px solid rgb(var(--v-theme-error));
  }
}
</style>
