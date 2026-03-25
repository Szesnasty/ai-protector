<template>
  <div class="compare-panel" :class="panelClasses">
    <!-- ═══ Column Header — compact, one clear line ═══ -->
    <div class="column-header" :class="headerClasses">
      <div class="d-flex align-center ga-2">
        <v-icon :icon="headerIcon" size="20" />
        <span class="text-subtitle-2 font-weight-bold">{{ headerTitle }}</span>
        <v-spacer />
        <v-chip
          v-if="timing !== null && timing !== undefined"
          size="x-small"
          variant="outlined"
          class="column-header__timing"
        >
          {{ timing }}ms
        </v-chip>
      </div>
      <p class="text-caption mt-1 mb-0 column-header__subtitle">{{ headerSubtitle }}</p>
    </div>

    <!-- ═══ Messages (verdict card renders inside) ═══ -->
    <div class="compare-panel__messages">
      <playground-chat-message-list
        :messages="messages"
        :is-streaming="isStreaming"
      />
    </div>

    <!-- ═══ Direct side — DANGER footer (attack detected) ═══ -->
    <div v-if="variant === 'direct' && hasDirectResponse && isDanger" class="compare-panel__footer compare-panel__footer--danger">
      <div class="d-flex align-center ga-2">
        <v-icon icon="mdi-alert-circle" color="error" size="16" />
        <span class="text-caption font-weight-bold" style="color: rgb(var(--v-theme-error))">Unsafe output — no protection applied</span>
      </div>
    </div>

    <!-- ═══ Direct side — NEUTRAL footer (safe prompt) ═══ -->
    <div v-if="variant === 'direct' && hasDirectResponse && !isDanger" class="compare-panel__footer">
      <div class="d-flex align-center ga-2">
        <v-icon icon="mdi-shield-off-outline" size="16" color="grey" />
        <span class="text-caption text-medium-emphasis">Direct response — no scanning applied</span>
      </div>
    </div>

    <!-- ═══ Protected side — success footer (when blocked) ═══ -->
    <div v-if="variant === 'protected' && props.decision?.decision === 'BLOCK'" class="compare-panel__footer compare-panel__footer--success">
      <div class="d-flex align-center ga-2">
        <v-icon icon="mdi-shield-check" color="success" size="16" />
        <span class="text-caption font-weight-bold" style="color: rgb(var(--v-theme-success))">Protection succeeded — threat blocked</span>
      </div>
    </div>

    <!-- ═══ Integration details (collapsed) ═══ -->
    <div class="integration-toggle">
      <button class="integration-toggle__btn" @click="showIntegration = !showIntegration">
        <v-icon :icon="showIntegration ? 'mdi-chevron-up' : 'mdi-chevron-down'" size="14" />
        <span class="text-caption">{{ showIntegration ? 'Hide' : 'Show' }} integration details</span>
      </button>
      <v-expand-transition>
        <div v-if="showIntegration" class="integration-details mt-2">
          <!-- Route -->
          <div class="d-flex align-center flex-wrap ga-1 mb-2">
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
          <!-- Code snippet -->
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
      </v-expand-transition>
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
  if (props.variant === 'protected') return 'column-header--protected'
  return isDanger.value ? 'column-header--danger' : 'column-header--direct'
})

// ── Verdict header content ──
const headerIcon = computed(() =>
  props.variant === 'protected' ? 'mdi-shield-check' : 'mdi-shield-off',
)

const headerTitle = computed(() =>
  props.variant === 'protected' ? 'With AI Protector' : 'Without Protection',
)

const headerSubtitle = computed(() => {
  if (props.variant === 'protected') {
    if (props.decision?.decision === 'BLOCK') return 'Threat detected and blocked — model never saw the prompt'
    if (props.decision?.decision === 'MODIFY') return 'Prompt sanitized before forwarding to model'
    if (props.decision) return 'All checks passed — no threats detected'
    return 'Full security pipeline active'
  }
  // Direct side
  if (isDanger.value) return 'Model followed the malicious instruction — no guardrails'
  if (hasDirectResponse.value) return 'Direct response — no security scanning'
  return 'No protection pipeline — raw LLM access'
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

  &--protected { border-color: rgba(var(--v-theme-success), 0.5); }
  &--direct { border-color: rgba(var(--v-theme-on-surface), 0.12); }
  &--danger { border-color: rgb(var(--v-theme-error)); }

  &__messages {
    flex: 1;
    overflow-y: auto;
    min-height: 120px;
  }

  &__footer {
    flex-shrink: 0;
    padding: 8px 16px;
    border-top: 1px solid rgba(var(--v-theme-on-surface), 0.06);
    background: rgba(var(--v-theme-on-surface), 0.02);

    &--danger {
      background: rgba(var(--v-theme-error), 0.04);
      border-top-color: rgba(var(--v-theme-error), 0.15);
    }

    &--success {
      background: rgba(var(--v-theme-success), 0.04);
      border-top-color: rgba(var(--v-theme-success), 0.12);
    }
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

/* ─── Column Header ─── */
.column-header {
  padding: 12px 16px 10px;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.06);

  &--protected {
    background: rgba(var(--v-theme-success), 0.05);
    color: rgb(var(--v-theme-success));
  }

  &--direct {
    background: rgba(var(--v-theme-on-surface), 0.03);
    color: rgba(var(--v-theme-on-surface), 0.6);
  }

  &--danger {
    background: rgba(var(--v-theme-error), 0.05);
    color: rgb(var(--v-theme-error));
  }

  &__subtitle {
    opacity: 0.75;
    color: rgba(var(--v-theme-on-surface), 0.6);
  }

  &__timing {
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 10px !important;
  }
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
    color: rgba(var(--v-theme-on-surface), 0.5);
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
