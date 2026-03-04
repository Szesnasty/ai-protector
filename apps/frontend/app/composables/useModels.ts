/**
 * Composable for fetching the model catalog and computing availability.
 *
 * Models for providers with a browser-stored API key (or ollama) are "available".
 * Others are shown but grayed out in the UI.
 */
import { computed, ref } from 'vue'
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

  /**
   * Reactive trigger — bump this to force `groupedModels` to recompute.
   * Needed because `hasKeyForProvider` reads from browser Storage which is
   * not reactive in Vue.
   */
  const _keyVersion = ref(0)

  /** Force re-evaluation of model availability (e.g. after adding an API key). */
  function refreshAvailability() {
    _keyVersion.value++
  }

  /** All models with an `available` flag based on browser-stored keys. */
  const groupedModels = computed<ModelInfo[]>(() => {
    _keyVersion.value // touch to create reactive dependency
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
    refreshAvailability,
  }
}
