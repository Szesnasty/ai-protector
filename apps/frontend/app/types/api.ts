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

// ─── Request Log ───
export interface RequestRead {
  id: string
  client_id: string
  policy_id: string
  policy_name: string
  intent: string | null
  prompt_preview: string | null
  decision: 'ALLOW' | 'MODIFY' | 'BLOCK'
  risk_score: number | null
  risk_flags: Record<string, unknown> | null
  latency_ms: number | null
  model_used: string | null
  tokens_in: number | null
  tokens_out: number | null
  blocked_reason: string | null
  response_masked: boolean | null
  created_at: string
}

export interface RequestDetail extends RequestRead {
  prompt_hash: string | null
  scanner_results: Record<string, unknown> | null
  output_filter_results: Record<string, unknown> | null
  node_timings: Record<string, number> | null
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface RequestFilters {
  decision: string | null
  policy_id: string | null
  intent: string | null
  risk_min: number | null
  risk_max: number | null
  search: string | null
  from: string | null
  to: string | null
}

// ─── Policy mutations ───
export interface PolicyCreate {
  name: string
  description?: string
  config?: Record<string, unknown>
  is_active?: boolean
}

export interface PolicyUpdate {
  name?: string
  description?: string
  config?: Record<string, unknown>
  is_active?: boolean
}

// ─── Analytics ───
export interface AnalyticsSummary {
  total_requests: number
  blocked: number
  modified: number
  allowed: number
  block_rate: number
  avg_risk: number
  avg_latency_ms: number
  top_intent: string | null
}

export interface TimelineBucket {
  time: string
  total: number
  blocked: number
  modified: number
  allowed: number
}

export interface PolicyStatsRow {
  policy_id: string
  policy_name: string
  total: number
  blocked: number
  modified: number
  allowed: number
  block_rate: number
  avg_risk: number
}

export interface RiskFlagCount {
  flag: string
  count: number
  pct: number
}

export interface IntentCount {
  intent: string
  count: number
  pct: number
}
