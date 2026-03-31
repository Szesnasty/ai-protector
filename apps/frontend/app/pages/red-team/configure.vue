<template>
  <v-container fluid class="configure-page">
    <!-- Header -->
    <div class="mb-6">
      <div class="d-flex align-center mb-1">
        <v-btn
          icon="mdi-arrow-left"
          variant="text"
          size="small"
          class="mr-2"
          :to="'/red-team'"
        />
        <h1 class="text-h5">Run baseline scan</h1>
        <v-chip
          v-if="target === 'demo'"
          color="purple"
          variant="tonal"
          size="small"
          prepend-icon="mdi-robot"
          class="ml-3"
          label
        >
          Demo
        </v-chip>
      </div>
      <p class="text-body-2 text-medium-emphasis mt-2" style="max-width: 540px;">
        Attacks go directly to your endpoint — no protection active. You’ll enable protection and re-run after seeing results.
      </p>
      <div class="d-flex align-center mt-2">
        <span class="text-body-2 text-medium-emphasis mr-2">Target:</span>
        <v-chip color="primary" variant="tonal" size="small" :prepend-icon="targetIcon">
          {{ targetLabel }}
        </v-chip>
        <v-btn
          variant="text"
          size="x-small"
          class="ml-2"
          :to="'/red-team'"
        >
          Change
        </v-btn>
      </div>
    </div>

    <!-- Pack selection — simplified -->
    <h2 class="text-h6 mb-3">Attack pack</h2>

    <v-radio-group v-model="selectedPack" class="mb-2">
      <v-card
        v-for="pack in primaryPacks"
        :key="pack.name"
        variant="flat"
        class="mb-3 pack-card"
        :class="{ 'pack-card--selected': selectedPack === pack.name }"
        @click="selectedPack = pack.name"
      >
        <v-card-text class="d-flex align-start pa-4">
          <v-radio
            :value="pack.name"
            class="mr-3 mt-0"
            hide-details
          />
          <div>
            <div class="d-flex align-center flex-wrap mb-1">
              <span class="text-subtitle-2 font-weight-bold">{{ pack.displayName }}</span>
              <v-chip
                v-if="pack.recommended"
                size="x-small"
                color="primary"
                variant="tonal"
                class="ml-2"
              >
                ★ Recommended
              </v-chip>
              <v-chip
                v-if="pack.scenarioCount > 0"
                size="x-small"
                variant="outlined"
                class="ml-2"
              >
                {{ pack.scenarioCount }} attacks · ~{{ pack.estimatedTime }}
              </v-chip>
            </div>
            <p class="text-body-2 text-medium-emphasis mb-0">{{ pack.description }}</p>
          </div>
        </v-card-text>
      </v-card>
    </v-radio-group>

    <!-- More packs — collapsed -->
    <v-expansion-panels v-if="secondaryPacks.length > 0 || futurePacks.length > 0" class="mb-4" variant="accordion">
      <v-expansion-panel>
        <v-expansion-panel-title class="text-body-2 text-medium-emphasis">
          More attack packs
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <v-card
            v-for="pack in secondaryPacks"
            :key="pack.name"
            variant="flat"
            class="mb-3 pack-card"
            :class="{ 'pack-card--selected': selectedPack === pack.name }"
            @click="selectedPack = pack.name"
          >
            <v-card-text class="d-flex align-start pa-4">
              <v-radio
                :value="pack.name"
                class="mr-3 mt-0"
                hide-details
              />
              <div>
                <div class="d-flex align-center flex-wrap mb-1">
                  <span class="text-subtitle-2 font-weight-bold">{{ pack.displayName }}</span>
                  <v-chip
                    v-if="pack.scenarioCount > 0"
                    size="x-small"
                    variant="outlined"
                    class="ml-2"
                  >
                    {{ pack.scenarioCount }} attacks · ~{{ pack.estimatedTime }}
                  </v-chip>
                </div>
                <p class="text-body-2 text-medium-emphasis mb-0">{{ pack.description }}</p>
              </div>
            </v-card-text>
          </v-card>

          <v-card
            v-for="pack in futurePacks"
            :key="pack.name"
            variant="flat"
            class="mb-2 pack-card"
            disabled
          >
            <v-card-text class="d-flex align-start pa-4" style="opacity: 0.5;">
              <v-radio disabled class="mr-3 mt-0" hide-details />
              <div>
                <div class="d-flex align-center mb-1">
                  <span class="text-subtitle-2 font-weight-bold">{{ pack.displayName }}</span>
                  <v-chip size="x-small" color="grey" variant="tonal" class="ml-2">Coming soon</v-chip>
                </div>
                <p class="text-body-2 text-medium-emphasis mb-0">{{ pack.description }}</p>
              </div>
            </v-card-text>
          </v-card>
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>

    <!-- Summary bar -->
    <v-alert
      v-if="selectedPackInfo && selectedPackInfo.scenarioCount > 0"
      color="primary"
      variant="tonal"
      density="compact"
      class="mb-4"
    >
      <template #prepend>
        <v-icon icon="mdi-information-outline" />
      </template>
      {{ selectedPackInfo.scenarioCount }} attacks · ~{{ selectedPackInfo.estimatedTime }} · no enforced protection
    </v-alert>



    <!-- Hero Run button -->
    <div class="d-flex flex-column align-center mb-2">
      <v-btn
        color="primary"
        size="large"
        class="run-button px-12"
        prepend-icon="mdi-magnify-scan"
        :loading="isCreating"
        :disabled="!selectedPack || isCreating"
        data-testid="run-benchmark-btn"
        @click="onRunBenchmark"
      >
        Run baseline scan
      </v-btn>
    </div>
    <p v-if="selectedPackInfo" class="text-caption text-medium-emphasis text-center mt-1 mb-4" style="line-height: 1.2;">
      {{ selectedPackInfo.displayName }}
      <template v-if="selectedPackInfo.scenarioCount > 0"> · {{ selectedPackInfo.scenarioCount }} attacks</template>
    </p>

    <!-- What happens next — only for baseline flow -->
    <v-card variant="flat" class="mb-6 pa-4">
      <h3 class="text-subtitle-2 font-weight-bold mb-3">What happens next</h3>
      <div class="d-flex flex-column ga-2">
        <div class="d-flex align-start">
          <v-avatar color="primary" variant="tonal" size="24" class="mr-3 mt-0 flex-shrink-0">
            <span class="text-caption font-weight-bold">1</span>
          </v-avatar>
          <span class="text-body-2 text-medium-emphasis">We send adversarial attacks to your endpoint and measure what gets through.</span>
        </div>
        <div class="d-flex align-start">
          <v-avatar color="success" variant="tonal" size="24" class="mr-3 mt-0 flex-shrink-0">
            <span class="text-caption font-weight-bold">2</span>
          </v-avatar>
          <span class="text-body-2 text-medium-emphasis">You see which attacks got through — then route your endpoint through AI Protector.</span>
        </div>
        <div class="d-flex align-start">
          <v-avatar color="warning" variant="tonal" size="24" class="mr-3 mt-0 flex-shrink-0">
            <span class="text-caption font-weight-bold">3</span>
          </v-avatar>
          <span class="text-body-2 text-medium-emphasis">Re-run the same scan and get a before-vs-after comparison proving which vulnerabilities were fixed.</span>
        </div>
      </div>
    </v-card>

    <!-- Error alert -->
    <v-alert
      v-if="runError"
      type="error"
      variant="tonal"
      closable
      class="mb-4"
      @click:close="runError = null"
    >
      {{ runError }}
    </v-alert>

    <!-- Advanced section -->
    <v-expansion-panels v-model="advancedPanel" class="mb-6" variant="accordion">
      <v-expansion-panel value="advanced">
        <v-expansion-panel-title class="text-body-2 text-medium-emphasis">
          <v-icon icon="mdi-tune" size="small" class="mr-2" />
          Advanced settings
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <v-select
            v-model="selectedPolicy"
            :items="policyOptions"
            item-title="label"
            item-value="value"
            label="Evaluation Policy"
            variant="outlined"
            density="compact"
            class="mt-2"
            hint="Controls how strictly scenarios are evaluated"
            persistent-hint
          />

          <p v-if="target !== 'demo'" class="text-caption text-medium-emphasis mt-2">
            Policy is applied only when traffic runs through AI Protector.
          </p>
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>
  </v-container>
