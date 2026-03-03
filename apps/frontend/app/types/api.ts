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
  decision?: PipelineDecision
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

// ─── Rules ───
export type RuleAction = 'block' | 'flag' | 'score_boost'
export type RuleSeverity = 'low' | 'medium' | 'high' | 'critical'

export interface Rule {
  id: string
  policy_id: string
  phrase: string
  category: string
  is_regex: boolean
  action: RuleAction
  severity: RuleSeverity
  description: string
  created_at: string
  updated_at: string
}

export interface RuleCreate {
  phrase: string
  category?: string
  is_regex?: boolean
  action?: RuleAction
  severity?: RuleSeverity
  description?: string
}

export interface RuleUpdate {
  phrase?: string
  category?: string
  is_regex?: boolean
  action?: RuleAction
  severity?: RuleSeverity
  description?: string
}

export interface RuleTestResult {
  matched: boolean
  phrase: string
  category: string
  action: string
  severity: string
  is_regex: boolean
  description: string
  match_details: string | null
}
