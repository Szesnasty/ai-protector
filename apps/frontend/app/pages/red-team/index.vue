<template>
  <v-container fluid class="red-team-page">
    <!-- Hero header -->
    <div class="mb-2 text-center text-md-start">
      <h1 class="text-h4 font-weight-bold mb-2">Find agent vulnerabilities. Then prove the fix.</h1>
      <p class="text-body-1 text-medium-emphasis" style="max-width: 640px;">
        Run a baseline scan to see what gets through, enable AI Protector, and re-run to prove the difference.
      </p>
    </div>

    <!-- 3-step process strip -->
    <v-card variant="flat" class="mb-8 pa-4">
      <v-row align="center" justify="center" class="text-center">
        <v-col cols="12" sm="4" class="d-flex flex-column align-center">
          <v-avatar color="primary" variant="tonal" size="44" class="mb-2">
            <v-icon icon="mdi-magnify-scan" size="22" />
          </v-avatar>
          <span class="text-subtitle-2 font-weight-bold">1. Scan</span>
          <span class="text-caption text-medium-emphasis">Run attacks against your endpoint</span>
        </v-col>
        <v-col cols="12" sm="4" class="d-flex flex-column align-center">
          <v-avatar color="success" variant="tonal" size="44" class="mb-2">
            <v-icon icon="mdi-shield-check" size="22" />
          </v-avatar>
          <span class="text-subtitle-2 font-weight-bold">2. Protect</span>
          <span class="text-caption text-medium-emphasis">Enable AI Protector in one click</span>
        </v-col>
        <v-col cols="12" sm="4" class="d-flex flex-column align-center">
          <v-avatar color="warning" variant="tonal" size="44" class="mb-2">
            <v-icon icon="mdi-compare" size="22" />
          </v-avatar>
          <span class="text-subtitle-2 font-weight-bold">3. Prove</span>
          <span class="text-caption text-medium-emphasis">Re-run and see the before vs after</span>
        </v-col>
      </v-row>
    </v-card>

    <!-- Target cards -->
    <v-row>
      <v-col
        v-for="card in visibleCards"
        :key="card.key"
        cols="12"
        sm="6"
        md="6"
      >
        <v-card
          variant="flat"
          hover
          :disabled="card.disabled"
          :class="[
            'target-card',
            { 'card--disabled': card.disabled },
            { 'card--recommended': card.recommended },
          ]"
          @click="card.disabled ? null : onCardClick(card.key)"
        >
          <v-card-text class="d-flex flex-column align-center text-center pa-6">
            <v-chip
              v-if="card.badge"
              size="x-small"
              color="primary"
              variant="tonal"
              class="mb-2"
            >
              {{ card.badge }}
            </v-chip>

            <v-avatar :color="card.color" variant="tonal" size="56" class="mb-3">
              <v-icon :icon="card.icon" size="28" />
            </v-avatar>

            <span class="text-subtitle-1 font-weight-bold mb-1">
              {{ card.title }}
            </span>

            <p class="text-body-2 text-medium-emphasis mb-1" style="min-height: 40px;">
              {{ card.description }}
            </p>

            <p v-if="card.microcopy" class="text-caption text-primary mb-3">
              {{ card.microcopy }}
            </p>

            <v-btn
              v-if="!card.disabled"
              :color="card.recommended ? 'primary' : 'default'"
              :variant="card.recommended ? 'flat' : 'outlined'"
              size="default"
              :prepend-icon="card.ctaIcon"
            >
              {{ card.ctaLabel }}
            </v-btn>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- How it works — expandable -->
    <v-expansion-panels class="mt-6 mb-4" variant="accordion">
      <v-expansion-panel>
        <v-expansion-panel-title class="text-body-2 text-medium-emphasis">
          <v-icon icon="mdi-help-circle-outline" size="small" class="mr-2" />
          How does the security scan work?
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <div class="text-body-2 text-medium-emphasis">
            <p class="mb-2">AI Protector sends a curated set of adversarial prompts — prompt injections, jailbreak attempts, data leakage probes, and tool abuse scenarios — to your endpoint or our demo target.</p>
            <p class="mb-2">Each response is analysed by an AI judge that determines whether the attack succeeded or was safely handled. The result is a per-category breakdown of what got through.</p>
            <p class="mb-0">When you enable protection and re-run, the same attacks go through the AI Protector firewall first. The before-vs-after comparison proves exactly which vulnerabilities were fixed.</p>
          </div>
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>

    <!-- Security improvements — grouped by endpoint -->
    <div v-if="recentRuns && recentRuns.length > 0" class="mt-6">
      <h2 class="text-subtitle-1 font-weight-medium mb-3">Your recent proof</h2>

      <!-- Grouped endpoint pairs -->
      <template v-for="group in endpointGroups" :key="group.key">
        <v-card variant="flat" class="mb-4">
          <v-card-text class="pa-4">
            <!-- Endpoint group header -->
            <div class="d-flex align-center mb-3">
              <v-icon :icon="group.icon" size="small" class="mr-2" color="primary" />
              <span class="text-subtitle-2 font-weight-bold">{{ group.label }}</span>
              <v-chip
                v-if="group.uplift !== null"
                :color="group.uplift > 0 ? 'success' : 'grey'"
                variant="tonal"
                size="x-small"
                class="ml-2"
              >
                {{ group.uplift > 0 ? '+' : '' }}{{ group.uplift }} pts
              </v-chip>
            </div>

            <!-- Runs in this group -->
            <v-list density="compact" class="py-0 bg-transparent">
              <v-list-item
                v-for="run in group.runs"
                :key="run.id"
                :to="`/red-team/${run.status === 'running' ? 'run' : 'results'}/${run.id}`"
                class="px-0"
              >
                <template #prepend>
                  <v-icon
                    :icon="classifyRun(run).icon"
                    :color="classifyRun(run).color"
                    size="small"
                    class="mr-3"
                  />
                </template>
                <v-list-item-title class="text-body-2 font-weight-medium">
                  {{ humanPack(run.pack) }}
                  <v-chip
                    v-if="run.score_simple !== null && run.score_simple !== undefined"
                    :color="classifyRun(run).type === 'protected' ? scoreLabel(run.score_simple).vuetifyColor : 'blue-grey'"
                    variant="tonal"
                    size="x-small"
                    class="ml-2"
                  >
                    {{ run.score_simple }}/100
                  </v-chip>
                  <v-chip
                    v-else-if="run.status === 'running'"
                    color="primary"
                    variant="tonal"
                    size="x-small"
                    class="ml-2"
                  >
                    Running...
                  </v-chip>
                </v-list-item-title>
                <v-list-item-subtitle class="text-caption">
                  {{ timeAgo(run.completed_at ?? run.created_at) }}
                  <v-chip
                    :color="classifyRun(run).color"
                    variant="outlined"
                    size="x-small"
                    class="ml-1"
                  >
                    {{ classifyRun(run).type === 'protected' ? 'Protected' : 'Baseline' }}
                  </v-chip>
                  <span class="ml-1">
                    {{ run.passed }}/{{ run.executed }}
                    {{ classifyRun(run).type === 'protected' ? 'blocked' : 'handled' }}
                  </span>
                </v-list-item-subtitle>
                <template #append>
                  <v-btn variant="text" size="x-small" color="primary">View</v-btn>
                </template>
              </v-list-item>
            </v-list>
          </v-card-text>
        </v-card>
      </template>
    </div>

    <!-- Loading runs -->
    <div v-else-if="runsLoading" class="mt-8 text-center">
      <v-progress-circular indeterminate color="primary" size="24" />
    </div>

    <!-- Empty state -->
    <div v-else class="mt-8 text-center">
      <v-icon icon="mdi-shield-search" size="48" color="primary" class="mb-3" style="opacity: 0.4;" />
      <p class="text-body-2 text-medium-emphasis">
        No scans yet. Run a demo scan to see your first results in under a minute.
      </p>
    </div>
  </v-container>
