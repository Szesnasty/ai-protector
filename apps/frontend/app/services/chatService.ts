import { api } from './api'
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
}

export async function streamChat(
  options: StreamOptions,
  callbacks: StreamCallbacks,
): Promise<Response> {
  const baseURL = import.meta.env.NUXT_PUBLIC_API_BASE ?? 'http://localhost:8000'

  const response = await fetch(`${baseURL}/v1/chat/completions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-client-id': 'playground',
      ...options.headers,
    },
    body: JSON.stringify({ ...options.body, stream: true }),
    signal: options.signal,
  })

  if (!response.ok) {
    const errorBody = await response.json()
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
