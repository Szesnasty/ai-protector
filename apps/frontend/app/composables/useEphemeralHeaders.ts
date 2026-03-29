/**
 * Ephemeral in-memory store for custom headers between page navigations.
 *
 * Headers live ONLY in JavaScript memory — never written to sessionStorage,
 * localStorage, cookies, or any other persistence layer. They are consumed
 * exactly once (take-and-clear pattern) and discarded automatically when the
 * tab/window is closed.
 */

let _headers: Record<string, string> | null = null

export function useEphemeralHeaders() {
  /** Store headers in memory (replaces any previous value). */
  function stash(headers: Record<string, string>): void {
    _headers = Object.keys(headers).length > 0 ? { ...headers } : null
  }

  /** Consume headers: returns the stored value and clears memory. */
  function take(): Record<string, string> | null {
    const h = _headers
    _headers = null
    return h
  }

  /** Clear without reading. */
  function clear(): void {
    _headers = null
  }

  return { stash, take, clear }
}
