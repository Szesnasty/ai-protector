<template>
  <v-card variant="flat" class="target-form pa-6">
    <h2 class="text-h6 mb-1">
      {{ isHosted ? 'Hosted Endpoint' : 'Local Agent' }}
    </h2>
    <p class="text-body-2 text-medium-emphasis mb-4">
      {{ isHosted
        ? 'Enter the URL and credentials for your hosted AI endpoint.'
        : 'Enter the URL of your locally-running agent.' }}
    </p>

    <v-form ref="formRef" v-model="formValid" @submit.prevent>
      <!-- Endpoint URL (required) -->
      <v-text-field
        v-model="endpointUrl"
        label="Endpoint URL"
        :placeholder="isHosted ? 'https://api.example.com/chat' : 'http://localhost:8080/chat'"
        :rules="[rules.required, rules.url]"
        variant="outlined"
        density="compact"
        class="mb-3"
        data-testid="endpoint-url"
      />

      <!-- Target name (optional) -->
      <v-text-field
        v-model="targetName"
        label="Target Name (optional)"
        placeholder="My Agent"
        variant="outlined"
        density="compact"
        class="mb-3"
      />

      <!-- Auth header — shown by default for hosted, collapsed in advanced for local -->
      <v-text-field
        v-if="isHosted || showAdvanced"
        v-model="authHeader"
        label="Authorization Header"
        placeholder="Bearer sk-..."
        variant="outlined"
        density="compact"
        class="mb-3"
        :type="showAuth ? 'text' : 'password'"
        :append-inner-icon="showAuth ? 'mdi-eye-off' : 'mdi-eye'"
        data-testid="auth-header"
        @click:append-inner="showAuth = !showAuth"
      />

      <!-- Safety notice — always visible -->
      <v-alert
        type="warning"
        variant="tonal"
        class="mb-4"
        data-testid="safety-notice"
      >
        Benchmarks send realistic attack prompts. If your agent has real tools,
        use Safe mode or a staging environment.
      </v-alert>

      <!-- Test Connection -->
      <div class="mb-4">
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
        class="mb-4"
        data-testid="connection-result"
      >
        {{ connectionResult.message }}
      </v-alert>

      <!-- Non-JSON warning -->
      <v-alert
        v-if="nonJsonWarning"
        type="warning"
        variant="tonal"
        class="mb-4"
        data-testid="non-json-warning"
      >
        Endpoint returned {{ nonJsonContentType }} instead of JSON.
        Benchmark may have limited accuracy. Continue anyway?
      </v-alert>

      <!-- Advanced section — collapsed by default -->
      <v-expansion-panels v-model="advancedPanel" class="mb-4" variant="accordion">
        <v-expansion-panel value="advanced">
          <v-expansion-panel-title>
            <v-icon icon="mdi-tune" size="small" class="mr-2" />
            Advanced Settings
          </v-expansion-panel-title>
          <v-expansion-panel-text>
            <!-- Auth header for local (if not shown above) -->
            <v-text-field
              v-if="!isHosted"
              v-model="authHeader"
              label="Authorization Header"
              placeholder="Bearer sk-..."
              variant="outlined"
              density="compact"
              class="mb-3"
              :type="showAuth ? 'text' : 'password'"
              :append-inner-icon="showAuth ? 'mdi-eye-off' : 'mdi-eye'"
              @click:append-inner="showAuth = !showAuth"
            />

            <!-- Type -->
            <p class="text-body-2 font-weight-medium mb-1">Endpoint Type</p>
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
                label="Safe Mode"
                color="primary"
                density="compact"
                hide-details
                class="mr-2"
                data-testid="safe-mode-toggle"
              />
              <v-tooltip text="Skip scenarios that may trigger real actions (delete, transfer, etc.)">
                <template #activator="{ props }">
                  <v-icon v-bind="props" icon="mdi-help-circle-outline" size="small" />
                </template>
              </v-tooltip>
            </div>

            <!-- Environment (Hosted only) -->
            <template v-if="isHosted">
              <p class="text-body-2 font-weight-medium mb-1">Environment</p>
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

      <!-- Continue button -->
      <v-btn
        color="primary"
        size="large"
        block
        :disabled="!canContinue"
        data-testid="continue-btn"
        @click="onContinue"
      >
        Continue
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
  auth_header: string
  agent_type: string
  timeout_s: number
  safe_mode: boolean
  environment: string
}

const isHosted = computed(() => props.targetType === 'hosted_endpoint')

// Form state
const formRef = ref()
const formValid = ref(false)
const endpointUrl = ref(isHosted.value ? 'https://' : 'http://localhost:')
const targetName = ref('')
const authHeader = ref('')
const showAuth = ref(false)
const agentType = ref('chatbot_api')
const timeoutS = ref(30)
const safeMode = ref(isHosted.value) // Hosted=On, Local=Off
const environment = ref('staging')
const advancedPanel = ref<string | undefined>(undefined)
const showAdvanced = computed(() => advancedPanel.value === 'advanced')

// Connection test state
const isTesting = ref(false)
const connectionPassed = ref(false)
const connectionResult = ref<{ type: 'success' | 'error'; message: string } | null>(null)
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

// Can continue only after successful test (or non-JSON warning allows proceed)
const canContinue = computed(() => connectionPassed.value)

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
    }>('/v1/benchmark/test-connection', {
      endpoint_url: endpointUrl.value,
      auth_header: authHeader.value || undefined,
      timeout_s: timeoutS.value,
    })

    const data = res.data
    if (data.status === 'ok') {
      connectionPassed.value = true
      connectionResult.value = {
        type: 'success',
        message: `${data.status_code} OK | ${data.latency_ms}ms | AI Protector can reach your endpoint`,
      }
      // Check for non-JSON
      if (data.content_type && !data.content_type.includes('json')) {
        nonJsonWarning.value = true
        nonJsonContentType.value = data.content_type
      }
    } else {
      connectionResult.value = {
        type: 'error',
        message: data.error ?? 'Connection failed',
      }
    }
  } catch (err: unknown) {
    connectionResult.value = {
      type: 'error',
      message: (err as { message?: string })?.message ?? 'Connection test failed',
    }
  } finally {
    isTesting.value = false
  }
}

function onContinue() {
  emit('continue', {
    target_type: props.targetType,
    endpoint_url: endpointUrl.value,
    target_name: targetName.value,
    auth_header: authHeader.value,
    agent_type: agentType.value,
    timeout_s: timeoutS.value,
    safe_mode: safeMode.value,
    environment: isHosted.value ? environment.value : '',
  })
}
</script>