</template>

<script setup lang="ts">
import { benchmarkService } from '~/services/benchmarkService'
import type { RunDetail } from '~/services/benchmarkService'
import { humanPack, scoreLabel, classifyRun } from '~/utils/redTeamLabels'

definePageMeta({ layout: 'default' })

interface TargetCard {
  key: string
  title: string
  description: string
  microcopy?: string
  icon: string
  color: string
  disabled: boolean
  recommended: boolean
  disabledNote?: string
  ctaLabel: string
  ctaIcon: string
  badge?: string
  hidden: boolean
}

const targetCards: TargetCard[] = [
  {
    key: 'demo',
    title: 'Try the demo scan',
    description: 'Attack our sample endpoint and see what gets through. No setup, under a minute.',
    microcopy: 'Best first step — see results instantly',
    icon: 'mdi-play-circle-outline',
    color: 'primary',
    disabled: false,
    recommended: true,
    ctaLabel: 'Run demo scan',
    ctaIcon: 'mdi-play',
    badge: 'No setup needed',
    hidden: false,
  },
  {
    key: 'hosted_endpoint',
    title: 'Scan your endpoint',
    description: 'Point AI Protector at your own AI endpoint to find real vulnerabilities.',
    icon: 'mdi-web',
    color: 'info',
    disabled: false,
    recommended: false,
    ctaLabel: 'Configure endpoint',
    ctaIcon: 'mdi-cog',
    hidden: false,
  },
  {
    key: 'local_agent',
    title: 'Local Agent',
    description: 'Test before you deploy. Agent running on localhost.',
    icon: 'mdi-laptop',
    color: 'secondary',
    disabled: false,
    recommended: false,
    ctaLabel: 'Configure',
    ctaIcon: 'mdi-cog',
    hidden: true,
  },
  {
    key: 'registered_agent',
    title: 'Registered Agent',
    description: 'Deeper protection and tracing.',
    icon: 'mdi-shield-check',
    color: 'success',
    disabled: true,
    recommended: false,
    disabledNote: 'Available in next iteration',
    ctaLabel: 'Coming soon',
    ctaIcon: 'mdi-shield-check',
    hidden: true,
  },
]

