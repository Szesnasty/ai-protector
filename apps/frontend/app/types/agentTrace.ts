// ─── Agent Trace types (matches backend GET /agent/traces response) ───

export interface AgentTraceSummary {
  trace_id: string
  session_id: string
  timestamp: string
  user_role: string
  intent: string
  model: string
  total_duration_ms: number
  iterations_count: number
  tool_calls_count: number
  tool_calls_blocked: number
  tokens_in: number
  tokens_out: number
  has_errors: boolean
  limits_hit: string | null
}

export interface AgentTraceListResponse {
  items: AgentTraceSummary[]
  total: number
  limit: number
  offset: number
}

// ─── Iteration sub-structures ───

export interface PreToolDecision {
  tool: string
  decision: string
  reason: string | null
  checks?: Array<{ check: string; passed: boolean; detail: string | null }>
  risk_score?: number
}

export interface ToolExecution {
  tool: string
  args: Record<string, unknown>
  raw_result?: string
  duration_ms?: number
}

export interface PostToolDecision {
  tool: string
  decision: string
  pii_count?: number
  injection_score?: number
}

export interface LlmCallInfo {
  messages_count?: number
  tokens_in: number | null
  tokens_out: number | null
  duration_ms?: number
}

export interface IterationFirewallDecision {
  decision: string
  risk_score: number | null
  flags?: Record<string, unknown>
}

export interface TraceIteration {
  iteration: number
  tool_plan?: Array<{ tool: string; args: Record<string, unknown> }>
  pre_tool_decisions?: PreToolDecision[]
  tool_executions?: ToolExecution[]
  post_tool_decisions?: PostToolDecision[]
  sanitized_results?: Array<{ tool: string; sanitized_result: string }>
  llm_call?: LlmCallInfo
  firewall_decision?: IterationFirewallDecision
}

// ─── Full trace detail ───

export interface AgentTraceDetail {
  trace_id: string
  session_id: string
  request_id: string
  timestamp: string
  user_role: string
  policy: string
  model: string
  user_message: string
  intent: string
  intent_confidence: number
  iterations: TraceIteration[]
  final_response: string
  total_duration_ms: number
  node_timings: Record<string, number>
  counters: Record<string, number>
  limits_hit: string | null
  errors: string[]
}

/** Export bundle from GET /agent/traces/{id}/export */
export type AgentTraceExport = Record<string, unknown>

export interface AgentTraceFilters {
  session_id: string | null
  user_role: string | null
  has_blocks: boolean | null
  date_from: string | null
  date_to: string | null
}
