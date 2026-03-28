<template>
  <v-card variant="flat" class="target-form pa-6">
    <h2 class="text-h6 mb-1">Your AI Endpoint</h2>
    <p class="text-body-2 text-medium-emphasis mb-4">
      Enter your endpoint URL, test the connection, then run a security benchmark.
    </p>

    <v-form ref="formRef" v-model="formValid" @submit.prevent>
      <!-- ===== STEP 1: Connection ===== -->

      <!-- Endpoint URL (required) -->
      <v-text-field
        v-model="endpointUrl"
        label="Endpoint URL"
        :placeholder="'https://your-api.example.com/chat'"
        hint="e.g. https://staging.myapp.com/api/chat or http://localhost:8000/chat"
        persistent-hint
        :rules="[rules.required, rules.url]"
        variant="outlined"
        density="compact"
        class="mb-3"
        data-testid="endpoint-url"
      />

      <!-- Custom Headers — dynamic key:value list -->
      <div class="mb-3">
        <p class="text-body-2 font-weight-medium mb-2">Request Headers (optional)</p>
        <div
          v-for="(header, idx) in customHeaders"
          :key="idx"
          class="d-flex align-center ga-2 mb-2"
        >
          <v-text-field
            v-model="header.name"
            label="Header name"
            placeholder="Authorization"
            variant="outlined"
            density="compact"
            hide-details
            style="max-width: 200px"
          />
          <v-text-field
            v-model="header.value"
            label="Value"
            :placeholder="header.name?.toLowerCase() === 'authorization' ? 'Bearer sk-...' : ''"
            variant="outlined"
            density="compact"
            hide-details
            :type="showAuth ? 'text' : 'password'"
            class="flex-grow-1"
          />
          <v-btn
            icon="mdi-close"
            size="small"
            variant="text"
            @click="customHeaders.splice(idx, 1)"
          />
        </div>
        <v-btn
          variant="tonal"
          size="small"
          prepend-icon="mdi-plus"
          @click="customHeaders.push({ name: '', value: '' })"
        >
          Add Header
        </v-btn>
        <v-btn
          v-if="customHeaders.length > 0"
          variant="text"
          size="small"
          :icon="showAuth ? 'mdi-eye-off' : 'mdi-eye'"
          class="ml-2"
          @click="showAuth = !showAuth"
        />
      </div>

      <!-- Localhost reachability hint -->
      <v-alert
        v-if="isLocalhostUrl"
        type="info"
        variant="tonal"
        density="compact"
        class="mb-4"
      >
        <span class="text-caption">
          Localhost URLs are automatically routed to your host machine.
          For remote environments use a public URL or tunnel (e.g. ngrok).
        </span>
      </v-alert>

      <!-- Test Connection -->
      <div class="d-flex align-center mb-4">
        <v-btn
          variant="outlined"
          prepend-icon="mdi-connection"
          :loading="isTesting"
          :disabled="!endpointUrl"
          data-testid="test-connection-btn"
          @click="onTestConnection"
        >
          Test Connection
        </v-btn>
      </div>

      <!-- Connection result banner -->
      <v-alert
        v-if="connectionResult"
        :type="connectionResult.type"
        variant="tonal"
        density="compact"
        class="mb-4"
        data-testid="connection-result"
      >
        <template #prepend>
          <v-icon
            :icon="connectionResult.type === 'success' ? 'mdi-check-circle' : 'mdi-close-circle'"
            size="small"
          />
        </template>
        <strong>{{ connectionResult.headline }}</strong>
        <template v-if="connectionResult.type === 'error'">
          <p class="text-body-2 mb-1 mt-1">{{ connectionResult.message }}</p>
          <p class="text-caption text-medium-emphasis mb-0">
            Check the URL, auth header, and whether the endpoint is reachable from AI Protector.
          </p>
        </template>
        <template v-else>
          {{ connectionResult.message }}
        </template>
      </v-alert>

      <!-- Non-JSON warning -->
      <v-alert
        v-if="nonJsonWarning"
        type="warning"
        variant="tonal"
        density="compact"
        class="mb-4"
        data-testid="non-json-warning"
      >
        Endpoint returned {{ nonJsonContentType }} instead of JSON.
        Some checks may be less accurate. You can still continue.
      </v-alert>

      <!-- ===== STEP 2: Benchmark Settings (only after successful connection) ===== -->
      <template v-if="connectionPassed">
        <v-divider class="my-4" />

        <div class="text-center mb-4">
          <v-icon icon="mdi-check-circle" color="success" size="32" class="mb-2" />
          <p class="text-body-2 font-weight-medium text-success mb-1">Connection successful</p>
          <p class="text-caption text-medium-emphasis mb-0">Your endpoint is reachable. Choose a benchmark to run.</p>
        </div>

        <!-- Safety notice — compact, less alarming -->
        <v-alert
          type="info"
          variant="tonal"
          density="compact"
          class="mb-4"
          data-testid="safety-notice"
        >
          These tests send realistic attack prompts. Use Safe Mode for endpoints connected to real tools or actions.
        </v-alert>

        <!-- Continue button -->
        <v-btn
          color="primary"
          size="large"
          block
          data-testid="continue-btn"
          prepend-icon="mdi-arrow-right"
          @click="onContinue"
        >
          Continue to Benchmark
        </v-btn>

        <!-- Advanced section — collapsed, below the CTA -->
        <v-expansion-panels v-model="advancedPanel" class="mt-4 mb-4" variant="accordion">
          <v-expansion-panel value="advanced">
            <v-expansion-panel-title>
              <v-icon icon="mdi-tune" size="small" class="mr-2" />
              Advanced Settings
            </v-expansion-panel-title>
            <v-expansion-panel-text>
              <!-- Target name (optional) — hidden from initial view -->
              <v-text-field
                v-model="targetName"
                label="Target Name (optional)"
                placeholder="My Agent"
                hint="Auto-generated from URL if left empty"
                persistent-hint
                variant="outlined"
                density="compact"
                class="mb-3"
              />

              <!-- Type — hidden from initial view -->
              <p class="text-body-2 font-weight-medium mb-1">What does this endpoint do?</p>
              <v-radio-group v-model="agentType" inline density="compact" class="mb-3" data-testid="agent-type">
                <v-radio label="Chatbot / API" value="chatbot_api" />
                <v-radio label="Tool-calling Agent" value="tool_calling" />
              </v-radio-group>

              <!-- Request timeout -->
              <v-select
                v-model="timeoutS"
                :items="timeoutOptions"
                item-title="label"
                item-value="value"
                label="Request Timeout"
                variant="outlined"
                density="compact"
                class="mb-3"
              />

              <!-- Safe mode -->
              <div class="d-flex align-center mb-3">
                <v-switch
                  v-model="safeMode"
                  color="primary"
                  density="compact"
                  hide-details
                  class="mr-2"
                  data-testid="safe-mode-toggle"
                >
                  <template #label>
                    Safe Mode
                    <v-chip v-if="safeMode" size="x-small" color="primary" variant="tonal" class="ml-2">On</v-chip>
                  </template>
                </v-switch>
                <v-tooltip text="Skips prompts that could trigger write/delete/transfer actions on your system.">
                  <template #activator="{ props: tp }">
                    <v-icon v-bind="tp" icon="mdi-help-circle-outline" size="small" />
                  </template>
                </v-tooltip>
              </div>
              <p class="text-caption text-medium-emphasis mb-3">
                Use Safe Mode when your endpoint can trigger real tools or actions.
              </p>

              <!-- Environment (Hosted only) -->
              <template v-if="isHosted">
                <p class="text-body-2 font-weight-medium mb-1">Environment</p>
                <p class="text-caption text-medium-emphasis mb-2">Used for reporting only — does not affect the benchmark.</p>
                <v-radio-group v-model="environment" inline density="compact" class="mb-3">
                  <v-radio label="Staging" value="staging" />
                  <v-radio label="Internal" value="internal" />
                  <v-radio label="Production-like" value="production_like" />
                  <v-radio label="Other" value="other" />
                </v-radio-group>
              </template>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
      </template>

      <!-- Before connection: disabled continue button hint -->
      <v-btn
        v-if="!connectionPassed"
        color="primary"
        size="large"
        block
        disabled
        class="mt-2"
      >
        Test connection first
      </v-btn>
    </v-form>
  </v-card>
