import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { api } from '~/services/api'
import type { RequestDetail, RequestRead, PaginatedResponse, RequestFilters } from '~/types/api'

export function useRequestLog() {
  const _queryClient = useQueryClient()

  const filters = ref<RequestFilters>({
    decision: null,
    policy_id: null,
    intent: null,
    risk_min: null,
    risk_max: null,
    search: null,
    from: null,
    to: null,
  })

  const page = ref(1)
  const pageSize = ref(25)
  const sortBy = ref('created_at')
  const sortOrder = ref<'asc' | 'desc'>('desc')

  const { data, isLoading, error, refetch } = useQuery<PaginatedResponse<RequestRead>>({
    queryKey: ['requests', filters, page, pageSize, sortBy, sortOrder] as const,
    queryFn: async () => {
      const params = new URLSearchParams()
      params.set('page', String(page.value))
      params.set('page_size', String(pageSize.value))
      params.set('sort', sortBy.value)
      params.set('order', sortOrder.value)

      const f = filters.value
      if (f.decision) params.set('decision', f.decision)
      if (f.policy_id) params.set('policy_id', f.policy_id)
      if (f.intent) params.set('intent', f.intent)
      if (f.risk_min != null) params.set('risk_min', String(f.risk_min))
      if (f.risk_max != null) params.set('risk_max', String(f.risk_max))
      if (f.search) params.set('search', f.search)
      if (f.from) params.set('from', f.from)
      if (f.to) params.set('to', f.to)

      const { data: resp } = await api.get<PaginatedResponse<RequestRead>>(
        `/v1/requests?${params.toString()}`,
      )
      return resp
    },
    placeholderData: (prev) => prev,
  })

  async function fetchDetail(id: string): Promise<RequestDetail> {
    const { data: resp } = await api.get<RequestDetail>(`/v1/requests/${id}`)
    return resp
  }

  function resetFilters() {
    filters.value = {
      decision: null,
      policy_id: null,
      intent: null,
      risk_min: null,
      risk_max: null,
      search: null,
      from: null,
      to: null,
    }
    page.value = 1
  }

  const hasActiveFilters = computed(() => {
    const f = filters.value
    return !!(f.decision || f.policy_id || f.intent || f.search || f.from || f.to || f.risk_min != null || f.risk_max != null)
  })

  return {
    data,
    isLoading,
    error,
    filters,
    page,
    pageSize,
    sortBy,
    sortOrder,
    fetchDetail,
    refetch,
    resetFilters,
    hasActiveFilters,
  }
}
