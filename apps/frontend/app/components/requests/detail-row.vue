<template>
  <div class="detail-row-wrapper">
    <div v-if="loading" class="text-center py-4">
      <v-progress-circular indeterminate color="primary" size="24" />
      <p class="text-caption text-medium-emphasis mt-1">Loading details…</p>
    </div>

    <template v-else-if="detail">
      <!-- ═══ Hero: Prompt + Verdict ═══ -->
      <div class="detail-hero mb-3">
        <div class="d-flex align-start ga-3">
          <!-- Verdict badge -->
          <div class="verdict-badge flex-shrink-0" :class="`verdict-${detail.decision?.toLowerCase()}`">
            <v-icon :icon="verdictIcon" size="18" />
            <span class="text-caption font-weight-bold">{{ detail.decision }}</span>
          </div>
          <!-- Prompt -->
          <div class="flex-grow-1" style="min-width: 0;">
            <div v-if="detail.prompt_preview" class="prompt-preview-box">
              <span class="text-body-2" style="white-space: pre-wrap; word-break: break-word;">{{ detail.prompt_preview }}</span>
            </div>
            <div v-if="detail.blocked_reason" class="blocked-reason mt-2">
              <v-icon icon="mdi-shield-alert" size="14" class="mr-1" />
              <span class="text-caption font-weight-medium">{{ detail.blocked_reason }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- ═══ Two-column layout ═══ -->
      <v-row dense>
        <!-- LEFT: Human-readable summary -->
        <v-col cols="12" md="5">
          <!-- Risk Flags -->
          <div class="detail-section">
            <div class="section-title">
              <v-icon icon="mdi-flag-outline" size="14" class="mr-1" />
              Risk Flags
            </div>
            <div v-if="flagEntries.length" class="d-flex flex-wrap ga-1">
              <v-chip
                v-for="[key, val] in flagEntries"
                :key="key"
                :color="flagColor(key, val)"
                variant="tonal"
                size="x-small"
                label
              >
                {{ formatKey(key) }}: {{ formatVal(val) }}
              </v-chip>
            </div>
            <span v-else class="text-caption text-medium-emphasis">No flags raised</span>
          </div>

          <!-- Pipeline Timing -->
          <div v-if="timingEntries.length" class="detail-section">
            <div class="section-title">
              <v-icon icon="mdi-timer-outline" size="14" class="mr-1" />
              Pipeline Timing
              <span class="text-caption text-medium-emphasis ml-1">({{ totalTiming }}ms total)</span>
            </div>
            <div class="timing-grid">
              <template v-for="[node, ms] in timingEntries" :key="node">
                <span class="timing-label text-caption">{{ formatKey(node) }}</span>
                <div class="timing-bar-wrapper">
                  <div
                    class="timing-bar"
                    :style="{ width: `${Math.max(4, (ms as number) / maxTiming * 100)}%` }"
                    :class="timingBarColor(ms as number)"
                  />
                </div>
                <span class="timing-value text-caption font-weight-bold">{{ ms }}ms</span>
              </template>
            </div>
          </div>

          <!-- Metadata -->
          <div class="detail-section metadata-row">
            <div class="d-flex flex-wrap ga-2 align-center">
              <v-chip v-if="detail.model_used" size="x-small" variant="outlined" label prepend-icon="mdi-brain">
                {{ detail.model_used }}
              </v-chip>
              <v-chip v-if="detail.tokens_in != null" size="x-small" variant="outlined" label prepend-icon="mdi-counter">
                {{ detail.tokens_in }}→{{ detail.tokens_out ?? '?' }}
              </v-chip>
              <v-chip v-if="detail.prompt_hash" size="x-small" variant="outlined" label prepend-icon="mdi-pound">
                {{ detail.prompt_hash.slice(0, 10) }}…
              </v-chip>
              <v-chip v-if="detail.response_masked" size="x-small" variant="tonal" label color="warning" prepend-icon="mdi-eye-off">
                Masked
              </v-chip>
            </div>
          </div>
        </v-col>

        <!-- RIGHT: Technical evidence -->
        <v-col cols="12" md="7">
          <!-- Scanner Results (summary-first) -->
          <div class="detail-section">
            <div class="section-title">
              <v-icon icon="mdi-shield-search" size="14" class="mr-1" />
              Scanner Results
            </div>
            <template v-if="scannerEntries.length">
              <div class="scanner-cards">
                <div
                  v-for="[scanner, result] in scannerEntries"
                  :key="scanner"
                  class="scanner-card"
                  :class="{ 'scanner-card--flagged': getScannerStatus(result) === 'flagged' }"
                >
                  <div class="d-flex align-center justify-space-between mb-1">
                    <span class="text-caption font-weight-bold">{{ formatKey(scanner) }}</span>
                    <v-chip
                      :color="getScannerStatus(result) === 'flagged' ? 'error' : 'success'"
                      size="x-small"
                      variant="tonal"
                      label
                    >
                      {{ getScannerStatus(result) === 'flagged' ? 'Flagged' : 'Pass' }}
                    </v-chip>
                  </div>
                  <div class="d-flex align-center ga-3 text-caption text-medium-emphasis">
                    <span v-if="getScannerScore(result) != null">
                      Score: <strong>{{ getScannerScore(result)!.toFixed(2) }}</strong>
                    </span>
                    <span v-if="getScannerFinding(result)">
                      {{ getScannerFinding(result) }}
                    </span>
                  </div>
                  <!-- Expandable raw JSON -->
                  <v-expand-transition>
                    <div v-if="expandedScanners[scanner]">
                      <pre class="scanner-raw mt-2">{{ JSON.stringify(result, null, 2) }}</pre>
                    </div>
                  </v-expand-transition>
                  <button
                    class="scanner-toggle text-caption"
                    @click="toggleScanner(scanner)"
                  >
                    {{ expandedScanners[scanner] ? 'Hide' : 'Show' }} raw data
                    <v-icon :icon="expandedScanners[scanner] ? 'mdi-chevron-up' : 'mdi-chevron-down'" size="12" />
                  </button>
                </div>
              </div>
            </template>
            <span v-else class="text-caption text-medium-emphasis">No scanner results</span>
          </div>

          <!-- Output Filter -->
          <div v-if="detail.output_filter_results && Object.keys(detail.output_filter_results).length" class="detail-section">
            <div class="section-title">
              <v-icon icon="mdi-filter-check-outline" size="14" class="mr-1" />
              Output Filter
            </div>
            <div class="scanner-card">
              <div class="d-flex align-center justify-space-between mb-1">
                <span class="text-caption font-weight-bold">Filter Results</span>
                <v-chip size="x-small" variant="tonal" label color="info">Applied</v-chip>
              </div>
              <v-expand-transition>
                <div v-if="expandedOutput">
                  <pre class="scanner-raw mt-2">{{ JSON.stringify(detail.output_filter_results, null, 2) }}</pre>
                </div>
              </v-expand-transition>
              <button class="scanner-toggle text-caption" @click="expandedOutput = !expandedOutput">
                {{ expandedOutput ? 'Hide' : 'Show' }} raw data
                <v-icon :icon="expandedOutput ? 'mdi-chevron-up' : 'mdi-chevron-down'" size="12" />
              </button>
            </div>
          </div>
        </v-col>
      </v-row>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { RequestDetail } from '~/types/api'
import { decisionIcon, flagColor as _flagColor } from '~/utils/colors'

const props = defineProps<{
  detail: RequestDetail | null
  loading: boolean
}>()

const expandedScanners = ref<Record<string, boolean>>({})
const expandedOutput = ref(false)

function toggleScanner(key: string) {
  expandedScanners.value[key] = !expandedScanners.value[key]
}

const verdictIcon = computed(() => decisionIcon(props.detail?.decision))

const flagEntries = computed(() =>
  Object.entries(props.detail?.risk_flags ?? {}),
)

const scannerEntries = computed(() =>
  Object.entries(props.detail?.scanner_results ?? {}),
)

const timingEntries = computed(() =>
  Object.entries(props.detail?.node_timings ?? {}).sort(
    ([, a], [, b]) => (b as number) - (a as number),
  ),
)

const maxTiming = computed(() =>
  Math.max(1, ...timingEntries.value.map(([, v]) => v as number)),
)

const totalTiming = computed(() =>
  timingEntries.value.reduce((sum, [, v]) => sum + (v as number), 0),
)

function formatKey(key: string) {
  return key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function formatVal(val: unknown): string {
  if (typeof val === 'boolean') return val ? 'Yes' : 'No'
  if (typeof val === 'number') return val.toFixed(2)
  if (Array.isArray(val)) return val.join(', ')
  return String(val)
}

function flagColor(key: string, val: unknown): string {
  return _flagColor(key, val)
}

function timingBarColor(ms: number): string {
  if (ms < 20) return 'bar-fast'
  if (ms < 100) return 'bar-medium'
  return 'bar-slow'
}

function getScannerStatus(result: unknown): 'flagged' | 'pass' {
  if (result == null) return 'pass'
  if (typeof result === 'object') {
    const r = result as Record<string, unknown>
    if (r.flagged === true || r.detected === true || r.is_blocked === true) return 'flagged'
    if (typeof r.score === 'number' && r.score > 0.5) return 'flagged'
    if (typeof r.risk_score === 'number' && r.risk_score > 0.5) return 'flagged'
    if (r.result === 'BLOCK' || r.decision === 'BLOCK') return 'flagged'
    if (r.matched === true) return 'flagged'
  }
  return 'pass'
}

function getScannerScore(result: unknown): number | null {
  if (result == null || typeof result !== 'object') return null
  const r = result as Record<string, unknown>
  if (typeof r.score === 'number') return r.score
  if (typeof r.risk_score === 'number') return r.risk_score
  if (typeof r.confidence === 'number') return r.confidence
  return null
}

function getScannerFinding(result: unknown): string | null {
  if (result == null || typeof result !== 'object') return null
  const r = result as Record<string, unknown>
  if (typeof r.reason === 'string') return r.reason
  if (typeof r.match === 'string') return `Match: ${r.match}`
  if (typeof r.category === 'string') return r.category
  if (typeof r.message === 'string') return r.message
  if (typeof r.label === 'string') return r.label
  if (Array.isArray(r.matches) && r.matches.length) return `${r.matches.length} match(es)`
  if (Array.isArray(r.entities) && r.entities.length) return `${r.entities.length} entit(ies)`
  return null
}
</script>

<style lang="scss" scoped>
.detail-row-wrapper {
  padding: 12px 16px 8px;
  background: rgba(var(--v-theme-on-surface), 0.02);
  border-top: 1px solid rgba(var(--v-theme-on-surface), 0.06);
}

/* ─── Hero: Prompt + Verdict ─── */
.detail-hero {
  padding: 10px 12px;
  background: rgba(var(--v-theme-on-surface), 0.03);
  border-radius: 8px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.06);
}

.verdict-badge {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 8px 10px;
  border-radius: 8px;
  min-width: 60px;
}
.verdict-block { background: rgba(var(--v-theme-error), 0.12); color: rgb(var(--v-theme-error)); }
.verdict-modify { background: rgba(var(--v-theme-warning), 0.12); color: rgb(var(--v-theme-warning)); }
.verdict-allow { background: rgba(var(--v-theme-success), 0.12); color: rgb(var(--v-theme-success)); }

.prompt-preview-box {
  padding: 8px 10px;
  background: rgba(var(--v-theme-on-surface), 0.04);
  border-radius: 6px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.06);
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 12.5px;
  line-height: 1.5;
  max-height: 100px;
  overflow-y: auto;
}

