import { useQuery } from '@tanstack/vue-query'
import { policyService } from '~/services/policyService'
import type { Policy } from '~/types/api'

export const usePolicies = () => {
  const { data: policies, isLoading, error } = useQuery<Policy[]>({
    queryKey: ['policies'],
    queryFn: policyService.listActive,
    staleTime: 60_000,
  })

  return { policies, isLoading, error }
}
