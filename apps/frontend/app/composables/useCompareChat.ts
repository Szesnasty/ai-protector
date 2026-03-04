/**
 * Composable for the Compare Playground.
 *
 * Fires the SAME prompt to:
 *   1. Protected  — POST /v1/chat/completions (full AI Protector pipeline)
 *   2. Unprotected — POST /v1/chat/direct     (raw passthrough, zero scanning)
 *
 * Requests run SEQUENTIALLY (protected first, then direct) to avoid
 * doubling inference load on a single GPU / external rate-limit.
 *
 * Compare only works with EXTERNAL providers that require an API key
 * (OpenAI, Anthropic, Google, Mistral).  Ollama is excluded because
 * both sides would hit the same local model serially — pointless and
 * CPU-crushing.
 */
import { ref, reactive, computed } from 'vue'
import {
  streamChat,
  extractPipelineDecision,
  extractBlockDecision,
} from '~/services/chatService'
import { detectProviderClient, getKey } from '~/composables/useApiKeys'
import type { ChatMessage, PipelineDecision, ApiError } from '~/types/api'

export interface CompareTimings {
  protected: number | null // ms
  direct: number | null // ms
}

/** Which phase is currently running. */
export type ComparePhase = 'idle' | 'protected' | 'direct'

export function useCompareChat() {
  // ── Protected panel (left) ──
  const protectedMessages = ref<ChatMessage[]>([])
  const isProtectedStreaming = ref(false)
  const protectedDecision = ref<PipelineDecision | null>(null)

  // ── Direct panel (right) ──
  const directMessages = ref<ChatMessage[]>([])
  const isDirectStreaming = ref(false)

  // ── Shared ──
  const timings = reactive<CompareTimings>({ protected: null, direct: null })
  const error = ref<string | null>(null)
  const phase = ref<ComparePhase>('idle')

  let protectedAbort: AbortController | null = null
  let directAbort: AbortController | null = null

  const config = reactive({
    policy: 'balanced',
    model: '',          // set by compare.vue once models load
    temperature: 0.7,
    maxTokens: null as number | null,
  })

  const isBusy = computed(() => phase.value !== 'idle')

  // ────────────────────────────────────────────────────────────────
  // Sequential send: Protected → then → Direct
  // ────────────────────────────────────────────────────────────────
  async function send(text: string) {
    if (!config.model) {
      error.value = 'Select a model and add its API key in Settings first.'
      return
    }

    // Verify API key exists for the selected model's provider
    const provider = detectProviderClient(config.model)
    if (provider !== 'ollama' && !getKey(provider)) {
      error.value = `No API key for provider "${provider}". Add one in Settings → API Keys.`
      return
    }

    // Push user message to both panels
    const userMsg: ChatMessage = { role: 'user', content: text }
    protectedMessages.value.push({ ...userMsg })
    directMessages.value.push({ ...userMsg })

    // Push empty assistant placeholders
    protectedMessages.value.push({ role: 'assistant', content: '' })
    directMessages.value.push({ role: 'assistant', content: '' })

    const protIdx = protectedMessages.value.length - 1
    const dirIdx = directMessages.value.length - 1

    error.value = null
    protectedDecision.value = null
    timings.protected = null
    timings.direct = null

    const chatHistory = protectedMessages.value.slice(0, -1).map(m => ({
      role: m.role,
      content: m.content,
    }))

    const body = {
      model: config.model,
      messages: chatHistory,
      temperature: config.temperature,
      max_tokens: config.maxTokens ?? undefined,
      stream: true as const,
    }

    // ── Phase 1: Protected ──────────────────────────────────────
    phase.value = 'protected'
    isProtectedStreaming.value = true
    protectedAbort = new AbortController()

    const protectedStart = performance.now()
    try {
      const response = await streamChat(
        {
          body,
          url: '/v1/chat/completions',
          headers: { 'x-policy': config.policy },
          signal: protectedAbort.signal,
        },
        {
          onToken: (token: string) => {
            const msg = protectedMessages.value[protIdx]
            if (msg) msg.content = (msg.content ?? '') + token
          },
          onDone: () => {
            isProtectedStreaming.value = false
            timings.protected = Math.round(performance.now() - protectedStart)
          },
          onError: (err: Error) => {
            isProtectedStreaming.value = false
            timings.protected = Math.round(performance.now() - protectedStart)
            error.value = err.message
          },
        },
      )
      protectedDecision.value = extractPipelineDecision(response)
      if (protectedDecision.value && protectedMessages.value[protIdx]) {
        protectedMessages.value[protIdx].decision = protectedDecision.value
      }
    } catch (err: unknown) {
      isProtectedStreaming.value = false
      timings.protected = Math.round(performance.now() - protectedStart)

      if (err instanceof DOMException && err.name === 'AbortError') {
        phase.value = 'idle'
        return
      }

      const apiErr = err as ApiError
      const errMsg = apiErr?.error?.message
        ?? (err instanceof Error ? err.message : String(err))

      if (apiErr?.error?.message) {
        protectedDecision.value = extractBlockDecision(apiErr)
      }

      protectedMessages.value[protIdx] = {
        role: 'assistant',
        content: `⛔ ${errMsg}`,
        decision: protectedDecision.value ?? undefined,
      }
      error.value = `Protected: ${errMsg}`
    }

    // ── Phase 2: Direct (unprotected) ───────────────────────────
    phase.value = 'direct'
    isDirectStreaming.value = true
    directAbort = new AbortController()

    const directStart = performance.now()
    try {
      await streamChat(
        {
          body,
          url: '/v1/chat/direct',
          signal: directAbort.signal,
        },
        {
          onToken: (token: string) => {
            const msg = directMessages.value[dirIdx]
            if (msg) msg.content = (msg.content ?? '') + token
          },
          onDone: () => {
            isDirectStreaming.value = false
            timings.direct = Math.round(performance.now() - directStart)
          },
          onError: (err: Error) => {
            isDirectStreaming.value = false
            timings.direct = Math.round(performance.now() - directStart)
          },
        },
      )
    } catch (err: unknown) {
      isDirectStreaming.value = false
      timings.direct = Math.round(performance.now() - directStart)

      if (err instanceof DOMException && err.name === 'AbortError') {
        phase.value = 'idle'
        return
      }

      const apiErr = err as ApiError
      const errMsg = apiErr?.error?.message
        ?? (err instanceof Error ? err.message : String(err))

      directMessages.value[dirIdx] = {
        role: 'assistant',
        content: `⚠️ ${errMsg}`,
      }
      if (!error.value) error.value = `Direct: ${errMsg}`
    }

    phase.value = 'idle'
  }

  function clear() {
    protectedMessages.value = []
    directMessages.value = []
    protectedDecision.value = null
    timings.protected = null
    timings.direct = null
    error.value = null
  }

  function abort() {
    protectedAbort?.abort()
    directAbort?.abort()
    isProtectedStreaming.value = false
    isDirectStreaming.value = false
    phase.value = 'idle'
  }

  return {
    protectedMessages,
    directMessages,
    isProtectedStreaming,
    isDirectStreaming,
    protectedDecision,
    timings,
    error,
    config,
    phase,
    isBusy,
    send,
    clear,
    abort,
  }
}
