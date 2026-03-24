<template>
  <v-container fluid class="configure-page">
    <!-- Header with target info -->
    <div class="mb-6">
      <div class="d-flex align-center mb-1">
        <v-btn
          icon="mdi-arrow-left"
          variant="text"
          size="small"
          class="mr-2"
          :to="'/red-team'"
        />
        <h1 class="text-h5">Configure Benchmark</h1>
      </div>
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

    <!-- Pack selection -->
    <h2 class="text-h6 mb-3">Select Attack Pack</h2>

    <v-radio-group v-model="selectedPack" class="mb-2">
      <v-card
        v-for="pack in activePacks"
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
          <div class="flex-grow-1">
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
                v-if="pack.badge"
                size="x-small"
                variant="outlined"
                class="ml-2"
              >
                {{ pack.badge }}
              </v-chip>
              <v-chip
                v-if="pack.scenarioCount > 0"
                size="x-small"
                variant="outlined"
                class="ml-2"
              >
                {{ pack.scenarioCount }} scenarios · ~{{ pack.estimatedTime }}
              </v-chip>
            </div>
            <p class="text-body-2 text-medium-emphasis mb-0">{{ pack.description }}</p>
          </div>
        </v-card-text>
      </v-card>
    </v-radio-group>

    <!-- Coming soon packs — collapsed -->
    <v-expansion-panels v-if="futurePacks.length > 0" class="mb-4" variant="accordion">
      <v-expansion-panel>
        <v-expansion-panel-title class="text-body-2 text-medium-emphasis">
          Show {{ futurePacks.length }} upcoming pack{{ futurePacks.length !== 1 ? 's' : '' }}
        </v-expansion-panel-title>
        <v-expansion-panel-text>
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

    <!-- Run summary -->
    <v-alert
      v-if="selectedPackInfo"
      type="info"
      variant="tonal"
      density="compact"
      class="mb-4"
    >
      {{ selectedPackInfo.scenarioCount }} scenarios selected · ~{{ selectedPackInfo.estimatedTime }} estimated
    </v-alert>

    <!-- Hero Run button -->
    <v-btn
      color="primary"
      size="large"
      block
      class="mb-6 run-button"
      prepend-icon="mdi-play"
      :loading="isCreating"
      :disabled="!selectedPack || isCreating"
      data-testid="run-benchmark-btn"
      @click="onRunBenchmark"
    >
      {{ runButtonLabel }}
    </v-btn>

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

    <!-- Advanced section — collapsed by default, BELOW Run button -->
    <v-expansion-panels v-model="advancedPanel" class="mb-6" variant="accordion">
      <v-expansion-panel value="advanced">
        <v-expansion-panel-title>
          <v-icon icon="mdi-tune" size="small" class="mr-2" />
          Advanced Settings
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

          <!-- Policy note for external endpoints -->
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

const targetLabel = computed(() => {
  if (target.value === 'demo') return 'Demo Agent'
  if (target.value === 'local_agent') return 'Local Agent'
  if (target.value === 'hosted_endpoint') return 'Hosted Endpoint'
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

const selectedPack = ref('core_security')
const selectedPolicy = ref('balanced')
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
}

function estimateTime(count: number): string {
  const sec = Math.round(count * 4.5) // ~4.5s per scenario avg
  if (sec < 60) return `${sec}s`
  return `${Math.ceil(sec / 60)} min`
}

const displayPacks = computed<DisplayPack[]>(() => {
  const packMeta: Record<string, { description: string; recommended: boolean; disabled: boolean; badge?: string }> = {
    core_security: {
      description: 'Tests prompt injection, jailbreak, data leaks, and harmful outputs. Works on any chatbot or API endpoint.',
      recommended: true,
      disabled: false,
      badge: 'Best for chatbots / APIs',
    },
    agent_threats: {
      description: 'Tests tool abuse, role bypass, and privilege escalation. Best for tool-calling agents.',
      recommended: false,
      disabled: false,
      badge: 'Best for tool-calling agents',
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
    })
  }

  return result
})

const activePacks = computed(() => displayPacks.value.filter((p) => !p.disabled))
const futurePacks = computed(() => displayPacks.value.filter((p) => p.disabled))

const selectedPackInfo = computed(() => displayPacks.value.find((p) => p.name === selectedPack.value))

const runButtonLabel = computed(() => {
  const pack = selectedPackInfo.value
  if (!pack) return 'Run Benchmark'
  return `Run ${pack.displayName} Benchmark`
})

// Run benchmark
const { createRun, isCreating } = useBenchmarkCreateRun()

async function onRunBenchmark() {
  runError.value = null
  try {
    const result = await createRun({
      target_type: target.value,
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
