// ─── Health ───
export interface ServiceHealth {
  status: 'ok' | 'error'
  detail?: string
}

export interface HealthResponse {
  status: 'ok' | 'degraded'
  services: Record<string, ServiceHealth>
  version: string
}

// ─── Chat ───
export interface ChatMessage {
  role: 'system' | 'user' | 'assistant' | 'tool'
  content: string
  name?: string
}

export interface ChatCompletionRequest {
  model?: string
  messages: ChatMessage[]
  temperature?: number
  max_tokens?: number
  stream?: boolean
}

export interface ChatCompletionResponse {
  id: string
  object: string
  created: number
  model: string
  choices: Array<{
    index: number
    message: ChatMessage
    finish_reason: string | null
  }>
  usage: {
    prompt_tokens: number
    completion_tokens: number
    total_tokens: number
  } | null
}

// ─── Pipeline metadata ───
export interface PipelineDecision {
  decision: 'ALLOW' | 'MODIFY' | 'BLOCK'
  intent: string
  riskScore: number
  riskFlags: Record<string, unknown>
  blockedReason?: string
}

// ─── Policy ───
export interface Policy {
  id: string
  name: string
  level?: string
  description: string | null
  config: Record<string, unknown>
  is_active: boolean
  version: number
  created_at: string
  updated_at: string
}

// ─── API Error ───
export interface ApiError {
  error: {
    message: string
    type: string
    code: string
  }
  decision?: string
  risk_score?: number
  risk_flags?: Record<string, unknown>
  intent?: string
}
