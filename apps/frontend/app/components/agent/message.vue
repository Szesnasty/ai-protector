<template>
  <div class="agent-message" :class="`agent-message--${message.role}`">
    <v-avatar size="32" class="agent-message__avatar">
      <v-icon>{{ avatarIcon }}</v-icon>
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

      <!-- ═══ VERDICT CARD ═══ -->
      <div
        v-else-if="isVerdict"
        class="verdict-card"
        :class="`verdict-card--${decision!.decision.toLowerCase()}`"
      >
        <!-- 1 · VERDICT — first and loudest -->
        <div class="verdict-card__header">
          <v-icon :color="decisionColor" size="28">{{ verdictIcon }}</v-icon>
          <div class="verdict-card__headline">
            <span class="verdict-card__word" :class="`text-${decisionColor}`">{{ verdictWord }}</span>
            <span class="verdict-card__dash text-medium-emphasis">—</span>
            <span class="verdict-card__short-reason text-medium-emphasis">{{ verdictReason }}</span>
          </div>
        </div>

        <!-- 2 · HUMAN-READABLE REASON -->
        <p v-if="humanReason" class="verdict-card__explain">
          {{ humanReason }}
        </p>

        <!-- 3 · AGENT ACTION CONTEXT — what the agent tried to do -->
        <div v-if="actionRows.length" class="verdict-card__action">
          <div v-for="row in actionRows" :key="row.label" class="verdict-card__action-row">
            <span class="verdict-card__label">{{ row.label }}</span>
            <span class="text-caption">{{ row.value }}</span>
          </div>
        </div>

        <!-- 4 · SECURITY SUMMARY — compact secondary row -->
        <div class="verdict-card__meta">
          <div v-if="trace?.user_role" class="verdict-card__kv">
            <span class="verdict-card__label">Role</span>
            <v-chip size="x-small" label variant="tonal">{{ trace.user_role }}</v-chip>
          </div>
          <div class="verdict-card__kv">
            <span class="verdict-card__label">Risk</span>
            <span class="text-caption font-weight-bold" :class="riskTextColor">{{ riskPercent }}%</span>
          </div>
          <v-progress-linear
            :model-value="decision!.risk_score * 100"
            :color="riskColor"
            height="3"
            rounded
            class="verdict-card__bar"
          />
          <div class="verdict-card__kv">
            <span class="verdict-card__label">Action</span>
            <v-chip :color="decisionColor" size="x-small" label variant="tonal">
              {{ decision!.decision }}
            </v-chip>
          </div>
        </div>

        <!-- 5 · POLICY SIGNALS — chips in own labeled section -->
        <div v-if="topFlags.length" class="verdict-card__section">
          <span class="verdict-card__section-title">Triggered controls</span>
          <div class="verdict-card__signals">
            <v-chip
              v-for="f in topFlags"
              :key="f.key"
              :color="flagChipColor(f.key, f.value)"
              size="x-small"
              label
              variant="outlined"
            >
              {{ f.key }}
            </v-chip>
          </div>
        </div>

        <!-- 6 · TOOL CALLS — expandable per-tool details -->
        <div v-if="message.tools_called?.length" class="verdict-card__section">
          <span class="verdict-card__section-title">Tool calls</span>
          <div class="verdict-card__tools">
            <agent-tool-call-chip
              v-for="(tc, idx) in message.tools_called"
              :key="idx"
              :tool="tc"
              :verdict="decision?.decision"
            />
          </div>
        </div>

        <!-- 7 · RESPONSE CONTENT — at the bottom, quietest -->
        <div v-if="cleanContent" class="verdict-card__body">
          <v-divider class="mb-4" />
          <div class="verdict-card__section-title mb-1">Final outcome</div>
          <div class="text-body-2 verdict-card__response">{{ cleanContent }}</div>
        </div>

        <!-- 8 · TRACE DETAILS — expandable at very bottom -->
        <div v-if="trace" class="verdict-card__trace-toggle">
          <v-btn
            variant="text"
            size="small"
            :prepend-icon="showTrace ? 'mdi-chevron-up' : 'mdi-chevron-down'"
            class="text-caption text-medium-emphasis pa-0"
            @click="showTrace = !showTrace"
          >
            Trace details
          </v-btn>
          <v-expand-transition>
            <div v-if="showTrace" class="verdict-card__trace">
              <div class="verdict-card__kv">
                <span class="verdict-card__label">Iterations</span>
                <span class="text-caption">{{ trace.iterations }}</span>
              </div>
              <div class="verdict-card__kv">
                <span class="verdict-card__label">Latency</span>
                <span class="text-caption">{{ trace.latency_ms }}ms</span>
              </div>
              <div v-if="trace.allowed_tools.length" class="verdict-card__kv">
                <span class="verdict-card__label">Role tool access</span>
                <span class="text-caption">{{ trace.allowed_tools.join(', ') }}</span>
              </div>
            </div>
          </v-expand-transition>
        </div>
      </div>

      <!-- ═══ REGULAR BUBBLE ═══ -->
      <v-card
        v-else
        :color="cardColor"
        variant="tonal"
        class="agent-message__bubble"
      >
        <v-card-text class="text-body-1">
          {{ message.content }}
        </v-card-text>
      </v-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { AgentMessage } from '~/types/agent'
