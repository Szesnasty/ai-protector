<template>
  <v-container fluid class="configure-page">
    <!-- Header -->
    <div class="mb-6">
      <div class="d-flex align-center mb-1">
        <v-btn icon="mdi-arrow-left" variant="text" size="small" class="mr-2" :to="'/red-team'" />
        <h1 class="text-h5">Run baseline scan</h1>
        <v-chip v-if="target === 'demo'" color="purple" variant="tonal" size="small" prepend-icon="mdi-robot" class="ml-3" label>
          Demo
        </v-chip>
      </div>
      <p class="text-body-2 text-medium-emphasis mt-2" style="max-width: 540px;">
        Attacks go directly to your endpoint — no protection active. You’ll enable protection and re-run after seeing results.
      </p>
      <div class="d-flex align-center mt-2">
        <span class="text-body-2 text-medium-emphasis mr-2">Target:</span>
        <v-chip color="primary" variant="tonal" size="small" :prepend-icon="targetIcon">{{ targetLabel }}</v-chip>
        <v-btn variant="text" size="x-small" class="ml-2" :to="'/red-team'">Change</v-btn>
      </div>
    </div>

    <!-- Attack selection -->
    <div class="d-flex align-center justify-space-between mb-1">
      <h2 class="text-h6">Choose attacks by threat</h2>
      <div>
        <v-btn variant="text" size="x-small" @click="selectAll">All</v-btn>
        <v-btn variant="text" size="x-small" @click="selectNone">None</v-btn>
      </div>
    </div>
    <p class="text-body-2 text-medium-emphasis mb-3">
      Pick whole OWASP categories, or expand to a corpus and its attack types. Each subtype shows which corpus it comes from.
    </p>

    <v-progress-linear v-if="categoriesLoading" indeterminate color="primary" class="mb-3" />

    <AttackTreeSelector v-model="selectedKeys" :categories="categories" class="mb-6" />

    <!-- Sample size — reproducibility control -->
    <v-card variant="flat" class="mb-4 mt-2 pa-4">
      <div class="d-flex align-center justify-space-between mb-2">
        <div>
          <span class="text-subtitle-2 font-weight-bold">Sample size</span>
          <p class="text-caption text-medium-emphasis mb-0">
            Bounded, deterministic subset per category — same seed gives the exact same attacks every run.
          </p>
        </div>
        <v-switch v-model="runAll" color="primary" density="compact" hide-details label="Run all" />
      </div>
      <div v-if="!runAll" class="d-flex align-center ga-4">
        <v-slider v-model="samplePerCategory" :min="5" :max="100" :step="5" thumb-label hide-details color="primary" class="flex-grow-1" />
        <span class="text-body-2 text-medium-emphasis" style="min-width: 90px;">{{ samplePerCategory }} / category</span>
      </div>
    </v-card>

    <!-- Summary -->
    <v-alert v-if="totalAttacks > 0" color="primary" variant="tonal" density="compact" class="mb-4">
      <template #prepend><v-icon icon="mdi-information-outline" /></template>
      <strong>{{ totalAttacks }}</strong> attacks across <strong>{{ categoriesTouched }}</strong>
      {{ categoriesTouched === 1 ? 'category' : 'categories' }} · ~{{ estimateTime(totalAttacks) }} · reproducible (seed {{ seed }})
    </v-alert>
    <v-alert v-else type="warning" variant="tonal" density="compact" class="mb-4">
      Select at least one threat category to run a scan.
    </v-alert>

    <!-- Run -->
    <div class="d-flex flex-column align-center mb-2">
      <v-btn
        color="primary"
        size="large"
        class="run-button px-12"
        prepend-icon="mdi-magnify-scan"
        :loading="isCreating"
        :disabled="totalAttacks === 0 || isCreating"
        data-testid="run-benchmark-btn"
        @click="onRunBenchmark"
      >
        Run baseline scan
      </v-btn>
    </div>

    <!-- What happens next -->
    <v-card variant="flat" class="mb-6 pa-4 mt-4">
      <h3 class="text-subtitle-2 font-weight-bold mb-3">What happens next</h3>
      <div class="d-flex flex-column ga-2">
        <div class="d-flex align-start">
          <v-avatar color="primary" variant="tonal" size="24" class="mr-3 flex-shrink-0"><span class="text-caption font-weight-bold">1</span></v-avatar>
          <span class="text-body-2 text-medium-emphasis">We send adversarial attacks to your endpoint and measure what gets through.</span>
        </div>
        <div class="d-flex align-start">
          <v-avatar color="success" variant="tonal" size="24" class="mr-3 flex-shrink-0"><span class="text-caption font-weight-bold">2</span></v-avatar>
          <span class="text-body-2 text-medium-emphasis">You see which attacks got through — then route your endpoint through AI Protector.</span>
        </div>
        <div class="d-flex align-start">
          <v-avatar color="warning" variant="tonal" size="24" class="mr-3 flex-shrink-0"><span class="text-caption font-weight-bold">3</span></v-avatar>
          <span class="text-body-2 text-medium-emphasis">Re-run the same scan and get a before-vs-after comparison proving which vulnerabilities were fixed.</span>
        </div>
      </div>
    </v-card>

    <v-alert v-if="runError" type="error" variant="tonal" closable class="mb-4" @click:close="runError = null">
      {{ runError }}
    </v-alert>

    <!-- Advanced -->
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
          <v-text-field
            v-model.number="seed"
            type="number"
            label="Sampling seed"
            variant="outlined"
            density="compact"
            class="mt-4"
            hint="Same seed → the exact same attack set (reproducible). Change it to draw a different subset."
            persistent-hint
          />
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>
  </v-container>
