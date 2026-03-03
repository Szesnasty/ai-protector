import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { api } from '~/services/api'
import type { Policy } from '~/types/api'

export const usePolicies = () => {
  const queryClient = useQueryClient()

  const { data: policies, isLoading, error, refetch } = useQuery<Policy[]>({
    queryKey: ['policies'],
    queryFn: () => api.get<Policy[]>('/v1/policies?active_only=false').then(r => r.data),
    staleTime: 60_000,
  })

  const createMutation = useMutation({
    mutationFn: (body: { name: string; description?: string; config?: Record<string, unknown> }) =>
      api.post<Policy>('/v1/policies', body).then(r => r.data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['policies'] }) },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      api.patch<Policy>(`/v1/policies/${id}`, body).then(r => r.data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['policies'] }) },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/v1/policies/${id}`),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['policies'] }) },
  })

  return {
    policies,
    isLoading,
    error,
    refetch,
    createPolicy: createMutation.mutateAsync,
    updatePolicy: updateMutation.mutateAsync,
    deletePolicy: deleteMutation.mutateAsync,
    isCreating: createMutation.isPending,
    isUpdating: updateMutation.isPending,
    isDeleting: deleteMutation.isPending,
  }
}