</template>

<script setup lang="ts">
import { useBenchmarkPacks, useBenchmarkCreateRun } from '~/composables/useBenchmark'
import { humanPack } from '~/utils/redTeamLabels'

definePageMeta({ layout: 'default' })

const route = useRoute()
const router = useRouter()

// Redirect if no target
const target = computed(() => (route.query.target as string) || 'demo')

// Read target_config from query params (set by target.vue)
const endpointUrl = computed(() => (route.query.endpoint_url as string) || '')
const targetName = computed(() => (route.query.target_name as string) || '')
const agentType = computed(() => (route.query.agent_type as string) || 'chatbot_api')
const timeoutS = computed(() => Number(route.query.timeout_s) || 30)
const safeMode = computed(() => route.query.safe_mode === 'true')
const environment = computed(() => (route.query.environment as string) || '')

const targetLabel = computed(() => {
  if (target.value === 'demo') return 'Demo'
  if (target.value === 'local_agent') return 'Local Endpoint'
  if (target.value === 'hosted_endpoint') return 'Your Endpoint'
  return target.value
})

const targetIcon = computed(() => {
  if (target.value === 'demo') return 'mdi-robot'
  if (target.value === 'local_agent') return 'mdi-laptop'
  if (target.value === 'hosted_endpoint') return 'mdi-web'
  return 'mdi-cog'
})

// Pack data
const { packs, isLoading: _packsLoading } = useBenchmarkPacks()