</template>

<script setup lang="ts">
import { api } from '~/services/api'

interface Props {
  targetType: 'local_agent' | 'hosted_endpoint'
}

const props = defineProps<Props>()
const emit = defineEmits<{
  continue: [config: TargetFormConfig]
}>()

export interface TargetFormConfig {
  target_type: string
  endpoint_url: string
  target_name: string
  custom_headers: Record<string, string>
  agent_type: string
  timeout_s: number
  safe_mode: boolean
  environment: string
}

const isHosted = computed(() => props.targetType === 'hosted_endpoint')

/** Detect localhost URLs to show reachability hint */
const isLocalhostUrl = computed(() => {
  try {
    const u = new URL(endpointUrl.value)
    return ['localhost', '127.0.0.1', '0.0.0.0', '::1'].includes(u.hostname)
  } catch {
    return false
  }
})

// Form state
const formRef = ref()
const formValid = ref(false)
const endpointUrl = ref('')
const targetName = ref('')
const customHeaders = ref<Array<{ name: string; value: string }>>([{ name: 'Authorization', value: '' }])
const showAuth = ref(false)
const agentType = ref('chatbot_api')
const timeoutS = ref(30)
const safeMode = ref(true) // Default ON for safety
const environment = ref('staging')
const advancedPanel = ref<string | undefined>(undefined)

