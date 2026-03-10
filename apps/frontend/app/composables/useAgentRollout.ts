import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed } from 'vue'
import { api } from '~/services/api'
import type {
  PromotionEventRead,
  ReadinessResponse,
  RolloutMode,
  RolloutPromoteResponse,
} from '~/types/wizard'

export const useAgentRollout = (agentId: () => string) => {
  const queryClient = useQueryClient()

  const readinessKey = computed(() => ['wizard-agent-readiness', agentId()])
  const eventsKey = computed(() => ['wizard-agent-rollout-events', agentId()])

  const { data: readiness, isLoading: readinessLoading, refetch: refetchReadiness } = useQuery<ReadinessResponse>({
    queryKey: readinessKey,
    queryFn: () =>
      api.get<ReadinessResponse>(`/v1/agents/${agentId()}/rollout/readiness`).then(r => r.data),
    staleTime: 0,
    enabled: () => !!agentId(),
  })

  const { data: events, refetch: refetchEvents } = useQuery<PromotionEventRead[]>({
    queryKey: eventsKey,
    queryFn: () =>
      api.get<PromotionEventRead[]>(`/v1/agents/${agentId()}/rollout/events`).then(r => r.data),
    staleTime: 0,
    enabled: () => !!agentId(),
  })

  const promoteMutation = useMutation({
    mutationFn: (mode: RolloutMode) =>
      api.patch<RolloutPromoteResponse>(`/v1/agents/${agentId()}/rollout`, { mode }).then(r => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['wizard-agents'] })
      queryClient.invalidateQueries({ queryKey: readinessKey.value })
      queryClient.invalidateQueries({ queryKey: eventsKey.value })
    },
  })

  return {
    readiness,
    events: computed(() => events.value ?? []),
    readinessLoading,
    refetchReadiness,
    refetchEvents,
    promote: promoteMutation.mutateAsync,
    isPromoting: promoteMutation.isPending,
  }
}
