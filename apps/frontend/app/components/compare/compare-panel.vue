<template>
  <div class="compare-panel" :class="panelClasses">
    <!-- ═══ Verdict Header ═══ -->
    <div class="verdict-header" :class="headerClasses">
      <div class="d-flex align-center ga-2">
        <v-icon :icon="headerIcon" size="20" />
        <span class="text-subtitle-1 font-weight-bold">{{ headerTitle }}</span>
      </div>
      <p class="text-caption mt-1 mb-0 verdict-subtitle">{{ headerSubtitle }}</p>
      <v-chip
        v-if="timing !== null && timing !== undefined"
        size="x-small"
        variant="outlined"
        class="mt-1"
      >
        <v-icon start size="12">mdi-clock-outline</v-icon>
        {{ timing }}ms
      </v-chip>
    </div>

    <!-- ═══ Route summary (compact) ═══ -->
    <div class="route-summary">
      <div class="d-flex align-center flex-wrap ga-1">
        <template v-if="variant === 'protected'">
          <span class="text-caption text-medium-emphasis">OpenAI SDK</span>
          <v-icon size="12" color="grey">mdi-arrow-right</v-icon>
          <v-chip size="x-small" color="primary" variant="tonal" label>
            <v-icon start size="12">mdi-shield-check</v-icon>
            AI Protector
          </v-chip>
          <v-icon size="12" color="grey">mdi-arrow-right</v-icon>
          <span class="text-caption text-medium-emphasis">LLM</span>
        </template>
        <template v-else>
          <span class="text-caption text-medium-emphasis">OpenAI SDK</span>
          <v-icon size="12" color="grey">mdi-arrow-right</v-icon>
          <v-chip size="x-small" :color="isDanger ? 'error' : 'warning'" variant="tonal" label>
            <v-icon start size="12">{{ isDirectBrowser ? 'mdi-web' : 'mdi-shield-off' }}</v-icon>
            {{ isDirectBrowser ? 'Direct API' : 'No scanning' }}
          </v-chip>
          <v-icon size="12" color="grey">mdi-arrow-right</v-icon>
          <span class="text-caption text-medium-emphasis">LLM</span>
        </template>
      </div>
    </div>

    <v-divider />

    <!-- ═══ Messages ═══ -->
    <div class="compare-panel__messages">
      <playground-chat-message-list
        :messages="messages"
        :is-streaming="isStreaming"
      />
    </div>

    <!-- ═══ Outcome: Protected side ═══ -->
    <div v-if="props.decision" class="compare-panel__outcome">
      <v-divider />
      <compare-decision-card :decision="props.decision" />
    </div>

    <!-- ═══ Outcome: Direct side — DANGER (attack detected) ═══ -->
    <div v-if="variant === 'direct' && hasDirectResponse && isDanger" class="compare-panel__outcome compare-panel__outcome--unsafe">
      <v-divider />
      <div class="unsafe-outcome pa-3">
        <div class="d-flex align-center ga-2 mb-1">
          <v-icon icon="mdi-alert-circle" color="error" size="18" />
          <span class="text-caption font-weight-bold" style="color: rgb(var(--v-theme-error))">UNSAFE OUTPUT</span>
        </div>
        <p class="text-caption text-medium-emphasis mb-1">
          Model followed the malicious instruction without any guardrails.
        </p>
        <div class="d-flex flex-wrap ga-1">
          <v-chip size="x-small" variant="tonal" color="error" label>No scanning</v-chip>
          <v-chip size="x-small" variant="tonal" color="error" label>No policy enforcement</v-chip>
          <v-chip size="x-small" variant="tonal" color="error" label>Raw model output</v-chip>
        </div>
      </div>
    </div>

    <!-- ═══ Outcome: Direct side — NEUTRAL (safe prompt) ═══ -->
    <div v-if="variant === 'direct' && hasDirectResponse && !isDanger" class="compare-panel__outcome">
      <v-divider />
      <div class="neutral-outcome pa-3">
        <div class="d-flex align-center ga-2 mb-1">
          <v-icon icon="mdi-shield-off-outline" size="18" color="grey" />
          <span class="text-caption font-weight-bold text-medium-emphasis">Direct response</span>
        </div>
        <div class="d-flex flex-wrap ga-1">
          <v-chip size="x-small" variant="tonal" label>No scanning</v-chip>
          <v-chip size="x-small" variant="tonal" label>No policy enforcement</v-chip>
        </div>
      </div>
    </div>

    <!-- ═══ Integration details (collapsed) ═══ -->
    <div class="integration-toggle">
      <button class="integration-toggle__btn" @click="showIntegration = !showIntegration">
        <v-icon :icon="showIntegration ? 'mdi-chevron-up' : 'mdi-chevron-down'" size="14" />
        <span class="text-caption">{{ showIntegration ? 'Hide' : 'Show' }} integration details</span>
      </button>
      <div v-if="showIntegration" class="integration-details mt-2">
        <pre class="code-snippet__block"><span class="c-var">client</span> = <span class="c-fn">OpenAI</span>(
  <span class="c-key">api_key</span>=<span class="c-str">"sk-..."</span>,
  <span class="c-key">base_url</span>=<span class="c-str">"<span class="c-url">{{ codeBaseUrl }}</span>"</span>  <span class="c-comment">{{ codeComment }}</span>
)</pre>
        <div class="compare-panel__endpoint mt-2">
          <code class="compare-panel__url">
            <v-icon size="12" class="mr-1">mdi-arrow-right-bold</v-icon>
            POST <span class="compare-panel__url-highlight">{{ endpointBase }}</span>{{ endpointPath }}
          </code>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { ChatMessage, PipelineDecision } from '~/types/api'