import {
  decisionColor as _dc,
  decisionIcon as _di,
  riskColor as _rc,
  riskTextColor as _rtc,
  flagColor as _fc,
  intentLabel as _il,
} from '~/utils/colors'

const props = defineProps<{ message: AgentMessage }>()

// ── core state ──
const decision = computed(() => {
  const fd = props.message.firewall_decision
  if (!fd || fd.decision === 'UNKNOWN') return null
  return fd
})
const trace = computed(() => props.message.agent_trace ?? null)
const isBlocked = computed(() => props.message.content?.startsWith('⛔'))
const isError = computed(() => props.message.content.startsWith('⚠️'))
const isVerdict = computed(() => !!decision.value && props.message.role === 'assistant')
const showTrace = ref(false)

// ── icons ──
const avatarIcon = computed(() => {
  if (isVerdict.value) return _di(decision.value?.decision)
  if (isBlocked.value) return 'mdi-shield-alert'
  switch (props.message.role) {
    case 'user': return 'mdi-account-circle'
    case 'system': return 'mdi-information'
    default:
      if (isError.value) return 'mdi-alert-circle'
      return 'mdi-robot'
  }
})
const verdictIcon = computed(() => _di(decision.value?.decision))

// ── colors ──
const decisionColor = computed(() => _dc(decision.value?.decision))
const riskColor = computed(() => _rc(decision.value?.risk_score))
const riskTextColor = computed(() => _rtc(decision.value?.risk_score))
const riskPercent = computed(() => Math.round((decision.value?.risk_score ?? 0) * 100))

const cardColor = computed(() => {
  if (isBlocked.value) return 'surface-variant'
  if (isError.value) return 'error'
  return props.message.role === 'user' ? 'surface-variant' : 'primary'
})

// ── verdict text ──
const hasBlockedTools = computed(() =>
  props.message.tools_called?.some((tc) => !tc.allowed) ?? false,
)

const verdictWord = computed(() => {
  if (!decision.value) return 'Processed'
  if (decision.value.decision === 'BLOCK' && hasBlockedTools.value) return 'Tool Denied'
  switch (decision.value.decision) {
    case 'BLOCK': return 'Blocked'
    case 'MODIFY': return 'Modified'
    case 'ALLOW': return 'Allowed'
    default: return 'Processed'
  }
})

const verdictReason = computed(() => {
  if (!decision.value) return ''
  if (decision.value.decision === 'ALLOW') return 'role and tool checks passed'
  // BLOCK with denied tools — specific tool denial
  if (decision.value.decision === 'BLOCK' && hasBlockedTools.value) {
    const denied = props.message.tools_called?.filter((tc) => !tc.allowed) ?? []
    if (denied.length === 1) return `${denied[0].tool} access denied`
    return `${denied.length} tool calls denied`
  }
  // BLOCK — best human reason (intent → specific reason → role context → flags)
  const label = _il(decision.value.intent)
  if (label !== 'unknown') return label
  if (decision.value.blocked_reason) {
    const br = decision.value.blocked_reason
    const isGeneric = /^(request )?(blocked|denied)/i.test(br) || /^risk[\s:.]/i.test(br) || br.length < 12
    if (!isGeneric) {
      const first = (br.split(/[.!]/)[0] ?? '').trim()
      if (first.length > 0 && first.length < 60) return first.toLowerCase()
    }
  }
  if (trace.value?.user_role) {
    const tools = props.message.tools_called ?? []
    if (tools.length) return `${trace.value.user_role} role restricted from ${tools[0].tool}`
    return `${trace.value.user_role} role action blocked`
  }
  const flags = decision.value.risk_flags ? Object.keys(decision.value.risk_flags) : []
  if (flags.length) return flags[0].replace(/_/g, ' ')
  return 'security policy triggered'
})

