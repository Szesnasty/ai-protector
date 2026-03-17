<template>
  <v-container fluid class="test-agent-chat-page">
    <!-- Header -->
    <div class="d-flex align-center justify-space-between mb-4">
      <div>
        <h1 class="text-h5 mb-1">{{ title }}</h1>
        <p class="text-body-2 text-medium-emphasis">
          Test wizard-generated security configs against a live {{ framework }} agent
        </p>
      </div>
      <div class="d-flex align-center ga-2">
        <v-chip
          :color="configStatus?.loaded ? 'success' : 'grey'"
          variant="tonal"
          size="small"
          :prepend-icon="configStatus?.loaded ? 'mdi-check-circle' : 'mdi-circle-outline'"
        >
          {{ configStatus?.loaded ? 'Config Loaded' : 'No Config' }}
        </v-chip>
        <v-btn
          icon="mdi-code-braces"
          variant="text"
          size="small"
          title="View Agent Source & Config"
          @click="drawerOpen = !drawerOpen"
        />
      </div>
    </div>

    <!-- Controls Row -->
    <v-row class="mb-4">
      <!-- Agent Selector -->
      <v-col cols="12" sm="4">
        <v-select
          v-model="selectedAgentId"
          :items="filteredAgents"
          item-title="name"
          item-value="id"
          label="Select Agent"
          variant="outlined"
          density="compact"
          hide-details
          prepend-inner-icon="mdi-robot-outline"
          :loading="agentsLoading"
          no-data-text="No agents with this framework"
        />
      </v-col>

      <!-- Role Selector -->
      <v-col cols="12" sm="3">
        <v-select
          v-model="selectedRole"
          :items="availableRoles"
          label="Role"
          variant="outlined"
          density="compact"
          hide-details
          prepend-inner-icon="mdi-account-outline"
          :disabled="!configStatus?.loaded"
        />
      </v-col>

      <!-- Load Config Button + Status -->
      <v-col cols="12" sm="5">
        <div class="d-flex align-center ga-2">
          <v-btn
            color="primary"
            variant="tonal"
            :loading="agent.isLoading.value"
            :disabled="!selectedAgentId"
            prepend-icon="mdi-download"
            @click="handleLoadConfig"
          >
            Load Config
          </v-btn>
          <v-btn
            v-if="configStatus?.loaded"
            variant="text"
            icon="mdi-refresh"
            size="small"
            title="Reset config"
            @click="handleReset"
          />
          <div v-if="configStatus?.loaded" class="text-body-2 text-medium-emphasis">
            <v-icon size="14" class="mr-1">mdi-shield-check</v-icon>
            <span>{{ configStatus.policy_pack || 'default' }}</span>
            <span class="mx-1">·</span>
            <span>{{ configStatus.roles?.join(', ') }}</span>
            <span v-if="configStatus.tools_in_rbac" class="mx-1">·</span>
            <span v-if="configStatus.tools_in_rbac">{{ configStatus.tools_in_rbac }} tools</span>
          </div>
        </div>
      </v-col>
    </v-row>

    <!-- Mode Row -->
    <v-row class="mb-4" dense>
      <v-col cols="auto">
        <v-btn-toggle v-model="chatMode" mandatory density="compact" variant="outlined" divided>
          <v-btn value="mock" size="small">
            <v-icon start size="16">mdi-test-tube</v-icon>
            Mock
          </v-btn>
          <v-btn value="llm" size="small">
            <v-icon start size="16">mdi-brain</v-icon>
            LLM
          </v-btn>
        </v-btn-toggle>
      </v-col>
      <v-col v-if="chatMode === 'llm'" cols="12" sm="2">
        <v-select
          v-model="selectedProvider"
          :items="providerList"
          label="Provider"
          variant="outlined"
          density="compact"
          hide-details
        >
          <template #item="{ item, props: itemProps }">
            <v-list-item v-bind="itemProps">
              <template #prepend>
                <v-avatar size="20" :color="providerMeta[item.value]?.color ?? 'grey'" variant="tonal" rounded="sm">
                  <v-icon size="14">{{ providerMeta[item.value]?.icon ?? 'mdi-brain' }}</v-icon>
                </v-avatar>
              </template>
            </v-list-item>
          </template>
          <template #selection="{ item }">
            <v-avatar size="20" :color="providerMeta[item.value]?.color ?? 'grey'" variant="tonal" rounded="sm" class="mr-2">
              <v-icon size="14">{{ providerMeta[item.value]?.icon ?? 'mdi-brain' }}</v-icon>
            </v-avatar>
            {{ item.title }}
          </template>
        </v-select>
      </v-col>
      <v-col v-if="chatMode === 'llm'" cols="12" sm="3">
        <v-select
          v-model="llmModel"
          :items="filteredModels"
          label="Model"
          variant="outlined"
          density="compact"
          hide-details
        />
      </v-col>
      <v-col v-if="chatMode === 'llm' && needsApiKey" cols="12" sm="4">
        <v-text-field
          v-model="apiKey"
          label="API Key"
          variant="outlined"
          density="compact"
          hide-details
          :type="showApiKey ? 'text' : 'password'"
          prepend-inner-icon="mdi-key"
          :append-inner-icon="showApiKey ? 'mdi-eye-off' : 'mdi-eye'"
          @click:append-inner="showApiKey = !showApiKey"
          :placeholder="apiKeyPlaceholder"
        />
      </v-col>
      <v-col v-if="chatMode === 'llm'" cols="auto" class="d-flex align-center">
        <v-chip
          v-if="!needsApiKey"
          size="small"
          color="success"
          variant="tonal"
          prepend-icon="mdi-check-circle"
        >
          Local — no API key needed
        </v-chip>
      </v-col>
    </v-row>

    <!-- Error Alert -->
    <v-alert
      v-if="agent.error.value"
      type="error"
      variant="tonal"
      closable
      class="mb-4"
      @click:close="agent.error.value = null"
    >
      {{ agent.error.value }}
    </v-alert>

    <!-- Main Content: Chat + Gate Log -->
    <v-row>
      <!-- Chat Panel -->
      <v-col cols="12" md="7">
        <v-card variant="outlined" class="d-flex flex-column" style="height: 520px">
          <v-card-title class="text-subtitle-1 pb-0">
            <v-icon start size="18">mdi-chat-processing</v-icon>
            Chat
          </v-card-title>

          <!-- Messages -->
          <v-card-text ref="chatContainer" class="flex-grow-1 overflow-y-auto pa-3">
            <div v-if="!messages.length" class="text-center text-medium-emphasis py-12">
              <v-icon size="48" class="mb-2">mdi-message-text-outline</v-icon>
              <p class="text-body-2">
                {{ configStatus?.loaded ? 'Send a message to start testing' : 'Load a config to begin' }}
              </p>
            </div>

            <div v-for="(msg, i) in messages" :key="i" class="mb-3">
              <!-- User Message -->
              <div v-if="msg.type === 'user'" class="d-flex justify-end">
                <v-chip color="primary" variant="tonal" class="pa-3" style="max-width: 80%; white-space: normal; height: auto">
                  {{ msg.text }}
                </v-chip>
              </div>

              <!-- Agent Response -->
              <div v-else class="d-flex justify-start">
                <v-card
                  :color="msg.blocked ? 'error' : msg.noMatch ? 'grey-lighten-1' : msg.requiresConfirmation ? 'warning' : 'surface-light'"
                  :variant="msg.blocked || msg.requiresConfirmation ? 'tonal' : msg.noMatch ? 'tonal' : 'outlined'"
                  class="pa-3"
                  style="max-width: 80%"
                >
                  <div class="d-flex align-center ga-1 mb-1">
                    <v-icon v-if="msg.blocked" size="16" color="error">mdi-close-circle</v-icon>
                    <v-icon v-else-if="msg.noMatch" size="16" color="grey">mdi-help-circle-outline</v-icon>
                    <v-icon v-else-if="msg.requiresConfirmation" size="16" color="warning">mdi-alert</v-icon>
                    <v-icon v-else size="16">mdi-robot-outline</v-icon>
                    <span class="text-caption text-medium-emphasis">
                      {{ msg.blocked ? 'SECURITY BLOCK' : msg.noMatch ? 'NO MATCH' : msg.requiresConfirmation ? 'CONFIRMATION REQUIRED' : 'Agent' }}
                    </span>
                  </div>
                  <pre class="text-body-2" style="white-space: pre-wrap; font-family: inherit">{{ msg.text }}</pre>
                  <v-btn
                    v-if="msg.requiresConfirmation && !msg.confirmed"
                    color="warning"
                    variant="flat"
                    size="small"
                    class="mt-2"
                    prepend-icon="mdi-check"
                    :loading="isSending"
                    @click="handleConfirm(msg)"
                  >
                    Confirm Execution
                  </v-btn>
                  <v-chip
                    v-if="msg.requiresConfirmation && msg.confirmed"
                    color="success"
                    variant="tonal"
                    size="x-small"
                    class="mt-2"
                    prepend-icon="mdi-check"
                  >
                    Confirmed
                  </v-chip>
                </v-card>
              </div>
            </div>

            <!-- Sending indicator -->
            <div v-if="isSending" class="d-flex justify-start">
              <v-progress-circular indeterminate size="20" width="2" class="ml-2" />
            </div>
          </v-card-text>

          <!-- Quick Action Buttons -->
          <div v-if="configStatus?.loaded" class="px-3 pb-1">
            <div class="d-flex flex-wrap ga-1">
              <v-btn
                v-for="action in quickActions"
                :key="action.label"
                variant="text"
                size="x-small"
                :disabled="isSending"
                @click="sendMessage(action.message)"
              >
                {{ action.label }}
              </v-btn>
            </div>
          </div>

          <!-- Input -->
          <v-card-actions class="pa-3 pt-1">
            <v-text-field
              v-model="inputMessage"
              placeholder="Type a message..."
              variant="outlined"
              density="compact"
              hide-details
              :disabled="!configStatus?.loaded || isSending"
              append-inner-icon="mdi-send"
              @keyup.enter="sendMessage(inputMessage)"
              @click:append-inner="sendMessage(inputMessage)"
            />
          </v-card-actions>
        </v-card>
      </v-col>

      <!-- Gate Log Panel -->
      <v-col cols="12" md="5">
        <v-card variant="outlined" class="d-flex flex-column" style="height: 520px">
          <v-card-title class="text-subtitle-1 pb-0 d-flex align-center justify-space-between">
            <div>
              <v-icon start size="18">mdi-shield-search</v-icon>
              Gate Log
            </div>
            <v-btn
              v-if="gateLog.length"
              variant="text"
              size="x-small"
              @click="gateLog = []"
            >
              Clear
            </v-btn>
          </v-card-title>

          <v-card-text class="flex-grow-1 overflow-y-auto pa-3">
            <div v-if="!gateLog.length" class="text-center text-medium-emphasis py-12">
              <v-icon size="48" class="mb-2">mdi-shield-outline</v-icon>
              <p class="text-body-2">Security gate decisions will appear here</p>
            </div>

            <div v-for="(entry, i) in gateLog" :key="i" class="mb-2">
              <v-card
                :color="gateColor(entry.decision)"
                variant="tonal"
                density="compact"
                class="pa-2"
              >
                <div class="d-flex align-center ga-1 mb-1">
                  <v-icon size="14">{{ gateIcon(entry.decision) }}</v-icon>
                  <span class="text-caption font-weight-bold">{{ entry.gate }}</span>
                  <v-chip :color="gateColor(entry.decision)" size="x-small" variant="flat" class="ml-auto">
                    {{ entry.decision }}
                  </v-chip>
                </div>
                <div v-if="entry.tool" class="text-caption">
                  <v-icon size="12" class="mr-1">mdi-wrench</v-icon>
                  {{ entry.tool }}
                </div>
                <div v-if="entry.role" class="text-caption">
                  <v-icon size="12" class="mr-1">mdi-account</v-icon>
                  {{ entry.role }}
                </div>
                <div v-if="entry.reason" class="text-caption text-medium-emphasis mt-1">
                  {{ entry.reason }}
                </div>
                <div
                  v-if="entry.findings?.length || entry.scan_findings?.length"
                  class="mt-1"
                >
                  <v-chip
                    v-for="(f, fi) in [...(entry.findings || []), ...(entry.scan_findings || [])]"
                    :key="fi"
                    size="x-small"
                    variant="outlined"
                    class="mr-1 mb-1"
                  >
                    {{ f.type }}: {{ f.detail }}
                  </v-chip>
                </div>
              </v-card>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Source & Config Drawer -->
    <TestAgentsAgentSourceDrawer
      v-model="drawerOpen"
      :base-url="baseUrl"
      :config-loaded="!!configStatus?.loaded"
    />
  </v-container>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, watch } from 'vue'
