import { useQuery } from '@tanstack/vue-query'
import { api } from '~/services/api'
import type { ScenarioGroup } from '~/types/scenarios'

/**
 * Fetches attack-scenario catalogue from the backend.
 * @param kind — `'playground'`, `'agent'`, or `'compare'`
 */
export function useScenarios(kind: 'playground' | 'agent' | 'compare') {
  const { data, isLoading, error } = useQuery<ScenarioGroup[]>({
    queryKey: ['scenarios', kind],
    queryFn: () => api.get<ScenarioGroup[]>(`/v1/scenarios/${kind}`).then(r => r.data),
    staleTime: 0,
    gcTime: 1000 * 60 * 60,     // keep in cache for 1h
  })

  return { scenarios: data, isLoading, error }
}
