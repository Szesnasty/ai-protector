// ─── Enums ───

export type AgentFramework = 'langgraph' | 'raw_python' | 'proxy_only'
export type AgentEnvironment = 'dev' | 'staging' | 'production'
export type RiskLevel = 'low' | 'medium' | 'high' | 'critical'
export type ProtectionLevel = 'proxy_only' | 'agent_runtime' | 'full'
export type RolloutMode = 'observe' | 'warn' | 'enforce'
export type AgentStatus = 'draft' | 'active' | 'archived'
export type AccessType = 'read' | 'write'
export type Sensitivity = 'low' | 'medium' | 'high' | 'critical'
export type GateDecisionType = 'rbac' | 'injection' | 'pii' | 'budget'
export type GateAction = 'ALLOW' | 'DENY' | 'BLOCK' | 'REDACT' | 'WARN'
export type TraceGate = 'pre_tool' | 'post_tool' | 'pre_llm' | 'post_llm'
export type TraceDecision = 'ALLOW' | 'DENY' | 'REDACT' | 'WARN'
export type IncidentSeverity = 'low' | 'medium' | 'high' | 'critical'
export type IncidentCategory = 'rbac' | 'injection' | 'pii' | 'budget' | 'policy'
export type IncidentStatus = 'open' | 'acknowledged' | 'resolved' | 'false_positive'

// ─── Agent ───

export interface AgentCreate {
  name: string
  description?: string
  team?: string | null
  framework?: AgentFramework
  environment?: AgentEnvironment
  is_public_facing?: boolean
  has_tools?: boolean
  has_write_actions?: boolean
  touches_pii?: boolean
  handles_secrets?: boolean
  calls_external_apis?: boolean
  policy_pack?: string | null
}

export interface AgentUpdate {
  name?: string
  description?: string
  team?: string | null
  framework?: AgentFramework
  environment?: AgentEnvironment
  is_public_facing?: boolean
  has_tools?: boolean
  has_write_actions?: boolean
  touches_pii?: boolean
  handles_secrets?: boolean
  calls_external_apis?: boolean
  status?: AgentStatus
  policy_pack?: string | null
}

