<template>
  <v-menu
    v-model="open"
    :close-on-content-click="false"
    location="bottom start"
    offset="4"
    :width="menuWidth"
    max-height="460"
  >
    <template #activator="{ props: activator }">
      <div
        ref="fieldRef"
        v-bind="activator"
        class="field"
        :class="{ 'field--open': open }"
        @click="syncWidth"
      >
        <div class="field-content">
          <template v-if="chips.length">
            <v-chip
              v-for="chip in chips"
              :key="chip.key"
              size="small"
              color="primary"
              variant="tonal"
              closable
              class="ma-1"
              @click:close.stop="removeChip(chip.filter)"
              @click.stop
            >
              {{ chip.label }}
            </v-chip>
          </template>
          <span v-else class="placeholder">Select attacks by threat…</span>
        </div>
        <v-icon :icon="open ? 'mdi-menu-up' : 'mdi-menu-down'" class="field-chevron" />
      </div>
    </template>

    <v-card :width="menuWidth" class="menu-card">
      <div class="pa-2 pb-1">
        <v-text-field
          v-model="search"
          prepend-inner-icon="mdi-magnify"
          placeholder="Search threats, sources, or attack types…"
          density="compact"
          variant="outlined"
          hide-details
          clearable
          autofocus
        />
      </div>

      <div class="tree-scroll">
        <template v-for="cat in visibleCategories" :key="cat.category">
          <!-- ── Category ─────────────────────────────── -->
          <div class="node node--cat" @click="toggleExpand(catKey(cat.category))">
            <v-icon :icon="expandIcon(catKey(cat.category))" size="small" class="chev" />
            <v-icon
              :icon="boxIcon(coverage(modelValue, cat))"
              :color="coverage(modelValue, cat) === 'none' ? undefined : 'primary'"
              size="small"
              class="box"
              @click.stop="emitToggle(cat)"
            />
            <span class="label label--strong">{{ humanCategory(cat.category) }}</span>
            <v-chip v-if="cat.owasp && cat.owasp !== '—'" size="x-small" color="primary" variant="tonal" class="ml-2">
              {{ cat.owasp }}
            </v-chip>
            <span class="count">{{ cat.count }}</span>
            <v-spacer />
            <span class="muted d-none d-sm-inline">{{ cat.sources.length }} {{ cat.sources.length === 1 ? 'source' : 'sources' }}</span>
          </div>

          <!-- ── Sources ──────────────────────────────── -->
          <template v-if="isExpanded(catKey(cat.category))">
            <template v-for="src in visibleSources(cat)" :key="src.name">
              <div class="node node--src" @click="toggleExpand(srcKey(cat.category, src.name))">
                <v-icon
                  v-if="src.subcategories.length"
                  :icon="expandIcon(srcKey(cat.category, src.name))"
                  size="small"
                  class="chev"
                />
                <span v-else class="chev-spacer" />
                <v-icon
                  :icon="boxIcon(coverage(modelValue, cat, src.name))"
                  :color="coverage(modelValue, cat, src.name) === 'none' ? undefined : 'primary'"
                  size="small"
                  class="box"
                  @click.stop="emitToggle(cat, src.name)"
                />
                <span class="label">{{ src.display_name }}</span>
                <span class="count">{{ src.count }}</span>
              </div>

              <!-- ── Attack types — divider-separated ── -->
              <template v-if="isExpanded(srcKey(cat.category, src.name)) && src.subcategories.length">
                <div class="subs">
                  <template v-for="(sub, i) in visibleSubs(cat, src)" :key="sub.name">
                    <v-divider v-if="i > 0" class="sub-divider" />
                    <div class="node node--sub">
                      <span class="chev-spacer" />
                      <v-icon
                        :icon="boxIcon(coverage(modelValue, cat, src.name, sub.name))"
                        :color="coverage(modelValue, cat, src.name, sub.name) === 'none' ? undefined : 'primary'"
                        size="small"
                        class="box"
                        @click.stop="emitToggle(cat, src.name, sub.name)"
                      />
                      <span class="label">{{ sub.name }}</span>
                      <span class="count">{{ sub.count }}</span>
                    </div>
                  </template>
                </div>
              </template>
            </template>
          </template>
        </template>

        <div v-if="visibleCategories.length === 0" class="muted pa-6 text-center">No threats match “{{ search }}”.</div>
      </div>
    </v-card>
  </v-menu>
</template>

<script setup lang="ts">
import type { CategoryInfo, SourceInfo, SubcategoryInfo } from '~/services/benchmarkService'
import { humanCategory, humanPack } from '~/utils/redTeamLabels'
import {
  type Coverage,
  buildFilters,
  catKey,
  coverage,
  srcKey,
  toggle,
} from '~/utils/attackSelection'

const props = defineProps<{
  categories: CategoryInfo[]
  modelValue: Set<string>
}>()
const emit = defineEmits<{ 'update:modelValue': [Set<string>] }>()

