<template>
  <v-card variant="outlined" class="pa-4">
    <div v-if="loading" class="text-center py-4">
      <v-progress-circular indeterminate color="primary" />
      <p class="text-body-2 text-medium-emphasis mt-2">Loading details…</p>
    </div>

    <template v-else-if="detail">
      <!-- Prompt Preview -->
      <div class="mb-4" v-if="detail.prompt_preview">
        <div class="text-overline text-medium-emphasis mb-1">Prompt Preview</div>
        <v-code tag="pre" class="pa-3 text-body-2" style="white-space: pre-wrap; word-break: break-word;">{{ detail.prompt_preview }}</v-code>
      </div>

      <!-- Blocked Reason -->
      <v-alert
        v-if="detail.blocked_reason"
        type="error"
        variant="tonal"
        density="compact"
        class="mb-4"
      >
        <strong>Blocked:</strong> {{ detail.blocked_reason }}
      </v-alert>

      <v-row>
        <!-- Risk Flags -->
        <v-col cols="12" md="6">
          <div class="text-overline text-medium-emphasis mb-2">Risk Flags</div>
          <div v-if="flagEntries.length" class="d-flex flex-wrap ga-2">
            <v-chip
              v-for="[key, val] in flagEntries"
              :key="key"
              :color="flagColor(key, val)"
              variant="tonal"
              size="small"
            >
              {{ formatKey(key) }}: {{ formatVal(val) }}
            </v-chip>
          </div>
          <span v-else class="text-body-2 text-medium-emphasis">None</span>
        </v-col>

        <!-- Scanner Results -->
        <v-col cols="12" md="6">
          <div class="text-overline text-medium-emphasis mb-2">Scanner Results</div>
          <template v-if="scannerEntries.length">
            <div v-for="[scanner, result] in scannerEntries" :key="scanner" class="mb-2">
              <div class="text-caption font-weight-bold">{{ formatKey(scanner) }}</div>
              <pre class="text-caption pa-2 bg-surface-variant rounded" style="white-space: pre-wrap; max-height: 120px; overflow-y: auto;">{{ JSON.stringify(result, null, 2) }}</pre>
            </div>
          </template>
          <span v-else class="text-body-2 text-medium-emphasis">None</span>
        </v-col>
      </v-row>

      <v-row class="mt-2">
        <!-- Node Timings -->
        <v-col cols="12" md="6">
          <div class="text-overline text-medium-emphasis mb-2">Node Timings</div>
          <template v-if="timingEntries.length">
            <div v-for="[node, ms] in timingEntries" :key="node" class="d-flex align-center mb-1">
              <span class="text-caption" style="min-width: 120px;">{{ formatKey(node) }}</span>
              <v-progress-linear
                :model-value="(ms as number) / maxTiming * 100"
                color="primary"
                height="8"
                rounded
                style="max-width: 200px;"
                class="mr-2"
              />
              <span class="text-caption font-weight-bold">{{ ms }}ms</span>
            </div>
          </template>
          <span v-else class="text-body-2 text-medium-emphasis">None</span>
        </v-col>

        <!-- Output Filter -->
        <v-col cols="12" md="6">
          <div class="text-overline text-medium-emphasis mb-2">Output Filter</div>
          <template v-if="detail.output_filter_results && Object.keys(detail.output_filter_results).length">
            <pre class="text-caption pa-2 bg-surface-variant rounded" style="white-space: pre-wrap; max-height: 120px; overflow-y: auto;">{{ JSON.stringify(detail.output_filter_results, null, 2) }}</pre>
          </template>
          <span v-else class="text-body-2 text-medium-emphasis">None</span>
        </v-col>
      </v-row>

      <!-- Metadata -->
      <v-divider class="my-3" />
      <div class="d-flex flex-wrap ga-3 text-caption text-medium-emphasis">
        <span v-if="detail.model_used">Model: <strong>{{ detail.model_used }}</strong></span>
        <span v-if="detail.tokens_in != null">Tokens: {{ detail.tokens_in }}→{{ detail.tokens_out ?? '?' }}</span>
        <span v-if="detail.prompt_hash">Hash: {{ detail.prompt_hash.slice(0, 12) }}…</span>
        <span v-if="detail.response_masked">
          <v-icon size="14" icon="mdi-eye-off" class="mr-1" />Masked
        </span>
      </div>
    </template>
  </v-card>
</template>

<script setup lang="ts">
import type { RequestDetail } from '~/types/api'

const props = defineProps<{
  detail: RequestDetail | null
  loading: boolean
}>()

const flagEntries = computed(() =>
  Object.entries(props.detail?.risk_flags ?? {}),
)

const scannerEntries = computed(() =>
  Object.entries(props.detail?.scanner_results ?? {}),
)

const timingEntries = computed(() =>
  Object.entries(props.detail?.node_timings ?? {}).sort(
    ([, a], [, b]) => (a as number) - (b as number),
  ),
)

const maxTiming = computed(() =>
  Math.max(1, ...timingEntries.value.map(([, v]) => v as number)),
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
  if (key.includes('injection') || key === 'promptinjection') return 'error'
  if (key.includes('pii')) return 'warning'
  if (key.includes('toxicity')) return 'orange'
  if (key.includes('denylist') || key.includes('custom')) return 'error'
  if (val === true || (typeof val === 'number' && val > 0.5)) return 'warning'
  return 'grey'
}
</script>