import { useTestAgent, type GateLogEntry, type ChatResponse, type ChatRequest } from '~/composables/useTestAgent'
import { useAgents } from '~/composables/useAgents'
import type { AgentFramework } from '~/types/wizard'

// ─── Props ───

const props = defineProps<{
  baseUrl: string
  framework: AgentFramework
  title: string
}>()

// ─── Agent API ───

const agent = useTestAgent(props.baseUrl)
const configStatus = agent.configStatus

// ─── Agents List ───

const { agents, isLoading: agentsLoading } = useAgents()

const filteredAgents = computed(() =>
  (agents.value ?? []).filter(a => a.framework === props.framework),
)

// ─── State ───

const selectedAgentId = ref<string | null>(null)
const selectedRole = ref('user')
const inputMessage = ref('')
const isSending = ref(false)
const chatContainer = ref<HTMLElement | null>(null)
const drawerOpen = ref(false)
const chatMode = ref<'mock' | 'llm'>('mock')
const selectedProvider = ref('ollama')
const llmModel = ref('ollama/llama3.2:3b')
const apiKey = ref('')
const showApiKey = ref(false)

// ── Provider / Model catalogue (Playground-style) ──────────────
interface ProviderInfo {
  icon: string
  color: string
  keyEnv: string
  models: { title: string; value: string }[]
}

