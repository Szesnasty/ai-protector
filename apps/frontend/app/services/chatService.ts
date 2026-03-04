import { api } from './api'
import { detectProviderClient, getKey } from '~/composables/useApiKeys'
import type {
  ChatCompletionRequest,
  ChatCompletionResponse,
  PipelineDecision,
  ApiError,
} from '~/types/api'

// ─── Non-streaming ───

export const chatService = {
  sendMessage: (body: ChatCompletionRequest): Promise<ChatCompletionResponse> =>
    api.post<ChatCompletionResponse>('/v1/chat/completions', body)
      .then((r) => r.data),
}

// ─── Provider endpoints for direct browser → API calls ───

/**
 * Base URLs for providers that support direct browser calls
 * (CORS-enabled, OpenAI-compatible streaming format).
 *
 * The Compare Playground's right panel calls these directly from the
 * browser — completely bypassing the AI Protector proxy — to prove
 * the raw model accepts prompts that AI Protector would block.
 */
export const PROVIDER_API_BASES: Record<string, string> = {
  openai: 'https://api.openai.com',
  mistral: 'https://api.mistral.ai',
}

/** True if the provider supports direct browser → API calls. */
export function supportsDirectBrowserCall(provider: string): boolean {
  return provider in PROVIDER_API_BASES
}

// ─── Streaming (SSE via fetch) ───

export interface StreamCallbacks {
  onToken: (token: string) => void
  onDone: () => void
  onError: (error: Error) => void
}

export interface StreamOptions {
  body: ChatCompletionRequest
  headers?: Record<string, string>
  signal?: AbortSignal
  /** Custom endpoint path (default: /v1/chat/completions) */
  url?: string
}

export async function streamChat(
  options: StreamOptions,
  callbacks: StreamCallbacks,
): Promise<Response> {
  const baseURL = import.meta.env.NUXT_PUBLIC_API_BASE ?? 'http://localhost:8000'

  // Auto-inject x-api-key from browser storage if model requires an external provider
  const model = options.body.model ?? ''
  const apiKeyHeaders: Record<string, string> = {}
  if (model) {
    const provider = detectProviderClient(model)
    if (provider !== 'ollama') {
      const key = getKey(provider)
      if (key) {
        apiKeyHeaders['x-api-key'] = key
      }
    }
  }

  const endpoint = options.url ?? '/v1/chat/completions'
  const response = await fetch(`${baseURL}${endpoint}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-client-id': 'playground',
      ...apiKeyHeaders,
      ...options.headers,
    },
    body: JSON.stringify({ ...options.body, stream: true }),
    signal: options.signal,
  })

  if (!response.ok) {
    let errorBody: unknown
    try {
      errorBody = await response.json()
    } catch {
      errorBody = {
        error: {
          message: `Server error (${response.status} ${response.statusText})`,
          type: 'server_error',
          code: String(response.status),
        },
      }
    }
    throw errorBody
  }

  const reader = response.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''

    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed || !trimmed.startsWith('data: ')) continue

      const data = trimmed.slice(6)
      if (data === '[DONE]') {
        callbacks.onDone()
        return response
      }

      try {
        const chunk = JSON.parse(data)
        const content = chunk.choices?.[0]?.delta?.content
        if (content) {
          callbacks.onToken(content)
        }
      } catch {
        // Skip malformed chunks
      }
    }
  }

  callbacks.onDone()
  return response
}

/**
 * Stream a chat completion DIRECTLY to the LLM provider's API.
 * Browser → api.openai.com / api.mistral.ai — completely bypassing the proxy.
 *
 * This proves the raw model accepts prompts our proxy would block.
 * Supported: OpenAI, Mistral (CORS + OpenAI-compatible format).
 * Unsupported providers should use streamChat('/v1/chat/direct') as fallback.
 */
export async function streamChatDirect(
  options: {
    body: ChatCompletionRequest
    signal?: AbortSignal
  },
  callbacks: StreamCallbacks,
): Promise<Response> {
  const model = options.body.model ?? ''
  const provider = detectProviderClient(model)
  const base = PROVIDER_API_BASES[provider]
  const key = getKey(provider)

  if (!base) {
    throw {
      error: { message: `Direct browser → ${provider} not supported. Using proxy fallback.` },
    }
  }
  if (!key) {
    throw {
      error: { message: `No API key for "${provider}".` },
    }
  }

  const response = await fetch(`${base}/v1/chat/completions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${key}`,
    },
    body: JSON.stringify({ ...options.body, stream: true }),
    signal: options.signal,
  })

  if (!response.ok) {
    let errorBody: unknown
    try {
      errorBody = await response.json()
    } catch {
      errorBody = {
        error: {
          message: `${provider} error (${response.status} ${response.statusText})`,
        },
      }
    }
    throw errorBody
  }

  const reader = response.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''

    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed || !trimmed.startsWith('data: ')) continue

      const data = trimmed.slice(6)
      if (data === '[DONE]') {
        callbacks.onDone()
        return response
      }

      try {
        const chunk = JSON.parse(data)
        const content = chunk.choices?.[0]?.delta?.content
        if (content) {
          callbacks.onToken(content)
        }
      } catch {
        // Skip malformed chunks
      }
    }
  }

  callbacks.onDone()
  return response
}

// ─── Pipeline decision extraction ───

export function extractPipelineDecision(response: Response): PipelineDecision {
  return {
    decision: (response.headers.get('x-decision') ?? 'ALLOW') as PipelineDecision['decision'],
    intent: response.headers.get('x-intent') ?? 'unknown',
    riskScore: parseFloat(response.headers.get('x-risk-score') ?? '0'),
    riskFlags: {},
  }
}

export function extractBlockDecision(errorBody: ApiError): PipelineDecision {
  return {
    decision: 'BLOCK',
    intent: errorBody.intent ?? 'unknown',
    riskScore: errorBody.risk_score ?? 0,
    riskFlags: errorBody.risk_flags ?? {},
    blockedReason: errorBody.error.message,
  }
}
