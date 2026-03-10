import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed } from 'vue'
import { api } from '~/services/api'
import type { IntegrationKit } from '~/types/wizard'

export const useAgentKit = (agentId: () => string) => {
  const queryClient = useQueryClient()

  const queryKey = computed(() => ['wizard-agent-kit', agentId()])

  const { data: kit, isLoading, error, refetch } = useQuery<IntegrationKit | null>({
    queryKey,
    queryFn: () =>
      api.get<IntegrationKit>(`/v1/agents/${agentId()}/integration-kit`).then(r => r.data).catch(() => null),
    staleTime: 0,
    enabled: () => !!agentId(),
  })

  const generateMutation = useMutation({
    mutationFn: () =>
      api.post<IntegrationKit>(`/v1/agents/${agentId()}/integration-kit`).then(r => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKey.value })
    },
  })

  const download = () => {
    window.open(`${api.defaults.baseURL}/v1/agents/${agentId()}/integration-kit/download`, '_blank')
  }

  const copyFile = async (content: string) => {
    await navigator.clipboard.writeText(content)
  }

  return {
    kit,
    isLoading,
    error,
    refetch,
    generate: generateMutation.mutateAsync,
    isGenerating: generateMutation.isPending,
    download,
    copyFile,
  }
}
