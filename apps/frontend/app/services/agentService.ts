import axios from 'axios'
import type { AxiosInstance } from 'axios'
import type { AgentChatRequest, AgentChatResponse } from '~/types/agent'
import { detectProviderClient, getKey } from '~/composables/useApiKeys'

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
    const headers: Record<string, string> = {}

    // Inject API key for external providers
    if (request.model) {
      const provider = detectProviderClient(request.model)
      if (provider !== 'ollama') {
        const apiKey = getKey(provider)
        if (apiKey) {
          headers['x-api-key'] = apiKey
        }
      }
    }

    const { data } = await agentApi.post<AgentChatResponse>('/agent/chat', request, { headers })
    return data
  },
}