</template>

<script setup lang="ts">
import AttackTreeSelector from '~/components/red-team/AttackTreeSelector.vue'
import { useBenchmarkCategories, useBenchmarkCreateRun } from '~/composables/useBenchmark'
import type { CategoryInfo } from '~/services/benchmarkService'
import { allKeys, buildFilters, buildPacks, countsByCategory, totalSelected } from '~/utils/attackSelection'

definePageMeta({ layout: 'default' })

const route = useRoute()
const router = useRouter()

const target = computed(() => (route.query.target as string) || 'demo')
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

const { categories: rawCategories, isLoading: categoriesLoading } = useBenchmarkCategories()
const categories = computed<CategoryInfo[]>(() => rawCategories.value ?? [])

const selectedKeys = ref<Set<string>>(new Set())
const selectedPolicy = ref((route.query.policy as string) || 'balanced')
const advancedPanel = ref<string | undefined>(undefined)
const runError = ref<string | null>(null)
const runAll = ref(false)
const samplePerCategory = ref(15)
const seed = ref(1337)

const policyOptions = [
  { label: 'Fast', value: 'fast' },
  { label: 'Balanced (default)', value: 'balanced' },
  { label: 'Strict', value: 'strict' },
  { label: 'Paranoid', value: 'paranoid' },
]

// Default: all categories selected (user trims down).
watch(categories, (cats) => {
  if (cats.length > 0 && selectedKeys.value.size === 0) {
    selectedKeys.value = allKeys(cats)
  }
}, { immediate: true })

function selectAll(): void {
  selectedKeys.value = allKeys(categories.value)
}
function selectNone(): void {
  selectedKeys.value = new Set()
}

const samplerCap = computed(() => (runAll.value ? null : samplePerCategory.value))
const totalAttacks = computed(() => totalSelected(selectedKeys.value, categories.value, samplerCap.value))
const categoriesTouched = computed(() => countsByCategory(selectedKeys.value, categories.value).size)

function estimateTime(count: number): string {
  const sec = Math.round(count * 4.5)
  return sec < 60 ? `${sec}s` : `${Math.ceil(sec / 60)} min`
}

const { createRun, isCreating } = useBenchmarkCreateRun()

async function onRunBenchmark() {
  runError.value = null
  try {
    const targetConfig: Record<string, unknown> = {}
    if (target.value !== 'demo') {
      targetConfig.endpoint_url = endpointUrl.value
      targetConfig.agent_type = agentType.value
      targetConfig.timeout_s = timeoutS.value
      targetConfig.safe_mode = safeMode.value
      if (targetName.value) targetConfig.target_name = targetName.value
      if (environment.value) targetConfig.environment = environment.value

      const { take } = useEphemeralHeaders()
      const ephemeralHeaders = take()
      if (ephemeralHeaders) targetConfig.custom_headers = ephemeralHeaders

      const { load, clear: clearScanConfig } = useScanConfig()
      const scanCfg = load()
      if (scanCfg.requestTemplate) targetConfig.request_template = scanCfg.requestTemplate
      if (scanCfg.responseTextPaths.length > 0) targetConfig.response_text_paths = scanCfg.responseTextPaths
      clearScanConfig()
    }

    const result = await createRun({
      target_type: target.value,
      target_config: targetConfig,
      pack: 'selection',
      packs: buildPacks(selectedKeys.value, categories.value),
      filters: buildFilters(selectedKeys.value, categories.value),
      sample_per_category: runAll.value ? undefined : samplePerCategory.value,
      seed: seed.value,
      policy: selectedPolicy.value,
    })
    router.push(`/red-team/run/${result.id}`)
  } catch (err: unknown) {
    runError.value = (err as { message?: string })?.message ?? 'Failed to create benchmark run'
  }
}
</script>

<style lang="scss" scoped>
.run-button {
  font-weight: 600;
  letter-spacing: 0.02em;
}
</style>
