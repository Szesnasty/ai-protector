/**
 * Composable for the Compare Playground.
 *
 * Fires the SAME prompt through two paths:
 *   1. Protected  — POST proxy/v1/chat/completions (full AI Protector pipeline)
 *   2. Unprotected — DIRECT to provider API (browser → api.openai.com etc.)
 *
 * The right panel proves the raw model accepts dangerous prompts.
 * The left panel proves AI Protector blocks them.  One-line URL change.
 *
 * For providers without browser CORS support (Anthropic, Google), the
 * right panel falls back to the proxy's /v1/chat/direct endpoint
 * (zero scanning passthrough).
 *
 * Requests run SEQUENTIALLY (protected first, then direct) to avoid
 * rate-limit issues with external providers.
 */
import { ref, reactive, computed } from 'vue'
import {
  streamChat,
  streamChatDirect,
  supportsDirectBrowserCall,
  getProviderApiBases,
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

  /** URL the direct panel actually hits (provider API or proxy fallback). */
  const directEndpointUrl = computed(() => {
    if (!config.model) return ''
    const p = detectProviderClient(config.model)
    const base = getProviderApiBases()[p]
    return base ? `${base}/v1/chat/completions` : '/v1/chat/direct'
  })

  /** True when the right panel calls the provider API directly from the browser. */
  const isDirectBrowser = computed(() => {
    if (!config.model) return false
    return supportsDirectBrowserCall(detectProviderClient(config.model))
  })

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
    if (provider !== 'ollama' && provider !== 'mock' && !getKey(provider)) {
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
            if (msg) {
              protectedMessages.value.splice(protIdx, 1, {
                ...msg,
                content: (msg.content ?? '') + token,
              })
            }
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
    // For OpenAI/Mistral: browser → provider API directly (true proof)
    // For others: browser → proxy /v1/chat/direct (zero scanning fallback)
    phase.value = 'direct'
    isDirectStreaming.value = true
    directAbort = new AbortController()

    const directStart = performance.now()
    const directProvider = detectProviderClient(config.model)
    const useDirectBrowser = supportsDirectBrowserCall(directProvider)

    const directCallbacks = {
      onToken: (token: string) => {
        const msg = directMessages.value[dirIdx]
        if (msg) {
          directMessages.value.splice(dirIdx, 1, {
            ...msg,
            content: (msg.content ?? '') + token,
          })
        }
      },
      onDone: () => {
        isDirectStreaming.value = false
        timings.direct = Math.round(performance.now() - directStart)
      },
      onError: (err: Error) => {
        isDirectStreaming.value = false
        timings.direct = Math.round(performance.now() - directStart)
      },
    }

    try {
      if (useDirectBrowser) {
        await streamChatDirect(
          { body, signal: directAbort.signal },
          directCallbacks,
        )
      } else {
        await streamChat(
          { body, url: '/v1/chat/direct', signal: directAbort.signal },
          directCallbacks,
        )
      }
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
    directEndpointUrl,
    isDirectBrowser,
    send,
    clear,
    abort,
  }
}
