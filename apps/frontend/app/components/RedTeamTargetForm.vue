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
        <div class="d-flex align-center ga-2 mb-1">
          <p class="text-body-2 font-weight-medium mb-0">Request Headers (optional)</p>
          <v-tooltip location="top" max-width="340">
            <template #activator="{ props }">
              <v-icon v-bind="props" icon="mdi-help-circle-outline" size="16" color="medium-emphasis" />
            </template>
            <div class="text-caption">
              Your credentials are stored temporarily only to run the test.
              They are encrypted before storage, used only during benchmark
              execution, never shown in logs or the UI, and automatically
              deleted 24 hours after the run completes.
            </div>
          </v-tooltip>
        </div>
        <p class="text-caption text-medium-emphasis mb-2">
          Add auth headers only if your endpoint requires them. We use them
          only for this benchmark, keep them encrypted, and delete them
          automatically after 24 hours.
        </p>
        <div
          v-for="(header, idx) in customHeaders"
          :key="idx"
          class="d-flex align-center ga-2 mb-4"
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
            :type="header.visible ? 'text' : 'password'"
            class="flex-grow-1"
          />
          <v-btn
            :icon="header.visible ? 'mdi-eye-off' : 'mdi-eye'"
            size="small"
            variant="text"
            @click="header.visible = !header.visible"
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
          @click="customHeaders.push({ name: '', value: '', visible: false })"
        >
          Add Header
        </v-btn>
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
          Requests to localhost are sent from your local AI Protector instance
          running on this machine.
        </span>
      </v-alert>

      <!-- Test request body (JSON, optional) -->
      <div class="mb-4">
        <p class="text-body-2 font-weight-medium mb-1">Test request body (JSON, optional)</p>
        <v-textarea
          v-model="requestTemplate"
          :placeholder="requestTemplatePlaceholder"
          variant="outlined"
          density="compact"
          rows="3"
          auto-grow
          class="font-monospace"
          data-testid="request-template"
        />
        <p class="text-caption text-medium-emphasis mt-n2">
          Use your API's real field names (e.g. Spring: <code>company_id</code>).
          Include <code v-pre>{{PROMPT}}</code> so each attack can be injected;
          same JSON drives the benchmark if you leave the benchmark template empty below.
        </p>
        <v-alert
          v-if="requestTemplate && !requestTemplateHasPlaceholder"
          type="warning"
          variant="tonal"
          density="compact"
          class="mt-2"
          data-testid="template-placeholder-warning"
        >
          Template is missing <code v-pre>{{PROMPT}}</code> placeholder — attack text won't be injected.
        </v-alert>
      </div>

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
            Check the URL, auth header, and test JSON body.
            <template v-if="connectionResult.bodySnippet">
              If the endpoint responded, the box above is its reply (truncated).
            </template>
          </p>
          <pre
            v-if="connectionResult.bodySnippet"
            class="text-caption mt-2 pa-2 rounded bg-surface-variant"
            style="white-space: pre-wrap; word-break: break-all; max-height: 120px; overflow: auto;"
          >{{ connectionResult.bodySnippet }}</pre>
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

        <!-- Response preview -->
        <div v-if="responsePreview" class="mb-4">
          <p class="text-body-2 font-weight-medium mb-1">Endpoint response</p>
          <pre
            class="text-caption pa-3 rounded bg-surface-variant font-monospace"
            style="white-space: pre-wrap; word-break: break-all; max-height: 200px; overflow: auto;"
            data-testid="response-preview"
          >{{ responsePreview }}</pre>
        </div>

        <!-- Auto-detected / manual response path -->
        <div class="mb-4">
          <p class="text-body-2 font-weight-medium mb-1">
            Where is the AI response?
          </p>
          <p class="text-caption text-medium-emphasis mb-2">
            <template v-if="!responsePreview || !isJsonResponse">
              Response is not JSON — the entire body will be used as-is.
            </template>
            <template v-else-if="detectedTextPaths.length">
              Auto-detected from the response above. Edit if the wrong field was picked.
            </template>
            <template v-else>
              Could not auto-detect. Enter the dot-notation path to the AI text field (e.g. <code>data.result.text</code>).
              Use <code>*</code> for array elements.
            </template>
          </p>
          <v-text-field
            v-if="isJsonResponse"
            v-model="responseTextPathsRaw"
            label="Response text path"
            :placeholder="'choices.*.message.content'"
            variant="outlined"
            density="compact"
            class="font-monospace"
            :hint="responseTextPathsRaw.trim()
              ? (detectedTextPaths.length > 1 ? `Other candidates: ${detectedTextPaths.slice(1).join(', ')}` : '')
              : 'Leave empty to scan the entire response body'"
            persistent-hint
            data-testid="response-text-paths"
          />
          <v-chip
            v-if="!isJsonResponse"
            color="info"
            variant="tonal"
            size="small"
            prepend-icon="mdi-text"
          >
            Using full response body (not JSON)
          </v-chip>
        </div>

        <!-- Safety notice -->
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

              <v-divider class="my-4" />
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
  initialEndpointUrl?: string
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
  request_template: string
  response_text_paths: string[]
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
const endpointUrl = ref(props.initialEndpointUrl ?? '')
const targetName = ref('')
const customHeaders = ref<Array<{ name: string; value: string; visible: boolean }>>([{ name: 'Authorization', value: '', visible: false }])
const agentType = ref('chatbot_api')
const timeoutS = ref(60)
const safeMode = ref(true) // Default ON for safety
const environment = ref('staging')
const advancedPanel = ref<string | undefined>(undefined)
const requestTemplatePlaceholder = '{ "user_id": "123", "description": "{{PROMPT}}", "additional_field": [] }'
const requestTemplate = ref('')
const responseTextPathsRaw = ref('')

