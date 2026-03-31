/**
 * SessionStorage-backed store for scan configuration (request template +
 * response text paths) that survives page navigation within the same tab.
 *
 * Unlike ephemeral headers (in-memory only), this data is NOT sensitive
 * — it describes the *shape* of requests/responses, not secrets.
 */

const STORAGE_KEY = 'ai-protector:scan-config'

export interface ScanConfig {
  /** JSON template with {{PROMPT}} placeholder */
  requestTemplate: string
  /** Dot-notation paths to extract body_text from JSON responses */
  responseTextPaths: string[]
}

const _empty: ScanConfig = { requestTemplate: '', responseTextPaths: [] }

function _read(): ScanConfig {
  if (import.meta.server) return { ..._empty }
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return { ..._empty }
    return JSON.parse(raw) as ScanConfig
  } catch {
    return { ..._empty }
  }
}

function _write(cfg: ScanConfig): void {
  if (import.meta.server) return
  try {
    if (!cfg.requestTemplate && cfg.responseTextPaths.length === 0) {
      sessionStorage.removeItem(STORAGE_KEY)
    } else {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(cfg))
    }
  } catch {
    // sessionStorage full or unavailable — silently ignore
  }
}

export function useScanConfig() {
  /** Read current scan config from sessionStorage. */
  function load(): ScanConfig {
    return _read()
  }

  /** Persist scan config to sessionStorage. */
  function save(cfg: ScanConfig): void {
    _write(cfg)
  }

  /** Clear stored scan config. */
  function clear(): void {
    if (!import.meta.server) {
      sessionStorage.removeItem(STORAGE_KEY)
    }
  }

  /** Check if a request template contains the required placeholder. */
  function hasAttackPlaceholder(template: string): boolean {
    return template.includes('{{PROMPT}}') || template.includes('{{ATTACK_PROMPT}}')
  }

  return { load, save, clear, hasAttackPlaceholder }
}
