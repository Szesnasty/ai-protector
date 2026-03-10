import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed, type Ref } from 'vue'
import { api } from '~/services/api'
import type {
  IncidentListResponse,
  IncidentRead,
  IncidentStatus,
  TraceListResponse,
  TraceStatsResponse,
} from '~/types/wizard'

export const useAgentTracesList = (
  agentId: () => string,
  filters?: {
    page?: Ref<number>
    perPage?: Ref<number>
    gate?: Ref<string | undefined>
    decision?: Ref<string | undefined>
    category?: Ref<string | undefined>
    rolloutMode?: Ref<string | undefined>
    sessionId?: Ref<string | undefined>
  },
) => {
  const queryKey = computed(() => [
    'wizard-agent-traces',
    agentId(),
    filters?.page?.value ?? 1,
    filters?.perPage?.value ?? 20,
    filters?.gate?.value,
    filters?.decision?.value,
    filters?.category?.value,
    filters?.rolloutMode?.value,
    filters?.sessionId?.value,
  ])

  const { data, isLoading, error, refetch } = useQuery<TraceListResponse>({
    queryKey,
    queryFn: () => {
      const qp = new URLSearchParams()
      qp.set('page', String(filters?.page?.value ?? 1))
      qp.set('per_page', String(filters?.perPage?.value ?? 20))
      if (filters?.gate?.value) qp.set('gate', filters.gate.value)
      if (filters?.decision?.value) qp.set('decision', filters.decision.value)
      if (filters?.category?.value) qp.set('category', filters.category.value)
      if (filters?.rolloutMode?.value) qp.set('rollout_mode', filters.rolloutMode.value)
      if (filters?.sessionId?.value) qp.set('session_id', filters.sessionId.value)
      return api.get<TraceListResponse>(`/v1/agents/${agentId()}/traces/list?${qp}`).then(r => r.data)
    },
    staleTime: 0,
    enabled: () => !!agentId(),
  })

  return {
    traces: computed(() => data.value?.items ?? []),
    total: computed(() => data.value?.total ?? 0),
    isLoading,
    error,
    refetch,
  }
}

export const useAgentTracesStats = (agentId: () => string) => {
  const { data: stats, isLoading, refetch } = useQuery<TraceStatsResponse>({
    queryKey: computed(() => ['wizard-agent-trace-stats', agentId()]),
    queryFn: () =>
      api.get<TraceStatsResponse>(`/v1/agents/${agentId()}/traces/stats`).then(r => r.data),
    staleTime: 0,
    enabled: () => !!agentId(),
  })

  return { stats, isLoading, refetch }
}

export const useAgentIncidents = (
  agentId: () => string,
  filters?: {
    status?: Ref<string | undefined>
    severity?: Ref<string | undefined>
    category?: Ref<string | undefined>
  },
) => {
  const queryClient = useQueryClient()

  const queryKey = computed(() => [
    'wizard-agent-incidents',
    agentId(),
    filters?.status?.value,
    filters?.severity?.value,
    filters?.category?.value,
  ])

  const { data, isLoading, error, refetch } = useQuery<IncidentListResponse>({
    queryKey,
    queryFn: () => {
      const qp = new URLSearchParams()
      if (filters?.status?.value) qp.set('status', filters.status.value)
      if (filters?.severity?.value) qp.set('severity', filters.severity.value)
      if (filters?.category?.value) qp.set('category', filters.category.value)
      return api.get<IncidentListResponse>(`/v1/agents/${agentId()}/incidents?${qp}`).then(r => r.data)
    },
    staleTime: 0,
    enabled: () => !!agentId(),
  })

  const updateMutation = useMutation({
    mutationFn: ({ incidentId, status }: { incidentId: string; status: IncidentStatus }) =>
      api.patch<IncidentRead>(`/v1/agents/${agentId()}/incidents/${incidentId}`, { status }).then(r => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKey.value })
    },
  })

  return {
    incidents: computed(() => data.value?.items ?? []),
    total: computed(() => data.value?.total ?? 0),
    isLoading,
    error,
    refetch,
    updateIncident: updateMutation.mutateAsync,
    isUpdating: updateMutation.isPending,
  }
}