const visibleCards = computed(() => targetCards.filter((c) => !c.hidden))

const router = useRouter()

function onCardClick(key: string) {
  if (key === 'demo') {
    router.push('/red-team/configure?target=demo')
  } else if (key === 'local_agent' || key === 'hosted_endpoint') {
    router.push(`/red-team/target?type=${key}`)
  }
}

// Recent runs
const recentRuns = ref<RunDetail[]>([])
const runsLoading = ref(true)

async function fetchRecentRuns() {
  runsLoading.value = true
  try {
    recentRuns.value = await benchmarkService.listRuns(20)
  } catch {
    recentRuns.value = []
  } finally {
    runsLoading.value = false
  }
}

// ---------------------------------------------------------------------------
// Group runs by endpoint + pack for "Your recent proof" section
// ---------------------------------------------------------------------------

interface EndpointGroup {
  key: string
  label: string
  icon: string
  runs: RunDetail[]
  uplift: number | null // score delta between best baseline and best protected
}

const endpointGroups = computed<EndpointGroup[]>(() => {
  const groups = new Map<string, RunDetail[]>()

  for (const run of recentRuns.value) {
    const endpoint = run.target_type === 'demo' || run.target_type === 'demo_agent'
      ? 'demo'
      : (run.target_label || run.target_type)
    const key = `${endpoint}::${run.pack}`
    const list = groups.get(key) ?? []
    list.push(run)
    groups.set(key, list)
  }

  const result: EndpointGroup[] = []
  for (const [key, runs] of groups.entries()) {
    const endpoint = key.split('::')[0] ?? ''
    const isDemo = endpoint === 'demo'

    // Sort newest first
    runs.sort((a, b) => {
      const ta = new Date(b.completed_at ?? b.created_at ?? 0).getTime()
      const tb = new Date(a.completed_at ?? a.created_at ?? 0).getTime()
      return ta - tb
    })

    // Calculate uplift
    const baselines = runs.filter((r) => classifyRun(r).type === 'baseline' && r.score_simple != null)
    const protectedRuns = runs.filter((r) => classifyRun(r).type === 'protected' && r.score_simple != null)
    let uplift: number | null = null
    if (baselines.length > 0 && protectedRuns.length > 0) {
      const bestBaseline = Math.max(...baselines.map((r) => r.score_simple!))
      const bestProtected = Math.max(...protectedRuns.map((r) => r.score_simple!))
      uplift = bestProtected - bestBaseline
    }

    result.push({
      key,
      label: isDemo ? 'Demo Endpoint' : truncateLabel(endpoint, 50),
      icon: isDemo ? 'mdi-robot-outline' : 'mdi-web',
      runs: runs.slice(0, 6), // max 6 per group
      uplift,
    })
  }

  return result
})

function timeAgo(ts: string | null | undefined): string {
  if (!ts) return ''
  const diff = Math.round((Date.now() - new Date(ts).getTime()) / 1000)
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.round(diff / 60)} min ago`
  if (diff < 86400) return `${Math.round(diff / 3600)}h ago`
  return `${Math.round(diff / 86400)}d ago`
}

function truncateLabel(label: string, max = 40): string {
  if (!label) return ''
  try {
    const u = new URL(label)
    const short = u.host + (u.pathname.length > 1 ? u.pathname : '')
    return short.length > max ? short.slice(0, max) + '…' : short
  } catch {
    return label.length > max ? label.slice(0, max) + '…' : label
  }
}

onMounted(() => {
  fetchRecentRuns()
})
</script>

<style lang="scss" scoped>
.target-card {
  transition: transform 0.15s ease, box-shadow 0.15s ease;

  &:not(.card--disabled):hover {
    transform: translateY(-2px);
  }
}

.card--disabled {
  opacity: 0.5;
  cursor: default;
}

.card--recommended {
  border: 2px solid rgb(var(--v-theme-primary));
}
</style>
