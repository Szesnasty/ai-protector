<template>
  <div
    class="chat-message"
    :class="[`chat-message--${message.role}`, { 'chat-message--verdict': isVerdict }]"
  >
    <v-avatar size="32" class="chat-message__avatar">
      <v-icon>{{ avatarIcon }}</v-icon>
    </v-avatar>

    <!-- ═══ VERDICT CARD ═══ -->
    <div
      v-if="isVerdict"
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

      <!-- 3 · SECURITY SUMMARY — compact secondary row -->
      <div class="verdict-card__meta">
        <div class="verdict-card__kv">
          <span class="verdict-card__label">Risk</span>
          <span class="text-caption font-weight-bold" :class="riskTextColor">{{ riskPercent }}%</span>
        </div>
        <v-progress-linear
          :model-value="decision!.riskScore * 100"
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
        <div v-if="decision!.intent" class="verdict-card__kv">
          <span class="verdict-card__label">Intent</span>
          <span class="text-caption">{{ decision!.intent }}</span>
        </div>
      </div>

      <!-- 4 · POLICY SIGNALS — chips in own labeled section -->
      <div v-if="topFlags.length" class="verdict-card__section">
        <span class="verdict-card__section-title">Matched signals</span>
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

      <!-- 5 · RESPONSE CONTENT — at the bottom, quietest -->
      <div v-if="cleanContent" class="verdict-card__body">
        <v-divider class="mb-4" />
        <div class="verdict-card__section-title mb-1">Final outcome</div>
        <!-- eslint-disable-next-line vue/no-v-html -- sanitized by DOMPurify -->
        <div class="text-body-2 chat-message__content verdict-card__response" v-html="renderedClean" />
      </div>
    </div>

    <!-- ═══ REGULAR BUBBLE ═══ -->
    <v-card
      v-else
      color="surface"
      variant="flat"
      class="chat-message__bubble"
    >
      <v-card-text class="text-body-1 chat-message__content">
        <!-- eslint-disable-next-line vue/no-v-html -- sanitized by DOMPurify -->
        <div v-html="renderedRaw" />
      </v-card-text>
    </v-card>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ChatMessage } from '~/types/api'
import {
  decisionColor as _dc,
  decisionIcon as _di,
  riskColor as _rc,
  riskTextColor as _rtc,
  flagColor as _fc,
  intentLabel as _il,
} from '~/utils/colors'
import { renderMarkdown } from '~/utils/markdown'

const props = defineProps<{ message: ChatMessage }>()

// ── core state ──
const decision = computed(() => props.message.decision ?? null)
const isVerdict = computed(() => !!decision.value && props.message.role === 'assistant')

// ── icons ──
const avatarIcon = computed(() => {
  if (isVerdict.value) return _di(decision.value?.decision)
  if (props.message.content?.startsWith('⛔')) return 'mdi-shield-alert'
  return props.message.role === 'user' ? 'mdi-account-circle' : 'mdi-robot'
})
const verdictIcon = computed(() => _di(decision.value?.decision))

// ── colors ──
const decisionColor = computed(() => _dc(decision.value?.decision))
const riskColor = computed(() => _rc(decision.value?.riskScore))
const riskTextColor = computed(() => _rtc(decision.value?.riskScore))
const riskPercent = computed(() => Math.round((decision.value?.riskScore ?? 0) * 100))

// ── verdict text ──
const verdictWord = computed(() => {
  switch (decision.value?.decision) {
    case 'BLOCK': return 'Blocked'
    case 'MODIFY': return 'Modified'
    case 'ALLOW': return 'Allowed'
    default: return 'Processed'
  }
})