const providerMeta: Record<string, ProviderInfo> = {
  ollama:    { icon: 'mdi-llama',          color: 'grey',    keyEnv: '',                  models: [
    { title: 'Llama 3.2 3B',   value: 'ollama/llama3.2:3b' },
    { title: 'Llama 3.1 8B',   value: 'ollama/llama3.1:8b' },
    { title: 'Mistral 7B',     value: 'ollama/mistral:7b' },
    { title: 'Gemma 2 9B',     value: 'ollama/gemma2:9b' },
    { title: 'Phi-3 Mini',     value: 'ollama/phi3:mini' },
    { title: 'Qwen 2.5 7B',   value: 'ollama/qwen2.5:7b' },
  ]},
  openai:    { icon: 'mdi-creation',       color: 'teal',    keyEnv: 'OPENAI_API_KEY',    models: [
    { title: 'GPT-4o',         value: 'gpt-4o' },
    { title: 'GPT-4o Mini',    value: 'gpt-4o-mini' },
    { title: 'GPT-4 Turbo',    value: 'gpt-4-turbo' },
    { title: 'o3-mini',        value: 'o3-mini' },
  ]},
  anthropic: { icon: 'mdi-alpha-a-circle', color: 'deep-orange', keyEnv: 'ANTHROPIC_API_KEY', models: [
    { title: 'Claude 4 Sonnet',       value: 'anthropic/claude-sonnet-4-20250514' },
    { title: 'Claude 3.5 Sonnet',     value: 'anthropic/claude-3-5-sonnet-20241022' },
    { title: 'Claude 3.5 Haiku',      value: 'anthropic/claude-3-5-haiku-20241022' },
    { title: 'Claude 3 Opus',         value: 'anthropic/claude-3-opus-20240229' },
  ]},
  google:    { icon: 'mdi-google',         color: 'blue',    keyEnv: 'GEMINI_API_KEY',    models: [
    { title: 'Gemini 2.0 Flash',      value: 'gemini/gemini-2.0-flash' },
    { title: 'Gemini 2.5 Flash',      value: 'gemini/gemini-2.5-flash-preview-04-17' },
    { title: 'Gemini 1.5 Pro',        value: 'gemini/gemini-1.5-pro' },
  ]},
  groq:      { icon: 'mdi-lightning-bolt', color: 'orange',  keyEnv: 'GROQ_API_KEY',      models: [
    { title: 'Llama 3.3 70B',         value: 'groq/llama-3.3-70b-versatile' },
    { title: 'Llama 3.1 8B Instant',  value: 'groq/llama-3.1-8b-instant' },
    { title: 'Mixtral 8x7B',          value: 'groq/mixtral-8x7b-32768' },
  ]},
  deepseek:  { icon: 'mdi-fish',           color: 'indigo',  keyEnv: 'DEEPSEEK_API_KEY',  models: [
    { title: 'DeepSeek Chat',          value: 'deepseek/deepseek-chat' },
    { title: 'DeepSeek Reasoner',      value: 'deepseek/deepseek-reasoner' },
  ]},
}

