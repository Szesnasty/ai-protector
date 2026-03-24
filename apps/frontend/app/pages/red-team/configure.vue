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
        <v-chip color="primary" variant="tonal" size="small" prepend-icon="mdi-robot">
          Demo Agent
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
        v-for="pack in displayPacks"
        :key="pack.name"
        variant="flat"
        class="mb-3 pack-card"
        :class="{ 'pack-card--selected': selectedPack === pack.name }"
        :disabled="pack.disabled"
        @click="!pack.disabled && (selectedPack = pack.name)"
      >
        <v-card-text class="d-flex align-start pa-4">
          <v-radio
            :value="pack.name"
            :disabled="pack.disabled"
            class="mr-3 mt-0"
            hide-details
          />
          <div class="flex-grow-1">
            <div class="d-flex align-center mb-1">
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
                v-if="pack.disabled"
                size="x-small"
                color="grey"
                variant="tonal"
                class="ml-2"
              >
                Coming soon
              </v-chip>
              <v-chip
                v-if="pack.scenarioCount > 0 && !pack.disabled"
                size="x-small"
                variant="outlined"
                class="ml-2"
              >
                {{ pack.scenarioCount }} scenarios
              </v-chip>
            </div>
            <p class="text-body-2 text-medium-emphasis mb-0">{{ pack.description }}</p>
          </div>
        </v-card-text>
      </v-card>
    </v-radio-group>

    <!-- Hero Run button — above Advanced section -->
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
      Run Benchmark
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
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>
  </v-container>
</template>

<script setup lang="ts">
import { useBenchmarkPacks, useBenchmarkCreateRun } from '~/composables/useBenchmark'

definePageMeta({ layout: 'default' })

const route = useRoute()
const router = useRouter()

// Redirect if no target
const target = computed(() => (route.query.target as string) || 'demo')

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
}

const displayPacks = computed<DisplayPack[]>(() => {
  // User-facing descriptions — no technical jargon
  const packMeta: Record<string, { description: string; recommended: boolean; disabled: boolean }> = {
    core_security: {
      description: 'Tests prompt injection, jailbreak, data leaks, and harmful outputs. Works on any chatbot or API endpoint.',
      recommended: true,
      disabled: false,
    },
    agent_threats: {
      description: 'Tests tool abuse, role bypass, and privilege escalation. Best for tool-calling agents.',
      recommended: false,
      disabled: false,
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

  // Merge API data with our user-facing descriptions
  const apiPacks = packs.value ?? []
  const result: DisplayPack[] = []

  for (const [name, meta] of Object.entries(packMeta)) {
    const apiPack = apiPacks.find((p) => p.name === name)
    result.push({
      name,
      displayName: apiPack?.display_name ?? name.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
      description: meta.description,
      scenarioCount: apiPack?.scenario_count ?? 0,
      recommended: meta.recommended,
      disabled: meta.disabled,
    })
  }

  return result
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