const props = defineProps<{
  variant: 'protected' | 'direct'
  messages: ChatMessage[]
  isStreaming: boolean
  decision?: PipelineDecision | null
  timing?: number | null
  endpointUrl?: string
  isDirectBrowser?: boolean
  compareMode?: 'neutral' | 'attack'
}>()

const showIntegration = ref(false)

const apiBase = import.meta.env.NUXT_PUBLIC_API_BASE ?? 'http://localhost:8000'

/** True when the direct panel has at least one assistant message with content. */
const hasDirectResponse = computed(() =>
  props.messages.some(m => m.role === 'assistant' && m.content?.trim()),
)

/** True when direct side should show danger state (attack mode + model responded). */
const isDanger = computed(() =>
  props.variant === 'direct' && props.compareMode === 'attack' && hasDirectResponse.value,
)

// ── Dynamic classes ──
const panelClasses = computed(() => {
  if (props.variant === 'protected') return 'compare-panel--protected'
  return isDanger.value ? 'compare-panel--danger' : 'compare-panel--direct'
})

const headerClasses = computed(() => {
  if (props.variant === 'protected') return 'verdict-header--protected'
  return isDanger.value ? 'verdict-header--danger' : 'verdict-header--direct'
})

// ── Verdict header content ──
const headerIcon = computed(() =>
  props.variant === 'protected' ? 'mdi-shield-check' : 'mdi-shield-off',
)

const headerTitle = computed(() =>
  props.variant === 'protected' ? 'With AI Protector' : 'Without AI Protector',
)

const headerSubtitle = computed(() => {
  if (props.variant === 'protected') {
    if (props.decision?.decision === 'BLOCK') return 'Blocked before reaching the model'
    if (props.decision?.decision === 'MODIFY') return 'Prompt sanitized before forwarding'
    if (props.decision) return 'No threats detected'
    return 'Full security pipeline applied'
  }
  // Direct side
  if (isDanger.value) return 'Unsafe response returned by model'
  if (hasDirectResponse.value) return 'Direct model response'
  return 'Direct LLM call — no protection'
})

