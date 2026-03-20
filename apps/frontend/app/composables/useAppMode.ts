/**
 * Composable that detects application mode (demo / real) from the
 * proxy-service `/health` endpoint.
 *
 * Fetched once on first call; subsequent consumers share the same
 * reactive state.
 */

import { computed, type ComputedRef, type Ref } from 'vue'

interface AppMode {
  mode: 'demo' | 'real'
  version: string
}

interface UseAppMode {
  appMode: Ref<AppMode | null>
  isDemo: ComputedRef<boolean>
  fetchMode: () => Promise<void>
}

export function useAppMode(): UseAppMode {
  const appMode = useState<AppMode | null>('appMode', () => null)

  const isDemo = computed(() => appMode.value?.mode === 'demo')

  async function fetchMode(): Promise<void> {
    if (appMode.value) return // already fetched

    try {
      const config = useRuntimeConfig()
      const data = await $fetch<Record<string, unknown>>(
        `${config.public.apiBase}/health`,
      )
      appMode.value = {
        mode: (data.mode as AppMode['mode']) ?? 'real',
        version: (data.version as string) ?? '0.1.10',
      }
    } catch {
      // Fallback — assume real mode if health fails
      appMode.value = { mode: 'real', version: '0.1.10' }
    }
  }

  return { appMode, isDemo, fetchMode }
}