const providerList = Object.keys(providerMeta).map(k => ({
  title: k.charAt(0).toUpperCase() + k.slice(1),
  value: k,
}))

const filteredModels = computed(() => {
  return providerMeta[selectedProvider.value]?.models ?? []
})

// Auto-select first model when provider changes
watch(selectedProvider, (prov) => {
  const models = providerMeta[prov]?.models ?? []
  if (models.length && models[0]) llmModel.value = models[0].value
})

const needsApiKey = computed(() => {
  return selectedProvider.value !== 'ollama'
})

const apiKeyPlaceholder = computed(() => {
  const info = providerMeta[selectedProvider.value]
  return info?.keyEnv ? `paste ${info.keyEnv}` : ''
})

interface ChatMsg {
  type: 'user' | 'agent'
  text: string
  blocked?: boolean
  noMatch?: boolean
  requiresConfirmation?: boolean
  confirmed?: boolean
  tool?: string
  toolArgs?: Record<string, unknown>
  originalMessage?: string
}

const messages = ref<ChatMsg[]>([])
const gateLog = ref<GateLogEntry[]>([])

// ─── Computed ───

const availableRoles = computed(() => {
  if (configStatus.value?.roles?.length) return configStatus.value.roles
  return ['user', 'admin']
})

const quickActions = [
  { label: 'Get Orders', message: 'show me all orders' },
  { label: 'Get Users', message: 'list all users' },
  { label: 'Search Products', message: 'search products laptop' },
  { label: 'Update Order', message: 'update order ORD-001 status shipped' },
  { label: 'Update User', message: 'update user USR-001 email test@test.com' },
]