// ── Endpoint computations ──
const endpoint = computed(() => {
  if (props.endpointUrl) return props.endpointUrl
  return props.variant === 'protected'
    ? `${apiBase}/v1/chat/completions`
    : '/v1/chat/direct'
})

const endpointBase = computed(() => {
  const url = endpoint.value
  try {
    const u = new URL(url)
    return `${u.protocol}//${u.host}`
  } catch {
    return ''
  }
})

const endpointPath = computed(() => {
  const url = endpoint.value
  try {
    const u = new URL(url)
    return u.pathname
  } catch {
    return url
  }
})

const codeBaseUrl = computed(() => {
  if (props.variant === 'protected') return `${apiBase}/v1`
  const url = props.endpointUrl ?? ''
  const idx = url.indexOf('/v1/')
  return idx >= 0 ? `${url.slice(0, idx)}/v1` : url
})

const codeComment = computed(() =>
  props.variant === 'protected'
    ? '# ONE LINE CHANGE'
    : '# NO PROTECTION',
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

  &--protected { border-color: rgb(var(--v-theme-success)); }
  &--direct { border-color: rgba(var(--v-theme-warning), 0.6); }
  &--danger { border-color: rgb(var(--v-theme-error)); }

  &__messages {
    flex: 1;
    overflow-y: auto;
    min-height: 120px;
  }

  &__outcome {
    flex-shrink: 0;
  }

  &__endpoint {
    background: rgba(var(--v-theme-on-surface), 0.05);
    border-radius: 4px;
    padding: 4px 8px;
  }

  &__url {
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.02em;
  }

  &__url-highlight {
    color: #e879f9;
    font-weight: 700;
  }
}

/* ─── Verdict Header ─── */
.verdict-header {
  padding: 12px 16px 8px;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.06);

  &--protected {
    background: rgba(var(--v-theme-success), 0.06);
    color: rgb(var(--v-theme-success));
  }

  &--direct {
    background: rgba(var(--v-theme-warning), 0.06);
    color: rgb(var(--v-theme-warning));
  }

  &--danger {
    background: rgba(var(--v-theme-error), 0.06);
    color: rgb(var(--v-theme-error));
  }
}

.verdict-subtitle {
  opacity: 0.8;
}

/* ─── Route Summary ─── */
.route-summary {
  padding: 6px 16px;
  background: rgba(var(--v-theme-on-surface), 0.02);
}

/* ─── Unsafe outcome (direct side — attack mode) ─── */
.unsafe-outcome {
  background: rgba(var(--v-theme-error), 0.04);
  border-left: 3px solid rgb(var(--v-theme-error));
}

/* ─── Neutral outcome (direct side — benign mode) ─── */
.neutral-outcome {
  background: rgba(var(--v-theme-on-surface), 0.03);
  border-left: 3px solid rgba(var(--v-theme-on-surface), 0.15);
}

/* ─── Integration toggle ─── */
.integration-toggle {
  padding: 6px 16px 8px;
  border-top: 1px solid rgba(var(--v-theme-on-surface), 0.06);

  &__btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: none;
    border: none;
    cursor: pointer;
    color: rgba(var(--v-theme-primary), 0.8);
    padding: 0;

    &:hover { text-decoration: underline; }
  }
}

.integration-details {
  animation: fadeIn 0.15s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: translateY(0); }
}

/* ─── Code snippet ─── */
.code-snippet__block {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 0.8rem;
  line-height: 1.6;
  margin: 0;
  padding: 8px 12px;
  background: #1e1e2e;
  color: #e0e4f0;
  border-radius: 6px;
  overflow-x: auto;
  white-space: pre;
}

.c-var { color: #7dd3fc; font-weight: 600; }
.c-fn { color: #fde68a; font-weight: 600; }
.c-key { color: #86efac; }
.c-str { color: #86efac; }
.c-url { color: #f0abfc; font-weight: 700; text-decoration: underline; text-underline-offset: 2px; }
.c-comment { color: #9ca3af; font-style: italic; }
</style>
