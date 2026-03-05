/**
 * Persists the last-selected model per view in localStorage.
 *
 * Storage key: `ai-protector:remembered-models`
 * Shape: `{ [viewName: string]: modelId }`
 */

const STORAGE_KEY = 'ai-protector:remembered-models'

function loadAll(): Record<string, string> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

function saveAll(map: Record<string, string>) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(map))
}

export function useRememberedModel(viewName: string) {
  /** Read the remembered model ID for this view (or empty string). */
  function get(): string {
    return loadAll()[viewName] ?? ''
  }

  /** Save the selected model ID for this view. */
  function set(modelId: string) {
    if (!modelId) return
    const map = loadAll()
    map[viewName] = modelId
    saveAll(map)
  }

  return { get, set }
}