/** Parsed paths — comma or newline separated */
const responseTextPaths = computed(() =>
  responseTextPathsRaw.value
    .split(/[,\n]/)
    .map((l) => l.trim())
    .filter(Boolean),
)

const requestTemplateHasPlaceholder = computed(() =>
  requestTemplate.value.includes('{{PROMPT}}'),
)

// Connection test state
const isTesting = ref(false)
const connectionPassed = ref(false)
const connectionResult = ref<{ type: 'success' | 'error'; headline: string; message: string; bodySnippet?: string } | null>(null)
const nonJsonWarning = ref(false)
const nonJsonContentType = ref('')
const responsePreview = ref('')
const detectedTextPaths = ref<string[]>([])
const isJsonResponse = ref(false)

const timeoutOptions = [
  { label: '10 seconds', value: 10 },
  { label: '30 seconds', value: 30 },
  { label: '60 seconds (default)', value: 60 },
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
  responsePreview.value = ''
  detectedTextPaths.value = []
  isJsonResponse.value = false

  try {
    // Build custom_body from request template if provided
    let customBody: Record<string, unknown> | undefined
    if (requestTemplate.value.trim()) {
      try {
        const rendered = requestTemplate.value.replace(/\{\{PROMPT}}/g, 'hello')
        customBody = JSON.parse(rendered)
      } catch {
        connectionResult.value = {
          type: 'error',
          headline: 'Invalid JSON in request body',
          message: 'The test request body is not valid JSON. Fix the syntax and try again.',
        }
        isTesting.value = false
        return
      }
    }

    const res = await api.post<{
      status: string
      status_code?: number
      latency_ms?: number
      content_type?: string
      error?: string
      resolved_url?: string
      body_snippet?: string
      response_body?: string
      detected_text_paths?: string[]
    }>('/v1/benchmark/test-connection', {
      endpoint_url: endpointUrl.value,
      custom_headers: buildHeadersDict(),
      timeout_s: timeoutS.value,
      ...(customBody !== undefined && { custom_body: customBody }),
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
        message: `Your endpoint is reachable and ready for benchmarking. HTTP ${data.status_code} in ${data.latency_ms}ms${resolvedNote}`,
      }
      // Populate response preview
      if (data.response_body) {
        responsePreview.value = data.response_body
        // Try to pretty-print JSON
        try {
          responsePreview.value = JSON.stringify(JSON.parse(data.response_body), null, 2)
        } catch { /* keep raw */ }
      }
      // Populate detected paths + auto-fill the first one
      isJsonResponse.value = !!(data.content_type && data.content_type.includes('json'))
      if (data.detected_text_paths?.length) {
        detectedTextPaths.value = data.detected_text_paths
        // Auto-fill if user hasn't manually set anything
        if (!responseTextPathsRaw.value.trim()) {
          responseTextPathsRaw.value = data.detected_text_paths[0]
        }
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
        bodySnippet: data.body_snippet,
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
    request_template: requestTemplate.value,
    response_text_paths: responseTextPaths.value,
  })
}
</script>
