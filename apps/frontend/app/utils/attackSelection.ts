// Selection logic for the 3-level attack tree (category → source corpus → subtype).
//
// Standard tree-checkbox model: the state is the set of *explicitly checked* node keys at
// every level. Toggling a node cascades DOWN (check/uncheck all its descendants) and UP
// (a parent becomes checked only when all its children are; unchecking a child unchecks its
// ancestors). A node renders checked / indeterminate / none from that set. The backend
// filters are the minimal "topmost checked" nodes.

import type { CategoryInfo, SelectionFilter } from '~/services/benchmarkService'

export type Coverage = 'checked' | 'indeterminate' | 'none'

const SEP = '|'
export const catKey = (cat: string): string => `c${SEP}${cat}`
export const srcKey = (cat: string, pack: string): string => `s${SEP}${cat}${SEP}${pack}`
export const subKey = (cat: string, pack: string, sub: string): string =>
  `t${SEP}${cat}${SEP}${pack}${SEP}${sub}`

/** Every node key in a category subtree (category + sources + subtypes). */
function categoryKeys(cat: CategoryInfo): string[] {
  const keys = [catKey(cat.category)]
  for (const src of cat.sources) {
    keys.push(srcKey(cat.category, src.name))
    for (const sub of src.subcategories) keys.push(subKey(cat.category, src.name, sub.name))
  }
  return keys
}

/** All node keys across the whole catalog (for the default "all selected" + "All" button). */
export function allKeys(categories: CategoryInfo[]): Set<string> {
  return new Set(categories.flatMap(categoryKeys))
}

/** Keys of a node (inclusive) and its descendants. */
function subtreeKeys(cat: CategoryInfo, pack?: string, sub?: string): string[] {
  if (sub) return [subKey(cat.category, pack!, sub)]
  if (pack) {
    const src = cat.sources.find((s) => s.name === pack)
    return [srcKey(cat.category, pack), ...(src?.subcategories.map((x) => subKey(cat.category, pack, x.name)) ?? [])]
  }
  return categoryKeys(cat)
}

function nodeKey(cat: CategoryInfo, pack?: string, sub?: string): string {
  return sub ? subKey(cat.category, pack!, sub) : pack ? srcKey(cat.category, pack) : catKey(cat.category)
}

/** Toggle a node: cascade to all descendants, then reconcile ancestors. Returns a NEW set. */
export function toggle(checked: Set<string>, cat: CategoryInfo, pack?: string, sub?: string): Set<string> {
  const next = new Set(checked)
  const keys = subtreeKeys(cat, pack, sub)
  const turningOn = !next.has(nodeKey(cat, pack, sub))

  for (const k of keys) {
    if (turningOn) next.add(k)
    else next.delete(k)
  }

  if (!turningOn) {
    // Unchecking a child means its ancestors can no longer be "all checked".
    if (sub) next.delete(srcKey(cat.category, pack!))
    if (pack || sub) next.delete(catKey(cat.category))
  } else {
    // A source auto-checks when all its subtypes are checked; a category when all sources are.
    if (sub) {
      const src = cat.sources.find((s) => s.name === pack)
      if (src && src.subcategories.every((x) => next.has(subKey(cat.category, pack!, x.name)))) {
        next.add(srcKey(cat.category, pack!))
      }
    }
    if (cat.sources.length && cat.sources.every((s) => next.has(srcKey(cat.category, s.name)))) {
      next.add(catKey(cat.category))
    }
  }
  return next
}

export function coverage(checked: Set<string>, cat: CategoryInfo, pack?: string, sub?: string): Coverage {
  if (checked.has(nodeKey(cat, pack, sub))) return 'checked'
  const descendants = subtreeKeys(cat, pack, sub).filter((k) => k !== nodeKey(cat, pack, sub))
  return descendants.some((k) => checked.has(k)) ? 'indeterminate' : 'none'
}

/** Minimal backend filters: the topmost fully-checked node on each branch. */
export function buildFilters(checked: Set<string>, categories: CategoryInfo[]): SelectionFilter[] {
  const out: SelectionFilter[] = []
  for (const c of categories) {
    if (checked.has(catKey(c.category))) {
      out.push({ category: c.category })
      continue
    }
    for (const src of c.sources) {
      if (checked.has(srcKey(c.category, src.name))) {
        out.push({ category: c.category, pack: src.name })
        continue
      }
      for (const sub of src.subcategories) {
        if (checked.has(subKey(c.category, src.name, sub.name))) {
          out.push({ category: c.category, pack: src.name, subcategory: sub.name })
        }
      }
    }
  }
  return out
}

/** Source packs to load for the current selection. */
export function buildPacks(checked: Set<string>, categories: CategoryInfo[]): string[] {
  const packs = new Set<string>()
  for (const c of categories) {
    const whole = checked.has(catKey(c.category))
    for (const src of c.sources) {
      if (whole || checked.has(srcKey(c.category, src.name))
        || src.subcategories.some((x) => checked.has(subKey(c.category, src.name, x.name)))) {
        packs.add(src.name)
      }
    }
  }
  return [...packs]
}

/** Per-category selected attack count from the topmost-checked nodes (disjoint). */
export function countsByCategory(checked: Set<string>, categories: CategoryInfo[]): Map<string, number> {
  const out = new Map<string, number>()
  for (const c of categories) {
    let n = 0
    if (checked.has(catKey(c.category))) {
      n = c.count
    } else {
      for (const src of c.sources) {
        if (checked.has(srcKey(c.category, src.name))) {
          n += src.count
        } else {
          for (const sub of src.subcategories) {
            if (checked.has(subKey(c.category, src.name, sub.name))) n += sub.count
          }
        }
      }
    }
    if (n > 0) out.set(c.category, n)
  }
  return out
}

/** Total attacks that will run, after the per-category sample cap. */
export function totalSelected(
  checked: Set<string>,
  categories: CategoryInfo[],
  samplePerCategory: number | null,
): number {
  let total = 0
  for (const n of countsByCategory(checked, categories).values()) {
    total += samplePerCategory ? Math.min(n, samplePerCategory) : n
  }
  return total
}
