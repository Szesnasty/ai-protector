import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed } from 'vue'
import { api } from '~/services/api'
import type { ValidationResponse, ValidationRunRead } from '~/types/wizard'

export const useAgentValidation = (agentId: () => string) => {
  const queryClient = useQueryClient()

  const queryKey = computed(() => ['wizard-agent-validations', agentId()])

  const { data: validations, isLoading, error, refetch } = useQuery<ValidationRunRead[]>({
    queryKey,
    queryFn: () =>
      api.get<ValidationRunRead[]>(`/v1/agents/${agentId()}/validations`).then(r => r.data),
    staleTime: 0,
    enabled: () => !!agentId(),
  })

  const latest = computed(() => {
    const runs = validations.value
    if (!runs?.length) return null
    return runs.reduce((a, b) => (a.created_at > b.created_at ? a : b))
  })

  const runMutation = useMutation({
    mutationFn: (pack: string | undefined) =>
      api.post<ValidationResponse>(`/v1/agents/${agentId()}/validate`, pack ? { pack } : {}).then(r => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKey.value })
    },
  })

  const run = (pack?: string) => runMutation.mutateAsync(pack)

  return {
    validations: computed(() => validations.value ?? []),
    latest,
    isLoading,
    error,
    refetch,
    run,
    isRunning: runMutation.isPending,
  }
}
