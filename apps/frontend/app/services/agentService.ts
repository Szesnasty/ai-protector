import axios from 'axios'
import type { AxiosInstance } from 'axios'
import type { AgentChatRequest, AgentChatResponse } from '~/types/agent'

const baseURL = import.meta.env.NUXT_PUBLIC_AGENT_API_BASE ?? 'http://localhost:8002'

const agentApi: AxiosInstance = axios.create({
  baseURL,
  timeout: 60_000,
  headers: { 'Content-Type': 'application/json' },
})

agentApi.interceptors.request.use((config) => {
  config.headers['x-correlation-id'] = crypto.randomUUID()
  return config
})

export const agentService = {
  async chat(request: AgentChatRequest): Promise<AgentChatResponse> {
    const { data } = await agentApi.post<AgentChatResponse>('/agent/chat', request)
    return data
  },
}
