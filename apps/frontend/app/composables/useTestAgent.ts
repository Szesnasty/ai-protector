/**
 * Composable for communicating with test agent endpoints (pure-python :8003, langgraph :8004).
 *
 * Uses direct axios calls (not the proxy `api` service) because test agents
 * run on their own ports and are NOT behind the AI Protector proxy.
 */
import { ref, type Ref } from 'vue'
import axios, { type AxiosInstance } from 'axios'

// ─── Types ───

export interface GateLogEntry {
  gate: string
  decision: string
  reason?: string
  tool?: string
  role?: string
  findings?: Array<{ type: string; detail: string }>
  scan_findings?: Array<{ type: string; detail: string }>
}

export interface ChatRequest {
  message: string
  role: string
  tool?: string
  tool_args?: Record<string, unknown>
  confirmed?: boolean
}

export interface ChatResponse {
  response: string
  blocked: boolean
  requires_confirmation?: boolean
  tool?: string
  tool_args?: Record<string, unknown>
  gate_log: GateLogEntry[]
}

export interface ConfigStatus {
  loaded: boolean
  roles: string[]
  tools_in_rbac?: number
  policy_pack: string
}

export interface HealthStatus {
  status: string
  config_loaded: boolean
  framework?: string
}

// ─── Composable ───

export function useTestAgent(baseUrl: Ref<string> | string) {
  const resolvedUrl = typeof baseUrl === 'string' ? ref(baseUrl) : baseUrl

  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const configStatus = ref<ConfigStatus | null>(null)

  function client(): AxiosInstance {
    return axios.create({
      baseURL: resolvedUrl.value,
      timeout: 30_000,
      headers: { 'Content-Type': 'application/json' },
    })
  }

  async function loadConfig(agentId: string): Promise<ConfigStatus> {
    isLoading.value = true
    error.value = null
    try {
      const res = await client().post<ConfigStatus>('/load-config', { agent_id: agentId })
      configStatus.value = res.data
      return res.data
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Failed to load config'
      error.value = msg
      throw new Error(msg)
    } finally {
      isLoading.value = false
    }
  }

  async function chat(req: ChatRequest): Promise<ChatResponse> {
    error.value = null
    try {
      const res = await client().post<ChatResponse>('/chat', req)
      return res.data
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Chat request failed'
      error.value = msg
      throw new Error(msg)
    }
  }

  async function getConfigStatus(): Promise<ConfigStatus> {
    error.value = null
    try {
      const res = await client().get<ConfigStatus>('/config-status')
      configStatus.value = res.data
      return res.data
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Failed to get config status'
      error.value = msg
      throw new Error(msg)
    }
  }

  async function getHealth(): Promise<HealthStatus> {
    error.value = null
    try {
      const res = await client().get<HealthStatus>('/health')
      return res.data
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Health check failed'
      error.value = msg
      throw new Error(msg)
    }
  }

  async function resetConfig(): Promise<void> {
    error.value = null
    try {
      await client().post('/reset-config')
      configStatus.value = null
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Failed to reset config'
      error.value = msg
      throw new Error(msg)
    }
  }

  return {
    isLoading,
    error,
    configStatus,
    loadConfig,
    chat,
    getConfigStatus,
    getHealth,
    resetConfig,
  }
}
