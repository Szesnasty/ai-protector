import type { Policy } from '~/types/api'

const BUILTIN = new Set(['fast', 'balanced', 'strict', 'paranoid'])

/**
 * Sort policies for select dropdowns:
 *  1. "balanced" always first
 *  2. Other built-in policies alphabetically (fast, paranoid, strict)
 *  3. Custom policies alphabetically
 */
export function sortedPolicyItems(policies: Policy[]): { title: string; value: string }[] {
  const sorted = [...policies].sort((a, b) => {
    const aBuiltin = BUILTIN.has(a.name)
    const bBuiltin = BUILTIN.has(b.name)
    const aBalanced = a.name === 'balanced'
    const bBalanced = b.name === 'balanced'

    // balanced always first
    if (aBalanced) return -1
    if (bBalanced) return 1

    // built-in before custom
    if (aBuiltin && !bBuiltin) return -1
    if (!aBuiltin && bBuiltin) return 1

    // within same group: alphabetical
    return a.name.localeCompare(b.name)
  })

  return sorted.map((p) => ({ title: p.name, value: p.name }))
}
