# 10a — Chat Service & Composable

| | |
|---|---|
| **Parent** | [Step 10 — Playground](SPEC.md) |
| **Next sub-step** | [10b — Chat UI](10b-chat-ui.md) |
| **Estimated time** | 2–3 hours |

---

## Goal

Create the data layer for the Playground chat: an Axios-based `chatService` for non-streaming calls, a `fetch`-based SSE reader for streaming, a `policyService` for loading available policies, and a `useChat` composable that manages message state, streaming, and pipeline decision extraction.

> **Convention:** All code uses TypeScript. `.vue` files use `<script setup lang="ts">`.
> Component files use **kebab-case**. Styles use `<style lang="scss" scoped>`.

---

## Tasks

### 1. Chat service (`app/services/chatService.ts`)

- [x] **Non-streaming** call (fallback):
  ```typescript
  import { api } from './api'
  import type { ChatCompletionRequest, ChatCompletionResponse } from '~/types/api'

  export const chatService = {
    sendMessage: (body: ChatCompletionRequest): Promise<ChatCompletionResponse> =>
      api.post<ChatCompletionResponse>('/v1/chat/completions', body)
        .then((r) => r.data),
  }
  ```

- [x] **Streaming** function using `fetch` + `ReadableStream`:
  ```typescript
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
      throw errorBody  // Will be caught by useChat as ApiError / block response
    }

    // Read SSE stream
    const reader = response.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''  // Keep incomplete line in buffer

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed || !trimmed.startsWith('data: ')) continue

        const data = trimmed.slice(6)  // Remove "data: " prefix
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
  ```

### 2. Pipeline decision extraction

- [x] Helper to extract pipeline metadata from response headers:
  ```typescript
  import type { PipelineDecision } from '~/types/api'

  export function extractPipelineDecision(response: Response): PipelineDecision {
    return {
      decision: (response.headers.get('x-decision') ?? 'ALLOW') as PipelineDecision['decision'],
      intent: response.headers.get('x-intent') ?? 'unknown',
      riskScore: parseFloat(response.headers.get('x-risk-score') ?? '0'),
      riskFlags: {},  // Not in headers — populated from block body if applicable
    }
  }
  ```

- [x] For BLOCK responses (403), extract full details from JSON body:
  ```typescript
  export function extractBlockDecision(errorBody: ApiError): PipelineDecision {
    return {
      decision: 'BLOCK',
      intent: errorBody.intent ?? 'unknown',
      riskScore: errorBody.risk_score ?? 0,
      riskFlags: errorBody.risk_flags ?? {},
      blockedReason: errorBody.error.message,
    }
  }
  ```

### 3. Policy service (`app/services/policyService.ts`)

- [x] Fetch active policies for the selector dropdown:
  ```typescript
  import { api } from './api'
  import type { Policy } from '~/types/api'

  export const policyService = {
    listActive: (): Promise<Policy[]> =>
      api.get<Policy[]>('/v1/policies', { params: { active_only: true } })
        .then((r) => r.data),
  }
  ```

### 4. `usePolicies` composable (`app/composables/usePolicies.ts`)

- [x] Vue Query wrapper:
  ```typescript
  import { useQuery } from '@tanstack/vue-query'
  import { policyService } from '~/services/policyService'
  import type { Policy } from '~/types/api'

  export const usePolicies = () => {
    const { data: policies, isLoading, error } = useQuery<Policy[]>({
      queryKey: ['policies'],
      queryFn: policyService.listActive,
      staleTime: 60_000,  // policies change rarely
    })

    return { policies, isLoading, error }
  }
  ```

### 5. `useChat` composable (`app/composables/useChat.ts`)

- [x] Core state:
  ```typescript
  interface ChatState {
    messages: Ref<ChatMessage[]>
    isStreaming: Ref<boolean>
    lastDecision: Ref<PipelineDecision | null>
    error: Ref<string | null>
  }
  ```

- [x] `send(text: string)` function:
  1. Push `{ role: 'user', content: text }` to `messages`
  2. Push empty `{ role: 'assistant', content: '' }` (placeholder for streaming)
  3. Set `isStreaming = true`, `error = null`
  4. Call `streamChat()` with:
     - `onToken`: append to last assistant message content
     - `onDone`: set `isStreaming = false`
     - `onError`: set error, remove empty assistant message
  5. After response: extract `PipelineDecision` from headers → set `lastDecision`

- [x] `clear()` function — reset messages, lastDecision, error

- [x] `abort()` function — cancel in-flight stream via `AbortController`

- [x] Config refs:
  ```typescript
  const config = reactive({
    policy: 'balanced',
    model: 'llama3.1:8b',
    temperature: 0.7,
    maxTokens: null as number | null,
  })
  ```

- [x] Sends config as headers/body:
  - `x-policy` header from `config.policy`
  - `model`, `temperature`, `max_tokens` from config in request body

- [x] Handle BLOCK responses:
  - Catch 403 errors
  - Push a system-style message: `{ role: 'assistant', content: '⛔ Blocked: {reason}' }`
  - Set `lastDecision` with full block details (risk_flags, intent, etc.)

---

## Types (additions to `app/types/api.ts`)

- [x] If not already present, ensure these exist:
  ```typescript
  export interface PipelineDecision {
    decision: 'ALLOW' | 'MODIFY' | 'BLOCK'
    intent: string
    riskScore: number
    riskFlags: Record<string, unknown>
    blockedReason?: string
  }
  ```

---

## Definition of Done

- [x] `chatService.sendMessage()` calls proxy and returns typed `ChatCompletionResponse`
- [x] `streamChat()` reads SSE stream token-by-token, fires `onToken` per chunk
- [x] `streamChat()` correctly handles `data: [DONE]` sentinel
- [x] BLOCK responses (403) throw with full `ApiError` body
- [x] `extractPipelineDecision(response)` parses `x-decision`, `x-intent`, `x-risk-score` headers
- [x] `extractBlockDecision(errorBody)` extracts `risk_flags`, `intent`, `blocked_reason`
- [x] `usePolicies()` returns `{ policies, isLoading, error }` via Vue Query
- [x] `useChat()` returns `{ messages, isStreaming, lastDecision, error, config, send, clear, abort }`
- [x] Sending a message pushes user + assistant placeholder, streams tokens into assistant
- [x] BLOCK response adds blocked message and populates `lastDecision` with flags
- [x] `abort()` cancels in-flight stream without errors
- [x] All code is fully typed TypeScript (no `any`)
- [x] `npx nuxi typecheck` passes

---

| **Parent** | **Next** |
|---|---|
| [Step 10 — Playground](SPEC.md) | [10b — Chat UI](10b-chat-ui.md) |
