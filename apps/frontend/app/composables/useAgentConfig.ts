import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed } from 'vue'
import { api } from '~/services/api'
import type { GeneratedConfig, PolicyPack } from '~/types/wizard'

export const useAgentConfig = (agentId: () => string) => {
  const queryClient = useQueryClient()

  const queryKey = computed(() => ['wizard-agent-config', agentId()])

  const { data: config, isLoading, error, refetch } = useQuery<GeneratedConfig | null>({
    queryKey,
    queryFn: () =>
      api.get<GeneratedConfig>(`/v1/agents/${agentId()}/config`).then(r => r.data).catch(() => null),
    staleTime: 0,
    enabled: () => !!agentId(),
  })

  const generateMutation = useMutation({
    mutationFn: () =>
      api.post<GeneratedConfig>(`/v1/agents/${agentId()}/generate-config`).then(r => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKey.value })
    },
  })

  const { data: policyPacks } = useQuery<PolicyPack[]>({
    queryKey: ['wizard-policy-packs'],
    queryFn: () => api.get<PolicyPack[]>('/v1/policy-packs').then(r => r.data),
    staleTime: 60_000,
  })

  const downloadConfig = () => {
    window.open(`${api.defaults.baseURL}/v1/agents/${agentId()}/config/download`, '_blank')
  }

  return {
    config,
    policyPacks: computed(() => policyPacks.value ?? []),
    isLoading,
    error,
    refetch,
    generate: generateMutation.mutateAsync,
    isGenerating: generateMutation.isPending,
    downloadConfig,
  }
}