export interface AgentRead {
  id: string
  name: string
  description: string
  team: string | null
  framework: AgentFramework
  environment: AgentEnvironment
  is_public_facing: boolean
  has_tools: boolean
  has_write_actions: boolean
  touches_pii: boolean
  handles_secrets: boolean
  calls_external_apis: boolean
  risk_level: RiskLevel | null
  protection_level: ProtectionLevel | null
  policy_pack: string | null
  rollout_mode: RolloutMode
  status: AgentStatus
  is_reference: boolean
  generated_config: Record<string, unknown> | null
  generated_kit: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface AgentListResponse {
  items: AgentRead[]
  total: number
  page: number
  per_page: number
}

// ─── Tool ───

export interface ToolCreate {
  name: string
  description?: string
  category?: string | null
  access_type?: AccessType
  sensitivity?: Sensitivity
  arg_schema?: Record<string, unknown> | null
  returns_pii?: boolean
  returns_secrets?: boolean
  rate_limit?: number | null
}

export interface ToolUpdate {
  name?: string
  description?: string
  category?: string | null
  access_type?: AccessType
  sensitivity?: Sensitivity
  arg_schema?: Record<string, unknown> | null
  returns_pii?: boolean
  returns_secrets?: boolean
  rate_limit?: number | null
}

export interface ToolRead {
  id: string
  agent_id: string
  name: string
  description: string
  category: string | null
  access_type: AccessType
  sensitivity: Sensitivity
  requires_confirmation: boolean
  arg_schema: Record<string, unknown> | null
  returns_pii: boolean
  returns_secrets: boolean
  rate_limit: number | null
  created_at: string
  updated_at: string
}

// ─── Role ───

export interface RoleCreate {
  name: string
  description?: string
  inherits_from?: string | null
}

export interface RoleUpdate {
  name?: string
  description?: string
  inherits_from?: string | null
}

export interface PermissionEntry {
  tool_id: string
  scopes?: string[]
  requires_confirmation_override?: boolean | null
  conditions?: Record<string, unknown> | null
}

export interface PermissionRead {
  id: string
  tool_id: string
  tool_name: string | null
  scopes: string[]
  requires_confirmation_override: boolean | null
  conditions: Record<string, unknown> | null
}

export interface RoleRead {
  id: string
  agent_id: string
  name: string
  description: string
  inherits_from: string | null
  permissions: PermissionRead[]
  inherited_permissions: PermissionRead[]
  created_at: string
}

export interface PermissionBatchSet {
  permissions: PermissionEntry[]
}

export interface PermissionMatrixResponse {
  tools: string[]
  roles: string[]
  matrix: Record<string, Record<string, string>>
}

export interface PermissionCheckResponse {
  allowed: boolean
  decision: string
  reason: string
}

// ─── Config ───

export interface GeneratedConfig {
  rbac_yaml: string
  limits_yaml: string
  policy_yaml: string
  generated_at: string
}

export interface PolicyPack {
  name: string
  description: string
  risk_levels: string[]
  [key: string]: unknown
}

// ─── Integration Kit ───

export interface IntegrationKit {
  files: Record<string, string>
  [key: string]: unknown
}

// ─── Validation ───

export interface ValidationResult {
  category: string
  name: string
  passed: boolean
  message: string
  recommendation?: string
}

export interface ValidationResponse {
  agent_id: string
  total: number
  passed: number
  failed: number
  score: number
  results: ValidationResult[]
  created_at: string
}

export interface ValidationRunRead {
  id: string
  agent_id: string
  pack: string
  total: number
  passed: number
  failed: number
  score: number
  results: ValidationResult[]
  created_at: string
}

// ─── Rollout ───

export interface RolloutPromoteRequest {
  mode: RolloutMode
}

export interface RolloutPromoteResponse {
  id: string
  name: string
  rollout_mode: RolloutMode
  previous_mode: RolloutMode
}

export interface PromotionEventRead {
  id: string
  agent_id: string
  from_mode: RolloutMode
  to_mode: RolloutMode
  user: string
  created_at: string
}

export interface ReadinessStats {
  traces_in_current_mode: number
  would_have_blocked: number
  false_positive_rate: number | null
  latest_validation: Record<string, unknown> | null
}

export interface ReadinessResponse {
  current_mode: RolloutMode
  can_promote_to: RolloutMode[]
  blockers: string[]
  stats: ReadinessStats
}

// ─── Gate Decision ───

export interface GateEvalRequest {
  gate_type: GateDecisionType
  context?: Record<string, unknown> | null
}

export interface GateEvalResponse {
  decision: GateAction
  effective_action: GateAction
  rollout_mode: RolloutMode
  enforced: boolean
  warning: string | null
}

export interface GateDecisionRead {
  id: string
  agent_id: string
  gate_type: GateDecisionType
  decision: GateAction
  effective_action: GateAction
  rollout_mode: RolloutMode
  enforced: boolean
  warning: string | null
  context: Record<string, unknown> | null
  created_at: string
}

// ─── Traces ───

export interface TraceCreate {
  session_id?: string
  gate: TraceGate
  tool_name?: string | null
  role?: string | null
  decision: TraceDecision
  reason?: string
  category?: string
  rollout_mode?: RolloutMode
  enforced?: boolean
  latency_ms?: number
  details?: Record<string, unknown> | null
}

export interface TraceRead {
  id: string
  agent_id: string
  session_id: string
  timestamp: string
  gate: TraceGate
  tool_name: string | null
  role: string | null
  decision: TraceDecision
  reason: string
  category: string
  rollout_mode: RolloutMode
  enforced: boolean
  latency_ms: number
  details: Record<string, unknown> | null
  incident_id: string | null
}

export interface TraceListResponse {
  items: TraceRead[]
  total: number
  page: number
  per_page: number
}

// ─── Incidents ───

export interface IncidentRead {
  id: string
  agent_id: string
  severity: IncidentSeverity
  category: IncidentCategory
  title: string
  status: IncidentStatus
  first_seen: string
  last_seen: string
  trace_count: number
  details: Record<string, unknown> | null
}

export interface IncidentListResponse {
  items: IncidentRead[]
  total: number
}

export interface IncidentUpdate {
  status: IncidentStatus
}

export interface IncidentStatsBreakdown {
  open: number
  acknowledged: number
  resolved: number
  false_positive: number
}

export interface TraceStatsResponse {
  total_evaluations: number
  by_decision: Record<string, number>
  by_category: Record<string, number>
  by_gate: Record<string, number>
  avg_latency_ms: number
  incidents: IncidentStatsBreakdown
}
