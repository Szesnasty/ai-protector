import { computed } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { healthService } from '../services/healthService'
import type { HealthResponse } from '~/types/api'

export const useHealth = () => {
  const { data, error, isLoading, dataUpdatedAt } = useQuery<HealthResponse>({
    queryKey: ['health'],
    queryFn: healthService.getHealth,
    refetchInterval: 30_000,
    refetchIntervalInBackground: true,
  })

  const status = computed(() => {
    if (isLoading.value) return 'loading' as const
    if (error.value) return 'error' as const
    return data.value?.status ?? ('error' as const)
  })

  const services = computed(() => data.value?.services ?? {})

  const lastChecked = computed(() =>
    dataUpdatedAt.value ? new Date(dataUpdatedAt.value) : null,
  )

  return { status, services, lastChecked, error, isLoading }
}