const humanReason = computed(() => {
  if (!decision.value) return ''
  if (decision.value.decision === 'BLOCK') {
    // Use backend reason only if specific
    if (decision.value.blocked_reason) {
      const br = decision.value.blocked_reason
      const isGeneric = /^(request )?(blocked|denied)/i.test(br) || /^risk[\s:.]/i.test(br)
      if (!isGeneric) return br
    }
    if (hasBlockedTools.value && trace.value) {
      return `The ${trace.value.user_role} role does not have permission for the requested tool action.`
    }
    if (trace.value?.user_role) {
      const tools = props.message.tools_called ?? []
      if (tools.length) {
        return `The ${trace.value.user_role} role is not authorized to use ${tools.map((t) => t.tool).join(', ')} for this request.`
      }
      return `This action exceeded the ${trace.value.user_role} role's authorized scope.`
    }
    const label = _il(decision.value.intent)
    if (label !== 'unknown') return `This action was blocked because it matched a ${label} pattern.`
    return 'This action was blocked by the security pipeline.'
  }
  if (decision.value.decision === 'MODIFY') {
    return 'The agent response was adjusted by the security pipeline before delivery.'
  }
  if (decision.value.decision === 'ALLOW') {
    return 'The agent action passed all role, tool, and policy checks.'
  }
  return ''
})

// ── action summary rows ──
const actionRows = computed(() => {
  const rows: { label: string; value: string }[] = []
  const tools = props.message.tools_called ?? []

  if (tools.length === 1) {
    rows.push({ label: 'Attempted tool', value: tools[0].tool })
  } else if (tools.length > 1) {
    rows.push({ label: 'Tool chain', value: tools.map((t) => t.tool).join(' → ') })
  }

  if (decision.value?.decision === 'BLOCK' && hasBlockedTools.value) {
    rows.push({ label: 'Blocked at', value: 'permission check' })
  }

  return rows
})

// ── flags (top 4 by score) ──
const topFlags = computed(() => {
  if (!decision.value?.risk_flags) return []
  return Object.entries(decision.value.risk_flags)
    .sort(([, a], [, b]) => Number(b) - Number(a))
    .slice(0, 4)
    .map(([key, value]) => ({ key, value: Number(value) }))
})

function flagChipColor(key: string, value: number): string {
  return _fc(key, value)
}

// ── content ──
const cleanContent = computed(() => {
  const c = (props.message.content ?? '').replace(/^⛔\s*/, '').trim()
  return c || ''
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
    max-width: 92%;
  }

  &__bubble {
    max-width: 100%;
    border-radius: 12px !important;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25), 0 0 0 1px rgba(255, 255, 255, 0.12) !important;
  }
}

/* ═══ Verdict card ═══ */
.verdict-card {
  padding: 28px 28px 24px;
  border-radius: 14px;
  border-left: 4px solid transparent;
  background: rgb(var(--v-theme-surface));
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3), 0 0 0 1px rgba(255, 255, 255, 0.06);

  &--block {
    border-left-color: rgb(var(--v-theme-error));
    background: linear-gradient(135deg, rgba(var(--v-theme-error), 0.04) 0%, rgb(var(--v-theme-surface)) 50%);
  }

  &--allow {
    border-left-color: rgb(var(--v-theme-success));
    background: linear-gradient(135deg, rgba(var(--v-theme-success), 0.03) 0%, rgb(var(--v-theme-surface)) 50%);
  }

  &--modify {
    border-left-color: rgb(var(--v-theme-warning));
    background: linear-gradient(135deg, rgba(var(--v-theme-warning), 0.04) 0%, rgb(var(--v-theme-surface)) 50%);
  }

  &__header {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    margin-bottom: 16px;
  }

  &__headline {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 6px;
  }

  &__word {
    font-size: 1.35rem;
    font-weight: 800;
    letter-spacing: -0.01em;
    line-height: 1.2;
  }

  &__dash {
    font-size: 1.1rem;
    font-weight: 400;
  }

  &__short-reason {
    font-size: 0.95rem;
    font-weight: 400;
    line-height: 1.4;
  }

  &__explain {
    margin: 0 0 20px;
    padding-left: 40px;
    font-size: 0.875rem;
    line-height: 1.6;
    color: rgba(var(--v-theme-on-surface), 0.6);
  }

  &__action {
    margin: 0 0 20px;
    padding: 12px 16px;
    background: rgba(var(--v-theme-on-surface), 0.04);
    border-radius: 8px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  &__action-row {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  &__meta {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 16px;
    margin-bottom: 20px;
    padding: 10px 14px;
    background: rgba(var(--v-theme-on-surface), 0.04);
    border-radius: 8px;
  }

  &__kv {
    display: flex;
    align-items: center;
    gap: 6px;
    white-space: nowrap;
  }

  &__label {
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    opacity: 0.45;
    font-weight: 600;
  }

  &__bar {
    flex: 1;
    max-width: 120px;
  }

  &__section {
    margin-bottom: 20px;
  }

  &__section-title {
    display: block;
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    opacity: 0.4;
    font-weight: 600;
    margin-bottom: 8px;
  }

  &__signals {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }

  &__tools {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  &__body {
    margin-top: 8px;
  }

  &__response {
    opacity: 0.8;
  }

  &__trace-toggle {
    margin-top: 12px;
  }

  &__trace {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    padding: 10px 14px;
    margin-top: 6px;
    background: rgba(var(--v-theme-on-surface), 0.03);
    border-radius: 8px;
  }
}
</style>
