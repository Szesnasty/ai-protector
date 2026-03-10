import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed } from 'vue'
import { api } from '~/services/api'
import type {
  ToolCreate,
  ToolRead,
  ToolUpdate,
} from '~/types/wizard'

export const useAgentTools = (agentId: () => string) => {
  const queryClient = useQueryClient()

  const queryKey = computed(() => ['wizard-agent-tools', agentId()])

  const { data: tools, isLoading, error, refetch } = useQuery<ToolRead[]>({
    queryKey,
    queryFn: () =>
      api.get<ToolRead[]>(`/v1/agents/${agentId()}/tools`).then(r => r.data),
    staleTime: 0,
    enabled: () => !!agentId(),
  })

  const createMutation = useMutation({
    mutationFn: (body: ToolCreate) =>
      api.post<ToolRead>(`/v1/agents/${agentId()}/tools`, body).then(r => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKey.value })
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ toolId, body }: { toolId: string; body: ToolUpdate }) =>
      api.patch<ToolRead>(`/v1/agents/${agentId()}/tools/${toolId}`, body).then(r => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKey.value })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (toolId: string) =>
      api.delete(`/v1/agents/${agentId()}/tools/${toolId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKey.value })
    },
  })

  return {
    tools: computed(() => tools.value ?? []),
    isLoading,
    error,
    refetch,
    createTool: createMutation.mutateAsync,
    updateTool: updateMutation.mutateAsync,
    deleteTool: deleteMutation.mutateAsync,
    isCreating: createMutation.isPending,
    isUpdating: updateMutation.isPending,
    isDeleting: deleteMutation.isPending,
  }
}
