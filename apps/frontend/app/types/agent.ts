// ─── Agent Demo types ───

export interface AgentChatRequest {
  message: string
  user_role: 'customer' | 'admin'
  session_id: string
  policy?: string
}

export interface ToolCall {
  tool: string
  args: Record<string, unknown>
  result_preview: string
  allowed: boolean
}

export interface AgentTrace {
  intent: string
  user_role: string
  allowed_tools: string[]
  iterations: number
  latency_ms: number
}

export interface FirewallDecision {
  decision: 'ALLOW' | 'MODIFY' | 'BLOCK' | 'UNKNOWN'
  risk_score: number
  intent: string
  risk_flags: Record<string, unknown>
  blocked_reason?: string | null
}

export interface AgentChatResponse {
  response: string
  session_id: string
  tools_called: ToolCall[]
  agent_trace: AgentTrace
  firewall_decision: FirewallDecision
}

export interface AgentMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  tools_called?: ToolCall[]
  agent_trace?: AgentTrace
  firewall_decision?: FirewallDecision
  timestamp: Date
}
