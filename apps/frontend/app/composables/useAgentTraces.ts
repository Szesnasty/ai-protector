import { useQuery } from '@tanstack/vue-query'
import axios from 'axios'
import type {
  AgentTraceSummary,
  AgentTraceListResponse,
  AgentTraceDetail,
  AgentTraceExport,
  AgentTraceFilters,
} from '~/types/agentTrace'

const baseURL = import.meta.env.NUXT_PUBLIC_AGENT_API_BASE ?? 'http://localhost:8002'

const agentTracesApi = axios.create({
  baseURL,
  timeout: 15_000,
  headers: { 'Content-Type': 'application/json' },
})

export function useAgentTraces() {
  const filters = ref<AgentTraceFilters>({
    session_id: null,
    user_role: null,
    has_blocks: null,
    date_from: null,
    date_to: null,
  })

  const page = ref(1)
  const pageSize = ref(25)

  const { data, isLoading, error, refetch } = useQuery<AgentTraceListResponse>({
    queryKey: ['agent-traces', filters, page, pageSize] as const,
    queryFn: async () => {
      const params = new URLSearchParams()
      const offset = (page.value - 1) * pageSize.value
      params.set('limit', String(pageSize.value))
      params.set('offset', String(offset))

      const f = filters.value
      if (f.session_id) params.set('session_id', f.session_id)
      if (f.user_role) params.set('user_role', f.user_role)
      if (f.has_blocks != null) params.set('has_blocks', String(f.has_blocks))
      if (f.date_from) params.set('date_from', f.date_from)
      if (f.date_to) params.set('date_to', f.date_to)

      const { data: resp } = await agentTracesApi.get<AgentTraceListResponse>(
        `/agent/traces?${params.toString()}`,
      )
      return resp
    },
    placeholderData: (prev) => prev,
    staleTime: 0,
    refetchOnWindowFocus: true,
  })

  const items = computed<AgentTraceSummary[]>(() => data.value?.items ?? [])
  const total = computed(() => data.value?.total ?? 0)

  async function fetchDetail(traceId: string): Promise<AgentTraceDetail> {
    const { data: resp } = await agentTracesApi.get<AgentTraceDetail>(
      `/agent/traces/${traceId}`,
    )
    return resp
  }

  async function fetchExport(traceId: string): Promise<AgentTraceExport> {
    const { data: resp } = await agentTracesApi.get<AgentTraceExport>(
      `/agent/traces/${traceId}/export`,
    )
    return resp
  }

  function resetFilters() {
    filters.value = {
      session_id: null,
      user_role: null,
      has_blocks: null,
      date_from: null,
      date_to: null,
    }
    page.value = 1
  }

  const hasActiveFilters = computed(() => {
    const f = filters.value
    return !!(f.session_id || f.user_role || f.has_blocks != null || f.date_from || f.date_to)
  })

  return {
    items,
    total,
    isLoading,
    error,
    filters,
    page,
    pageSize,
    fetchDetail,
    fetchExport,
    refetch,
    resetFilters,
    hasActiveFilters,
  }
}
