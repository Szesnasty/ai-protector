import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed, type Ref } from 'vue'
import { api } from '~/services/api'
import type {
  AgentCreate,
  AgentListResponse,
  AgentRead,
  AgentUpdate,
} from '~/types/wizard'

export const useAgents = (params?: {
  page?: Ref<number>
  perPage?: Ref<number>
  status?: Ref<string | undefined>
  riskLevel?: Ref<string | undefined>
}) => {
  const queryClient = useQueryClient()

  const queryKey = computed(() => [
    'wizard-agents',
    params?.page?.value ?? 1,
    params?.perPage?.value ?? 20,
    params?.status?.value,
    params?.riskLevel?.value,
  ])

  const { data, isLoading, error, refetch } = useQuery<AgentListResponse>({
    queryKey,
    queryFn: () => {
      const qp = new URLSearchParams()
      qp.set('page', String(params?.page?.value ?? 1))
      qp.set('per_page', String(params?.perPage?.value ?? 20))
      if (params?.status?.value) qp.set('status', params.status.value)
      if (params?.riskLevel?.value) qp.set('risk_level', params.riskLevel.value)
      return api.get<AgentListResponse>(`/v1/agents?${qp}`).then(r => r.data)
    },
    staleTime: 0,
  })

  const agents = computed(() => data.value?.items ?? [])
  const total = computed(() => data.value?.total ?? 0)

  const getAgent = (id: string) =>
    api.get<AgentRead>(`/v1/agents/${id}`).then(r => r.data)

  const createMutation = useMutation({
    mutationFn: (body: AgentCreate) =>
      api.post<AgentRead>('/v1/agents', body).then(r => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['wizard-agents'] })
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: AgentUpdate }) =>
      api.patch<AgentRead>(`/v1/agents/${id}`, body).then(r => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['wizard-agents'] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/v1/agents/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['wizard-agents'] })
    },
  })

  return {
    agents,
    total,
    isLoading,
    error,
    refetch,
    getAgent,
    createAgent: createMutation.mutateAsync,
    updateAgent: updateMutation.mutateAsync,
    deleteAgent: deleteMutation.mutateAsync,
    isCreating: createMutation.isPending,
    isUpdating: updateMutation.isPending,
    isDeleting: deleteMutation.isPending,
  }
}
