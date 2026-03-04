/**
 * Composable for fetching the model catalog and computing availability.
 *
 * Models for providers with a browser-stored API key (or ollama) are "available".
 * Others are shown but grayed out in the UI.
 */
import { computed } from 'vue'
import { api } from '~/services/api'
import type { ModelInfo, ModelsResponse } from '~/types/api'
import { useApiKeys } from '~/composables/useApiKeys'

export function useModels() {
  const { hasKeyForProvider } = useApiKeys()

  const { data: rawModels, isLoading, error, refetch } = useAsyncData<ModelInfo[]>(
    'models-catalog',
    async () => {
      const resp = await api.get<ModelsResponse>('/v1/models')
      return resp.data.models
    },
    { default: () => [] },
  )

  /** All models with an `available` flag based on browser-stored keys. */
  const groupedModels = computed<ModelInfo[]>(() => {
    if (!rawModels.value) return []
    return rawModels.value.map((m) => ({
      ...m,
      available: m.provider === 'ollama' || hasKeyForProvider(m.provider),
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
  }
}
