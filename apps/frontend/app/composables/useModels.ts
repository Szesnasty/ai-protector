/**
 * Composable for fetching the model catalog and computing availability.
 *
 * Uses @tanstack/vue-query (client-side only) instead of Nuxt's useAsyncData
 * to avoid SSR issues — the frontend Docker container cannot reach the proxy
 * at localhost:8000 during server rendering.
 *
 * Models for providers with a browser-stored API key (or ollama) are "available".
 * Others are hidden from dropdowns.
 */
import { computed, ref, type Ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { api } from '~/services/api'
import type { ModelInfo, ModelsResponse } from '~/types/api'
import { useApiKeys } from '~/composables/useApiKeys'

/**
 * Shared reactive trigger — lives inside a closure-safe getter so that
 * Nuxt SSR cannot leak it between requests (it's only relevant client-side
 * anyway, but this is the safe pattern).
 */
let _keyVersion: Ref<number> | null = null
function getKeyVersion(): Ref<number> {
  if (!_keyVersion) _keyVersion = ref(0)
  return _keyVersion
}

export function useModels() {
  const { hasKeyForProvider } = useApiKeys()
  const keyVersion = getKeyVersion()

  const { data: rawModels, isLoading, error, refetch } = useQuery<ModelInfo[]>({
    queryKey: ['models-catalog'],
    queryFn: () => api.get<ModelsResponse>('/v1/models').then((r) => r.data.models),
    staleTime: 60_000, // refetch after 1 min
  })

  /** Force re-evaluation of model availability (e.g. after adding an API key). */
  function refreshAvailability() {
    keyVersion.value++
  }

  /** All models with an `available` flag based on browser-stored keys. */
  const groupedModels = computed<ModelInfo[]>(() => {
    keyVersion.value // touch to create reactive dependency
    if (!rawModels.value) return []
    return rawModels.value.map((m) => ({
      ...m,
      available: m.provider === 'ollama' || m.provider === 'mock' || hasKeyForProvider(m.provider),
    }))
  })

  /** Only models for providers that have a key (or ollama). */
  const availableModels = computed<ModelInfo[]>(() =>
    groupedModels.value.filter((m) => m.available),
  )

  /** Unique providers that have at least one available model. */
  const availableProviders = computed<string[]>(() => {
    const set = new Set(availableModels.value.map((m) => m.provider))
    return [...set]
  })

  return {
    allModels: rawModels,
    groupedModels,
    availableModels,
    availableProviders,
    isLoading,
    error,
    refetch,
    refreshAvailability,
  }
}
