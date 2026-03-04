/**
 * Composable for the Compare Playground — fires the same prompt
 * to both the Protected (proxy pipeline) and Unprotected (direct) endpoints.
 */
import { ref, reactive } from 'vue'
import {
  streamChat,
  extractPipelineDecision,
  extractBlockDecision,
} from '~/services/chatService'
import type { ChatMessage, PipelineDecision, ApiError } from '~/types/api'

export interface CompareTimings {
  protected: number | null // ms
  direct: number | null // ms
}

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

  let protectedAbort: AbortController | null = null
  let directAbort: AbortController | null = null

  const config = reactive({
    policy: 'balanced',
    model: 'llama3.1:8b',
    temperature: 0.7,
    maxTokens: null as number | null,
  })

  async function send(text: string) {
    // Push user message to both panels
    const userMsg: ChatMessage = { role: 'user', content: text }
    protectedMessages.value.push({ ...userMsg })
    directMessages.value.push({ ...userMsg })

    // Push empty assistant placeholders
    protectedMessages.value.push({ role: 'assistant', content: '' })
    directMessages.value.push({ role: 'assistant', content: '' })

    const protIdx = protectedMessages.value.length - 1
    const dirIdx = directMessages.value.length - 1

    isProtectedStreaming.value = true
    isDirectStreaming.value = true
    error.value = null
    protectedDecision.value = null
    timings.protected = null
    timings.direct = null

    protectedAbort = new AbortController()
    directAbort = new AbortController()

    const body = {
      model: config.model,
      messages: protectedMessages.value.slice(0, -1).map(m => ({
        role: m.role,
        content: m.content,
      })),
      temperature: config.temperature,
      max_tokens: config.maxTokens ?? undefined,
      stream: true as const,
    }

    // ── Fire both requests simultaneously ──
    const protectedStart = performance.now()
    const directStart = performance.now()

    const protectedPromise = (async () => {
      try {
        const response = await streamChat(
          {
            body,
            url: '/v1/chat/completions',
            headers: { 'x-policy': config.policy },
            signal: protectedAbort!.signal,
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

        if (err instanceof DOMException && err.name === 'AbortError') return

        const apiErr = err as ApiError
        if (apiErr?.error?.message) {
          protectedDecision.value = extractBlockDecision(apiErr)
          protectedMessages.value[protIdx] = {
            role: 'assistant',
            content: `⛔ Blocked: ${apiErr.error.message}`,
            decision: protectedDecision.value ?? undefined,
          }
        } else {
          if (!protectedMessages.value[protIdx]?.content) {
            protectedMessages.value.splice(protIdx, 1)
          }
        }
      }
    })()

    const directPromise = (async () => {
      try {
        await streamChat(
          {
            body,
            url: '/v1/chat/direct',
            signal: directAbort!.signal,
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

        if (err instanceof DOMException && err.name === 'AbortError') return

        const apiErr = err as ApiError
        if (apiErr?.error?.message) {
          directMessages.value[dirIdx] = {
            role: 'assistant',
            content: `⚠️ Error: ${apiErr.error.message}`,
          }
        } else {
          if (!directMessages.value[dirIdx]?.content) {
            directMessages.value.splice(dirIdx, 1)
          }
        }
      }
    })()

    await Promise.allSettled([protectedPromise, directPromise])
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
    send,
    clear,
    abort,
  }
}
