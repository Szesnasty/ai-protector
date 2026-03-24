import { useMutation, useQuery } from '@tanstack/vue-query'
import { benchmarkService } from '~/services/benchmarkService'
import type { CreateRunPayload, PackInfo } from '~/services/benchmarkService'

export const useBenchmarkPacks = () => {
  const { data: packs, isLoading, error } = useQuery<PackInfo[]>({
    queryKey: ['benchmark-packs'],
    queryFn: () => benchmarkService.listPacks(),
    staleTime: 60_000,
  })

  return { packs, isLoading, error }
}

export const useBenchmarkCreateRun = () => {
  const mutation = useMutation({
    mutationFn: (payload: CreateRunPayload) => benchmarkService.createRun(payload),
  })

  return {
    createRun: mutation.mutateAsync,
    isCreating: mutation.isPending,
    error: mutation.error,
  }
}