const selectedPack = ref((route.query.pack as string) || 'core_security')
const selectedPolicy = ref((route.query.policy as string) || 'balanced')

const advancedPanel = ref<string | undefined>(undefined)
const runError = ref<string | null>(null)

const policyOptions = [
  { label: 'Fast', value: 'fast' },
  { label: 'Balanced (default)', value: 'balanced' },
  { label: 'Strict', value: 'strict' },
  { label: 'Paranoid', value: 'paranoid' },
]

interface DisplayPack {
  name: string
  displayName: string
  description: string
  scenarioCount: number
  recommended: boolean
  disabled: boolean
  badge?: string
  estimatedTime: string
  /** If true, pack is shown under collapsed "More packs" section */
  secondary?: boolean
}

function estimateTime(count: number): string {
  const sec = Math.round(count * 4.5) // ~4.5s per scenario avg
  if (sec < 60) return `${sec}s`
  return `${Math.ceil(sec / 60)} min`
}

const displayPacks = computed<DisplayPack[]>(() => {
  const packMeta: Record<string, { description: string; recommended: boolean; disabled: boolean; badge?: string; secondary?: boolean }> = {
    core_security: {
      description: 'Prompt injection, jailbreak, data leaks, and harmful output attacks. Works on any chatbot or API.',
      recommended: true,
      disabled: false,
      badge: 'Best starting point',
    },
    agent_threats: {
      description: 'Tool abuse, role bypass, and privilege escalation attacks. Best for tool-calling agents.',
      recommended: false,
      disabled: false,
      badge: 'Advanced',
      secondary: true,
    },
    full_suite: {
      description: 'Comprehensive security test covering all attack categories.',
      recommended: false,
      disabled: true,
    },
    jailbreakbench: {
      description: 'Academic jailbreak benchmark for advanced testing.',
      recommended: false,
      disabled: true,
    },
  }

  const apiPacks = packs.value ?? []
  const result: DisplayPack[] = []

  for (const [name, meta] of Object.entries(packMeta)) {
    const apiPack = apiPacks.find((p) => p.name === name)
    const count = apiPack?.scenario_count ?? 0
    result.push({
      name,
      displayName: apiPack?.display_name ?? humanPack(name),
      description: meta.description,
      scenarioCount: count,
      recommended: meta.recommended,
      disabled: meta.disabled,
      badge: meta.badge,
      estimatedTime: estimateTime(count),
      secondary: meta.secondary === true,
    })
  }

  return result
})

/** Primary packs shown at top level */
const primaryPacks = computed(() => displayPacks.value.filter((p) => !p.disabled && !p.secondary))
/** Secondary packs hidden under "More packs" */
const secondaryPacks = computed(() => displayPacks.value.filter((p) => !p.disabled && p.secondary))
const futurePacks = computed(() => displayPacks.value.filter((p) => p.disabled))

const selectedPackInfo = computed(() => displayPacks.value.find((p) => p.name === selectedPack.value))

// Run benchmark
const { createRun, isCreating } = useBenchmarkCreateRun()

async function onRunBenchmark() {
  runError.value = null
  try {
    // Build target_config from query params + sessionStorage auth
    const targetConfig: Record<string, unknown> = {}
    if (target.value !== 'demo') {
      targetConfig.endpoint_url = endpointUrl.value
      targetConfig.agent_type = agentType.value
      targetConfig.timeout_s = timeoutS.value
      targetConfig.safe_mode = safeMode.value
      if (targetName.value) targetConfig.target_name = targetName.value
      if (environment.value) targetConfig.environment = environment.value

      // Retrieve custom headers from in-memory store (never touches disk)
      const { take } = useEphemeralHeaders()
      const ephemeralHeaders = take()
      if (ephemeralHeaders) {
        targetConfig.custom_headers = ephemeralHeaders
      }

      // Retrieve scan config (request template + response paths) from sessionStorage
      const { load, clear: clearScanConfig } = useScanConfig()
      const scanCfg = load()
      if (scanCfg.requestTemplate) {
        targetConfig.request_template = scanCfg.requestTemplate
      }
      if (scanCfg.responseTextPaths.length > 0) {
        targetConfig.response_text_paths = scanCfg.responseTextPaths
      }
      clearScanConfig()
    }

    const result = await createRun({
      target_type: target.value,
      target_config: targetConfig,
      pack: selectedPack.value,
      policy: selectedPolicy.value,
    })
    router.push(`/red-team/run/${result.id}`)
  } catch (err: unknown) {
    const message = (err as { message?: string })?.message ?? 'Failed to create benchmark run'
    runError.value = message
  }
}
</script>

<style lang="scss" scoped>
.pack-card {
  cursor: pointer;
  transition: border-color 0.15s ease;
  border: 1px solid transparent;

  &--selected {
    border-color: rgb(var(--v-theme-primary));
  }
}

.pack-card[disabled] {
  opacity: 0.5;
  cursor: default;
}

.run-button {
  font-weight: 600;
  letter-spacing: 0.02em;
}
</style>