.blocked-reason {
  display: flex;
  align-items: center;
  color: rgb(var(--v-theme-error));
  font-size: 12px;
}

/* ─── Sections ─── */
.detail-section {
  margin-bottom: 12px;
}
.section-title {
  display: flex;
  align-items: center;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  color: rgba(var(--v-theme-on-surface), 0.5);
  margin-bottom: 6px;
}

/* ─── Pipeline Timing ─── */
.timing-grid {
  display: grid;
  grid-template-columns: minmax(100px, auto) 1fr 50px;
  gap: 3px 8px;
  align-items: center;
}
.timing-label {
  color: rgba(var(--v-theme-on-surface), 0.7);
  font-size: 11.5px;
}
.timing-bar-wrapper {
  height: 6px;
  background: rgba(var(--v-theme-on-surface), 0.06);
  border-radius: 3px;
  overflow: hidden;
}
.timing-bar {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s ease;
}
.bar-fast { background: rgb(var(--v-theme-success)); }
.bar-medium { background: rgb(var(--v-theme-primary)); }
.bar-slow { background: rgb(var(--v-theme-warning)); }

.timing-value {
  text-align: right;
  font-size: 11px;
  color: rgba(var(--v-theme-on-surface), 0.8);
}

/* ─── Scanner Cards ─── */
.scanner-cards {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.scanner-card {
  padding: 8px 10px;
  border-radius: 6px;
  background: rgba(var(--v-theme-on-surface), 0.03);
  border: 1px solid rgba(var(--v-theme-on-surface), 0.06);
  transition: border-color 0.15s;
}
.scanner-card--flagged {
  border-color: rgba(var(--v-theme-error), 0.25);
  background: rgba(var(--v-theme-error), 0.03);
}

.scanner-toggle {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  margin-top: 4px;
  color: rgba(var(--v-theme-primary), 0.8);
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
  font-size: 11px;
  &:hover { text-decoration: underline; }
}

.scanner-raw {
  padding: 6px 8px;
  background: rgba(var(--v-theme-on-surface), 0.05);
  border-radius: 4px;
  font-size: 11px;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 150px;
  overflow-y: auto;
  margin: 0;
}

/* ─── Metadata ─── */
.metadata-row {
  padding-top: 4px;
}

:deep(.v-chip) {
  font-size: 12px !important;
}
</style>