const open = ref(false)
const search = ref('')
const expanded = ref<Set<string>>(new Set())
const fieldRef = ref<HTMLElement | null>(null)
const menuWidth = ref<number | undefined>(undefined)

function syncWidth(): void {
  menuWidth.value = fieldRef.value?.offsetWidth
}

const q = computed(() => (search.value || '').trim().toLowerCase())
const searching = computed(() => q.value.length > 0)

// ── Selected chips (minimal: one per topmost-checked node) ──
const chips = computed(() =>
  buildFilters(props.modelValue, props.categories).map((f) => {
    let label = humanCategory(f.category!)
    if (f.subcategory) label = `${humanCategory(f.category!)} · ${humanPack(f.pack!)} · ${f.subcategory}`
    else if (f.pack) label = `${humanCategory(f.category!)} · ${humanPack(f.pack!)}`
    return { key: `${f.category}|${f.pack ?? ''}|${f.subcategory ?? ''}`, filter: f, label }
  }).sort((a, b) => a.label.localeCompare(b.label)),
)
function removeChip(filter: { category?: string, pack?: string, subcategory?: string }): void {
  const cat = props.categories.find((c) => c.category === filter.category)
  if (cat) emit('update:modelValue', toggle(props.modelValue, cat, filter.pack, filter.subcategory))
}

function emitToggle(cat: CategoryInfo, pack?: string, sub?: string): void {
  emit('update:modelValue', toggle(props.modelValue, cat, pack, sub))
}

function toggleExpand(key: string): void {
  const next = new Set(expanded.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  expanded.value = next
}
function isExpanded(key: string): boolean {
  return searching.value || expanded.value.has(key)
}
function expandIcon(key: string): string {
  return isExpanded(key) ? 'mdi-chevron-down' : 'mdi-chevron-right'
}

function boxIcon(cov: Coverage): string {
  if (cov === 'checked') return 'mdi-checkbox-marked'
  if (cov === 'indeterminate') return 'mdi-minus-box'
  return 'mdi-checkbox-blank-outline'
}

// ── Search filtering (matches at any level; parents shown if a child matches) ──
function subMatches(sub: SubcategoryInfo): boolean {
  return !searching.value || sub.name.toLowerCase().includes(q.value)
}
function srcMatches(cat: CategoryInfo, src: SourceInfo): boolean {
  if (!searching.value) return true
  return src.display_name.toLowerCase().includes(q.value)
    || src.name.toLowerCase().includes(q.value)
    || humanCategory(cat.category).toLowerCase().includes(q.value)
    || src.subcategories.some((s) => s.name.toLowerCase().includes(q.value))
}
function catMatches(cat: CategoryInfo): boolean {
  if (!searching.value) return true
  return humanCategory(cat.category).toLowerCase().includes(q.value)
    || cat.sources.some((s) => srcMatches(cat, s))
}

const visibleCategories = computed(() => props.categories.filter(catMatches))
function visibleSources(cat: CategoryInfo): SourceInfo[] {
  return cat.sources.filter((s) => srcMatches(cat, s))
}
function visibleSubs(cat: CategoryInfo, src: SourceInfo): SubcategoryInfo[] {
  if (!searching.value || humanCategory(cat.category).toLowerCase().includes(q.value)
    || src.display_name.toLowerCase().includes(q.value)) return src.subcategories
  return src.subcategories.filter(subMatches)
}
</script>

<style lang="scss" scoped>
.field {
  display: flex;
  align-items: center;
  min-height: 52px;
  padding: 4px 8px 4px 12px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 6px;
  cursor: pointer;
  transition: border-color 0.15s ease;
  &:hover { border-color: rgba(var(--v-theme-on-surface), 0.4); }
  &--open { border-color: rgb(var(--v-theme-primary)); }
}
.field-content {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  flex: 1 1 auto;
  min-width: 0;
}
.placeholder { opacity: 0.6; font-size: 0.9rem; padding: 6px 0; }
.field-chevron { opacity: 0.6; flex-shrink: 0; }

.menu-card { overflow: hidden; }
.tree-scroll { max-height: 360px; overflow-y: auto; }
.node {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  cursor: pointer;
  user-select: none;
  &:hover { background: rgba(var(--v-theme-on-surface), 0.04); }
}
.node--cat { font-weight: 600; }
.node--src { padding-left: 34px; }
.node--sub { padding-left: 62px; }
.subs { background: rgba(var(--v-theme-on-surface), 0.02); }
.sub-divider { margin-left: 62px; opacity: 0.4; }
.chev { opacity: 0.7; }
.chev-spacer { display: inline-block; width: 18px; }
.box { cursor: pointer; }
.label { font-size: 0.875rem; }
.label--strong { font-weight: 600; }
.count { font-size: 0.72rem; opacity: 0.6; margin-left: 8px; }
.muted { font-size: 0.8rem; opacity: 0.6; }
</style>