// Connection test state
const isTesting = ref(false)
const connectionPassed = ref(false)
const connectionResult = ref<{ type: 'success' | 'error'; headline: string; message: string } | null>(null)
const nonJsonWarning = ref(false)
const nonJsonContentType = ref('')

const timeoutOptions = [
  { label: '10 seconds', value: 10 },
  { label: '30 seconds (default)', value: 30 },
  { label: '60 seconds', value: 60 },
  { label: '120 seconds', value: 120 },
]

const rules = {
  required: (v: string) => !!v?.trim() || 'Required',
  url: (v: string) => {
    if (!v) return true
    try {
      const u = new URL(v)
      return ['http:', 'https:'].includes(u.protocol) || 'Must be http:// or https:// URL'
    } catch {
      return 'Invalid URL format'
    }
  },
}

// Connection gating — benchmark settings only show after successful test

function humanizeConnectionError(raw?: string | null, statusCode?: number): string {
  const msg = (raw ?? '').toLowerCase()
  if (msg.includes('timeout') || msg.includes('timed out')) return 'Request timed out — the endpoint did not respond in time'
  if (msg.includes('401') || statusCode === 401) return 'Authorization failed — check your auth header'
  if (msg.includes('403') || statusCode === 403) return 'Access denied (403) — verify credentials and permissions'
  if (msg.includes('404') || statusCode === 404) return 'Endpoint not found (404) — check the URL path'
  if (statusCode && statusCode >= 500) return `Server error (HTTP ${statusCode}) — the endpoint returned an error`
  if (statusCode && statusCode >= 400) return `Client error (HTTP ${statusCode}) — the endpoint rejected the request`
  if (msg.includes('connection refused') || msg.includes('econnrefused')) return 'Connection refused — is the endpoint running?'
  if (msg.includes('dns') || msg.includes('getaddrinfo') || msg.includes('not found')) return 'Could not resolve hostname — check the URL'
  if (msg.includes('ssl') || msg.includes('certificate')) return 'SSL/TLS error — the endpoint has a certificate problem'
  if (msg.includes('network') || msg.includes('fetch')) return 'Network error — could not reach the endpoint'
  if (raw) return raw
  return 'Couldn\u2019t reach the endpoint'
}

async function onTestConnection() {
  isTesting.value = true
  connectionResult.value = null
  nonJsonWarning.value = false
  connectionPassed.value = false

  try {
    const res = await api.post<{
      status: string
      status_code?: number
      latency_ms?: number
      content_type?: string
      error?: string
      resolved_url?: string
    }>('/v1/benchmark/test-connection', {
      endpoint_url: endpointUrl.value,
      custom_headers: buildHeadersDict(),
      timeout_s: timeoutS.value,
    })

    const data = res.data
    if (data.status === 'ok') {
      connectionPassed.value = true
      const resolvedNote = data.resolved_url
        ? ` (routed via ${data.resolved_url})`
        : ''
      connectionResult.value = {
        type: 'success',
        headline: 'Connection successful',
        message: `HTTP ${data.status_code} in ${data.latency_ms}ms${resolvedNote}`,
      }
      // Check for non-JSON
      if (data.content_type && !data.content_type.includes('json')) {
        nonJsonWarning.value = true
        nonJsonContentType.value = data.content_type
      }
    } else {
      connectionResult.value = {
        type: 'error',
        headline: 'Couldn\u2019t reach the endpoint',
        message: humanizeConnectionError(data.error, data.status_code),
      }
    }
  } catch (err: unknown) {
    const raw = (err as { message?: string })?.message ?? ''
    connectionResult.value = {
      type: 'error',
      headline: 'Couldn\u2019t reach the endpoint',
      message: humanizeConnectionError(raw),
    }
  } finally {
    isTesting.value = false
  }
}

function buildHeadersDict(): Record<string, string> {
  const out: Record<string, string> = {}
  for (const h of customHeaders.value) {
    if (h.name.trim() && h.value.trim()) {
      out[h.name.trim()] = h.value.trim()
    }
  }
  return out
}

function onContinue() {
  emit('continue', {
    target_type: props.targetType,
    endpoint_url: endpointUrl.value,
    target_name: targetName.value,
    custom_headers: buildHeadersDict(),
    agent_type: agentType.value,
    timeout_s: timeoutS.value,
    safe_mode: safeMode.value,
    environment: isHosted.value ? environment.value : '',
  })
}
</script>
