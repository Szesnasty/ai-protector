/**
 * Composable for managing LLM provider API keys in browser storage.
 *
 * Keys are stored in SessionStorage (default) or localStorage ("Remember" opt-in).
 * The server NEVER stores, logs, or caches these keys.
 */
import { ref, onMounted } from 'vue'

const STORAGE_PREFIX = 'aiprotector:apiKey:'
const REMEMBER_PREFIX = 'aiprotector:remember:'

export interface ProviderDef {
  id: string
  name: string
  icon: string
  placeholder: string
}

export interface StoredKey {
  provider: string
  maskedKey: string
  remembered: boolean
}

export const PROVIDERS: ProviderDef[] = [
  { id: 'openai', name: 'OpenAI', icon: 'mdi-creation', placeholder: 'sk-proj-...' },
  { id: 'anthropic', name: 'Anthropic', icon: 'mdi-robot', placeholder: 'sk-ant-...' },
  { id: 'google', name: 'Google AI', icon: 'mdi-google', placeholder: 'AIza...' },
  { id: 'mistral', name: 'Mistral', icon: 'mdi-weather-windy', placeholder: 'mis-...' },
]

function maskKey(key: string): string {
  if (key.length <= 8) return '****'
  return `${key.slice(0, 3)}...${key.slice(-4)}`
}

/**
 * Detect provider from a model name (client-side mirror of backend logic).
 */
export function detectProviderClient(model: string): string {
  const m = model.toLowerCase()
  if (m.startsWith('gpt-') || m.startsWith('o1') || m.startsWith('o3')) return 'openai'
  if (m.startsWith('claude-') || m.startsWith('anthropic/')) return 'anthropic'
  if (m.startsWith('gemini/') || m.startsWith('gemini-')) return 'google'
  if (m.startsWith('mistral-') || m.startsWith('mistral/') || m.startsWith('codestral')) return 'mistral'
  return 'ollama'
}

/**
 * Get an API key for a given provider from browser storage.
 * Checks localStorage first (remembered), then sessionStorage.
 * Exported as a standalone function for use outside of Vue components (e.g. services).
 */
export function getKey(provider: string): string | null {
  if (typeof window === 'undefined') return null
  return (
    localStorage.getItem(`${STORAGE_PREFIX}${provider}`)
    ?? sessionStorage.getItem(`${STORAGE_PREFIX}${provider}`)
  )
}

export function useApiKeys() {
  const keys = ref<StoredKey[]>([])

  function saveKey(provider: string, apiKey: string, remember: boolean): void {
    const storage = remember ? localStorage : sessionStorage
    storage.setItem(`${STORAGE_PREFIX}${provider}`, apiKey)

    if (remember) {
      localStorage.setItem(`${REMEMBER_PREFIX}${provider}`, 'true')
    } else {
      localStorage.removeItem(`${REMEMBER_PREFIX}${provider}`)
    }

    refreshKeys()
  }

  function removeKey(provider: string): void {
    sessionStorage.removeItem(`${STORAGE_PREFIX}${provider}`)
    localStorage.removeItem(`${STORAGE_PREFIX}${provider}`)
    localStorage.removeItem(`${REMEMBER_PREFIX}${provider}`)
    refreshKeys()
  }

  function getKeyForModel(model: string): string | null {
    const provider = detectProviderClient(model)
    if (provider === 'ollama') return null
    return getKey(provider)
  }

  function hasKeyForProvider(provider: string): boolean {
    return getKey(provider) !== null
  }

  function refreshKeys(): void {
    keys.value = PROVIDERS
      .map((p) => {
        const key = getKey(p.id)
        if (!key) return null
        return {
          provider: p.id,
          maskedKey: maskKey(key),
          remembered: localStorage.getItem(`${REMEMBER_PREFIX}${p.id}`) === 'true',
        }
      })
      .filter(Boolean) as StoredKey[]
  }

  onMounted(refreshKeys)

  return {
    keys,
    saveKey,
    getKey,
    removeKey,
    getKeyForModel,
    hasKeyForProvider,
    refreshKeys,
    PROVIDERS,
  }
}
