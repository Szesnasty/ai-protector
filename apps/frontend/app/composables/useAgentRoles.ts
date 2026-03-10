import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed } from 'vue'
import { api } from '~/services/api'
import type {
  PermissionBatchSet,
  PermissionMatrixResponse,
  PermissionRead,
  RoleCreate,
  RoleRead,
  RoleUpdate,
} from '~/types/wizard'

export const useAgentRoles = (agentId: () => string) => {
  const queryClient = useQueryClient()

  const queryKey = computed(() => ['wizard-agent-roles', agentId()])
  const matrixKey = computed(() => ['wizard-agent-matrix', agentId()])

  const { data: roles, isLoading, error, refetch } = useQuery<RoleRead[]>({
    queryKey,
    queryFn: () =>
      api.get<RoleRead[]>(`/v1/agents/${agentId()}/roles`).then(r => r.data),
    staleTime: 0,
    enabled: () => !!agentId(),
  })

  const { data: matrix, refetch: refetchMatrix } = useQuery<PermissionMatrixResponse>({
    queryKey: matrixKey,
    queryFn: () =>
      api.get<PermissionMatrixResponse>(`/v1/agents/${agentId()}/permission-matrix`).then(r => r.data),
    staleTime: 0,
    enabled: () => !!agentId(),
  })

  const createMutation = useMutation({
    mutationFn: (body: RoleCreate) =>
      api.post<RoleRead>(`/v1/agents/${agentId()}/roles`, body).then(r => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKey.value })
      queryClient.invalidateQueries({ queryKey: matrixKey.value })
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ roleId, body }: { roleId: string; body: RoleUpdate }) =>
      api.patch<RoleRead>(`/v1/agents/${agentId()}/roles/${roleId}`, body).then(r => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKey.value })
      queryClient.invalidateQueries({ queryKey: matrixKey.value })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (roleId: string) =>
      api.delete(`/v1/agents/${agentId()}/roles/${roleId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKey.value })
      queryClient.invalidateQueries({ queryKey: matrixKey.value })
    },
  })

  const setPermissions = useMutation({
    mutationFn: ({ roleId, body }: { roleId: string; body: PermissionBatchSet }) =>
      api.put<PermissionRead[]>(`/v1/agents/${agentId()}/roles/${roleId}/permissions`, body).then(r => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKey.value })
      queryClient.invalidateQueries({ queryKey: matrixKey.value })
    },
  })

  return {
    roles: computed(() => roles.value ?? []),
    matrix,
    isLoading,
    error,
    refetch,
    refetchMatrix,
    createRole: createMutation.mutateAsync,
    updateRole: updateMutation.mutateAsync,
    deleteRole: deleteMutation.mutateAsync,
    setPermissions: setPermissions.mutateAsync,
    isCreating: createMutation.isPending,
    isUpdating: updateMutation.isPending,
    isDeleting: deleteMutation.isPending,
  }
}