// ─── Methods ───

async function handleLoadConfig() {
  if (!selectedAgentId.value) return
  try {
    await agent.loadConfig(selectedAgentId.value)
    // Clear chat & gate log on new config
    messages.value = []
    gateLog.value = []
    // Set first role
    if (configStatus.value?.roles?.length) {
      selectedRole.value = configStatus.value.roles[0]
    }
  } catch {
    // error is already set in composable
  }
}

async function handleReset() {
  await agent.resetConfig()
  messages.value = []
  gateLog.value = []
}

async function sendMessage(text: string) {
  if (!text?.trim() || !configStatus.value?.loaded) return
  const trimmed = text.trim()
  inputMessage.value = ''

  messages.value.push({ type: 'user', text: trimmed })
  scrollToBottom()

  isSending.value = true
  try {
    const chatReq: ChatRequest = { message: trimmed, role: selectedRole.value }
    if (chatMode.value === 'llm') {
      chatReq.mode = 'llm'
      chatReq.model = llmModel.value
      if (apiKey.value) chatReq.api_key = apiKey.value
    }
    const res = await agent.chat(chatReq)
    appendAgentResponse(res, trimmed)
  } catch {
    messages.value.push({ type: 'agent', text: agent.error.value ?? 'Request failed', blocked: true })
  } finally {
    isSending.value = false
    scrollToBottom()
  }
}

async function handleConfirm(msg: ChatMsg) {
  if (!msg.originalMessage) return
  isSending.value = true
  try {
    const chatReq: ChatRequest = {
      message: msg.originalMessage,
      role: selectedRole.value,
      tool: msg.tool,
      tool_args: msg.toolArgs,
      confirmed: true,
    }
    if (chatMode.value === 'llm') {
      chatReq.mode = 'llm'
      chatReq.model = llmModel.value
      if (apiKey.value) chatReq.api_key = apiKey.value
    }
    const res = await agent.chat(chatReq)
    msg.confirmed = true
    appendAgentResponse(res, msg.originalMessage)
  } catch {
    messages.value.push({ type: 'agent', text: agent.error.value ?? 'Confirm failed', blocked: true })
  } finally {
    isSending.value = false
    scrollToBottom()
  }
}

function appendAgentResponse(res: ChatResponse, originalMessage: string) {
  messages.value.push({
    type: 'agent',
    text: res.response,
    blocked: res.blocked,
    noMatch: res.no_match ?? false,
    requiresConfirmation: res.requires_confirmation ?? false,
    tool: res.tool,
    toolArgs: res.tool_args,
    originalMessage,
  })
  // Append gate log entries
  if (res.gate_log?.length) {
    gateLog.value.push(...res.gate_log)
  }
}

function scrollToBottom() {
  nextTick(() => {
    const el = chatContainer.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

// ─── Gate Log Helpers ───

function gateColor(decision: string): string {
  const d = decision.toUpperCase()
  if (d === 'ALLOW') return 'success'
  if (d === 'BLOCK' || d === 'DENY') return 'error'
  if (d === 'CONFIRM') return 'warning'
  if (d === 'FLAGGED' || d === 'REDACT') return 'info'
  if (d === 'NO_MATCH') return 'grey'
  return 'grey'
}

function gateIcon(decision: string): string {
  const d = decision.toUpperCase()
  if (d === 'ALLOW') return 'mdi-check-circle'
  if (d === 'BLOCK' || d === 'DENY') return 'mdi-close-circle'
  if (d === 'CONFIRM') return 'mdi-alert-circle'
  if (d === 'FLAGGED' || d === 'REDACT') return 'mdi-magnify'
  if (d === 'NO_MATCH') return 'mdi-help-circle-outline'
  return 'mdi-help-circle'
}
</script>

<style lang="scss" scoped>
.test-agent-chat-page {
  max-width: 1400px;
}

pre {
  margin: 0;
}
</style>