const verdictReason = computed(() => {
  if (!decision.value) return ''
  if (decision.value.decision === 'ALLOW') return 'no threats detected'
  if (decision.value.decision === 'MODIFY') return 'response sanitized by pipeline'
  // BLOCK — best human reason for the headline (never show raw numbers)
  // 1. Intent label (most descriptive)
  const label = _il(decision.value.intent)
  if (label !== 'unknown') return label
  // 2. Blocked reason (only if truly specific, not generic/numeric)
  if (decision.value.blockedReason) {
    const br = decision.value.blockedReason
    const isGeneric = /^(request )?(blocked|denied)/i.test(br) || /^risk[\s:.]/i.test(br) || br.length < 12
    if (!isGeneric) {
      const first = (br.split(/[.!]/)[0] ?? '').trim()
      if (first.length > 0 && first.length < 60) return first.toLowerCase()
    }
  }
  // 3. Derive from top risk flag
  const flags = decision.value.riskFlags ? Object.keys(decision.value.riskFlags) : []
  if (flags.length && flags[0]) return flags[0].replace(/_/g, ' ')
  return 'unsafe content detected'
})

const humanReason = computed(() => {
  if (!decision.value) return ''
  if (decision.value.decision === 'BLOCK') {
    if (decision.value.blockedReason && !/^risk[\s:.]/i.test(decision.value.blockedReason)) {
      return decision.value.blockedReason
    }
    const label = _il(decision.value.intent)
    if (label !== 'unknown') return `This request was blocked because it matched a ${label} pattern.`
    return 'This request was blocked before reaching the model.'
  }
  if (decision.value.decision === 'MODIFY') {
    return 'The response was adjusted by the security pipeline before delivery.'
  }
  if (decision.value.decision === 'ALLOW') {
    return 'No security threats were detected. The request passed all pipeline checks.'
  }
  return ''
})

// ── flags (top 4 by score) ──
const topFlags = computed(() => {
  if (!decision.value?.riskFlags) return []
  return Object.entries(decision.value.riskFlags)
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
const renderedClean = computed(() => renderMarkdown(cleanContent.value))
const renderedRaw = computed(() => renderMarkdown(props.message.content ?? ''))
</script>

<style lang="scss" scoped>
/* ═══ Message wrapper ═══ */
.chat-message {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;

  &--user {
    flex-direction: row-reverse;

    .chat-message__bubble {
      background: rgba(var(--v-theme-primary), 0.08) !important;
    }
  }

  &--verdict {
    margin-bottom: 24px;
  }

  &__avatar {
    flex-shrink: 0;
  }

  &__bubble {
    max-width: 75%;
    border-radius: 12px !important;
    background: rgb(var(--v-theme-surface)) !important;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.2), 0 0 0 1px rgba(255, 255, 255, 0.06) !important;
  }

  &__content {
    :deep(p) {
      margin-bottom: 0.4em;
      &:last-child { margin-bottom: 0; }
    }

    :deep(strong), :deep(b) { font-weight: 700; }

    :deep(code) {
      font-family: 'JetBrains Mono', 'Fira Code', monospace;
      font-size: 0.85em;
      padding: 1px 5px;
      border-radius: 3px;
      background: rgba(var(--v-theme-on-surface), 0.1);
    }

    :deep(pre) {
      font-family: 'JetBrains Mono', 'Fira Code', monospace;
      font-size: 0.85em;
      padding: 8px 12px;
      border-radius: 6px;
      background: rgba(var(--v-theme-on-surface), 0.08);
      overflow-x: auto;
      margin: 0.5em 0;
      code { padding: 0; background: none; }
    }

    :deep(ul), :deep(ol) { padding-left: 1.4em; margin: 0.3em 0; }

    :deep(blockquote) {
      border-left: 3px solid rgba(var(--v-theme-primary), 0.4);
      margin: 0.4em 0;
      padding: 0.2em 0.8em;
      opacity: 0.85;
    }

    :deep(h1), :deep(h2), :deep(h3), :deep(h4) {
      margin: 0.5em 0 0.3em;
      font-size: 1em;
      font-weight: 700;
    }

    :deep(a) {
      color: rgb(var(--v-theme-primary));
      text-decoration: underline;
      text-underline-offset: 2px;
    }

    :deep(table) {
      border-collapse: collapse;
      margin: 0.5em 0;
      font-size: 0.9em;
    }

    :deep(th), :deep(td) {
      border: 1px solid rgba(var(--v-theme-on-surface), 0.15);
      padding: 4px 8px;
    }
  }
}

/* ═══ Verdict card ═══ */
.verdict-card {
  max-width: 92%;
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

  &__body {
    margin-top: 8px;
  }

  &__response {
    opacity: 0.8;
  }
}
</style>
