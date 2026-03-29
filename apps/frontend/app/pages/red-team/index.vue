<template>
  <v-container fluid class="red-team-page">
    <!-- Hero header -->
    <div class="mb-2 text-center text-md-start">
      <h1 class="text-h4 font-weight-bold mb-2">Find agent vulnerabilities. Then prove the fix.</h1>
      <p class="text-body-1 text-medium-emphasis" style="max-width: 640px;">
        Run a baseline scan, enable protection, re-run the same attacks — get before-vs-after proof in minutes.
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
          <span class="text-caption text-medium-emphasis">Route your endpoint through AI Protector</span>
        </v-col>
        <v-col cols="12" sm="4" class="d-flex flex-column align-center">
          <v-avatar color="warning" variant="tonal" size="44" class="mb-2">
            <v-icon icon="mdi-compare" size="22" />
          </v-avatar>
          <span class="text-subtitle-2 font-weight-bold">3. Prove</span>
          <span class="text-caption text-medium-emphasis">Re-run the same attacks and compare the result</span>
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

            <p v-if="card.helperText" class="text-caption text-medium-emphasis mt-2 mb-0" style="max-width: 280px;">
              {{ card.helperText }}
            </p>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- How it works — expandable -->
    <v-expansion-panels class="mt-6 mb-4" variant="accordion">
      <v-expansion-panel>
        <v-expansion-panel-title class="text-body-2 text-medium-emphasis">
          <v-icon icon="mdi-help-circle-outline" size="small" class="mr-2" />
          How the scan works
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <p class="text-body-2 text-medium-emphasis mb-0">
            Attack scenarios hit your endpoint directly. The baseline run shows what gets through.
            Enable protection and re-run the same attacks to see what AI Protector blocks.
          </p>
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>

    <!-- Recent proof — proof summary cards grouped by endpoint -->
    <div v-if="proofSummaries.length > 0" class="mt-6">
      <h2 class="text-subtitle-1 font-weight-medium mb-3">Your recent proof</h2>

      <!-- Filter chips -->
      <div class="d-flex ga-2 mb-3">
        <v-chip
          v-for="f in proofFilters"
          :key="f.value"
          :color="activeProofFilter === f.value ? 'primary' : undefined"
          :variant="activeProofFilter === f.value ? 'flat' : 'outlined'"
          size="small"
          @click="activeProofFilter = f.value"
        >
          {{ f.label }}
          <template v-if="f.count > 0">&nbsp;({{ f.count }})</template>
        </v-chip>
      </div>

      <!-- Proof summary cards -->
      <template v-for="proof in filteredProofSummaries" :key="proof.key">
        <v-card variant="flat" class="mb-3">
          <v-card-text class="pa-4">
            <div class="d-flex align-center justify-space-between flex-wrap ga-2">
              <!-- Left: endpoint + pack + scores -->
              <div class="d-flex align-center ga-3 flex-grow-1" style="min-width: 0;">
                <v-icon :icon="proof.icon" size="20" color="primary" class="flex-shrink-0" />
                <div style="min-width: 0;">
                  <div class="d-flex align-center ga-2 flex-wrap">
                    <span class="text-body-1 font-weight-bold">{{ proof.label }}</span>
                    <v-chip size="x-small" variant="outlined">{{ proof.pack }}</v-chip>
                  </div>
                  <div class="d-flex align-center ga-1 mt-1 flex-wrap">
                    <template v-if="proof.protectedScore !== null">
                      <span class="text-caption text-medium-emphasis">Baseline</span>
                      <span class="text-caption font-weight-medium">{{ proof.baselineScore }}</span>
                      <v-icon size="12" class="text-medium-emphasis mx-1">mdi-arrow-right</v-icon>
                      <span class="text-caption text-medium-emphasis">Protected</span>
                      <span class="text-caption font-weight-medium">{{ proof.protectedScore }}</span>
                      <v-chip
                        v-if="proof.uplift !== null"
                        :color="proof.uplift > 0 ? 'success' : 'grey'"
                        variant="tonal"
                        size="x-small"
                        class="ml-1"
                      >
                        {{ proof.uplift > 0 ? '+' : '' }}{{ proof.uplift }} pts
                      </v-chip>
                    </template>
                    <template v-else>
                      <span class="text-caption text-medium-emphasis">Baseline</span>
                      <span class="text-caption font-weight-medium">{{ proof.baselineScore }}</span>
                    </template>
                  </div>
                </div>
              </div>

              <!-- Right: status + CTA -->
              <div class="d-flex align-center ga-2 flex-shrink-0">
                <v-chip
                  :color="proof.statusColor"
                  variant="tonal"
                  size="default"
                  label
                >
                  {{ proof.statusLabel }}
                </v-chip>
                <v-btn
                  color="primary"
                  variant="flat"
                  size="small"
                  :to="proof.ctaRoute"
                >
                  {{ proof.ctaLabel }}
                </v-btn>
                <v-btn
                  v-if="proof.secondaryLabel"
                  variant="outlined"
                  size="small"
                  @click.prevent="proof.secondaryRoute ? $router.push(proof.secondaryRoute) : (proof.showHistory = !proof.showHistory)"
                >
                  {{ proof.secondaryLabel }}
                </v-btn>
              </div>
            </div>

            <!-- Expandable history -->
            <div v-if="proof.olderRunCount > 0" class="mt-2">
              <v-btn variant="text" size="x-small" color="primary" @click="proof.showHistory = !proof.showHistory">
                {{ proof.showHistory ? 'Hide history' : `View history (${proof.olderRunCount})` }}
              </v-btn>
              <v-list v-if="proof.showHistory" density="compact" class="py-0 bg-transparent mt-1">
                <v-list-item
                  v-for="r in proof.olderRuns"
                  :key="r.id"
                  :to="`/red-team/${r.status === 'running' ? 'run' : 'results'}/${r.id}`"
                  class="px-0"
                >
                  <v-list-item-title class="text-caption">
                    {{ classifyRun(r).type === 'protected' ? 'Protected' : 'Baseline' }}
                    {{ r.score_simple !== null ? `${r.score_simple}/100` : '' }}
                    · {{ timeAgo(r.completed_at ?? r.created_at) }}
                  </v-list-item-title>
                </v-list-item>
              </v-list>
            </div>
          </v-card-text>
        </v-card>
      </template>

      <!-- Empty state for filter -->
      <div v-if="filteredProofSummaries.length === 0" class="text-center pa-4">
        <p class="text-body-2 text-medium-emphasis">
          <template v-if="activeProofFilter === 'needs_protection'">
            These endpoints have baseline vulnerabilities but no protected re-run yet.
          </template>
          <template v-else>
            No matching results.
          </template>
        </p>
      </div>
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
import { humanPack, classifyRun } from '~/utils/redTeamLabels'

definePageMeta({ layout: 'default' })

interface TargetCard {
  key: string
  title: string
  description: string
  microcopy?: string
  helperText?: string
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
    description: 'Run a short attack pack against a vulnerable demo agent, then re-run the exact same scenarios with protection enabled.',
    microcopy: 'No setup · under 1 minute',
    helperText: 'Baseline results in ~30 seconds. One click to re-run with protection.',
    icon: 'mdi-play-circle-outline',
    color: 'primary',
    disabled: false,
    recommended: false,
    ctaLabel: 'Run demo scan',
    ctaIcon: 'mdi-play',
    badge: 'Fastest way to see the flow',
    hidden: false,
  },
  {
    key: 'hosted_endpoint',
    title: 'Scan your endpoint',
    description: 'Paste your endpoint URL and optional auth headers to run the same baseline test against your own system.',
    microcopy: 'No proxy required for the first scan',
    helperText: 'Baseline scans send requests directly to your endpoint — no setup or SDK needed.',
    icon: 'mdi-web',
    color: 'primary',
    disabled: false,
    recommended: true,
    ctaLabel: 'Configure endpoint',
    ctaIcon: 'mdi-cog',
    badge: 'Test your real system',
    hidden: false,
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
// Proof summaries — one card per endpoint::pack group, sorted by status
// ---------------------------------------------------------------------------

type ProofStatus = 'needs_protection' | 'protected_verified' | 'rerun_needed'

interface ProofSummary {
  key: string
  label: string
  pack: string
  icon: string
  status: ProofStatus
  statusLabel: string
  statusColor: string
  baselineScore: string
  protectedScore: string | null
  uplift: number | null
  ctaLabel: string
  ctaRoute: string
  secondaryLabel: string | null
  secondaryRoute: string | null
  latestRun: RunDetail
  olderRuns: RunDetail[]
  olderRunCount: number
  showHistory: boolean
}

const STATUS_PRIORITY: Record<ProofStatus, number> = {
  needs_protection: 0,
  rerun_needed: 1,
  protected_verified: 2,
}

const proofSummaries = computed<ProofSummary[]>(() => {
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

  const summaries: ProofSummary[] = []

  for (const [key, runs] of groups.entries()) {
    const endpoint = key.split('::')[0] ?? ''
    const packName = key.split('::')[1] ?? ''
    const isDemo = endpoint === 'demo'

    // Sort newest first
    runs.sort((a, b) => {
      const ta = new Date(b.completed_at ?? b.created_at ?? 0).getTime()
      const tb = new Date(a.completed_at ?? a.created_at ?? 0).getTime()
      return ta - tb
    })

    const baselines = runs.filter((r) => classifyRun(r).type === 'baseline' && r.score_simple != null)
    const protectedRuns = runs.filter((r) => classifyRun(r).type === 'protected' && r.score_simple != null)

    let status: ProofStatus = 'needs_protection'
    let statusLabel = 'Needs protection'
    let statusColor = 'warning'

    if (protectedRuns.length > 0 && baselines.length > 0) {
      status = 'protected_verified'
      statusLabel = 'Protected · verified'
      statusColor = 'success'
    } else if (protectedRuns.length > 0) {
      status = 'rerun_needed'
      statusLabel = 'Re-run needed'
      statusColor = 'info'
    }

    // Calculate scores
    const bestBaseline = baselines.length > 0 ? Math.max(...baselines.map((r) => r.score_simple!)) : null
    const bestProtected = protectedRuns.length > 0 ? Math.max(...protectedRuns.map((r) => r.score_simple!)) : null
    const uplift = bestBaseline != null && bestProtected != null ? bestProtected - bestBaseline : null

    const latestRun = runs[0]!
    const latestRoute = `/red-team/${latestRun.status === 'running' ? 'run' : 'results'}/${latestRun.id}`

    let ctaLabel = 'View baseline'
    const ctaRoute = latestRoute
    if (status === 'protected_verified') {
      ctaLabel = 'View proof'
    } else if (status === 'rerun_needed') {
      ctaLabel = 'View latest'
    }

    let secondaryLabel: string | null = null
    let secondaryRoute: string | null = null
    if (status === 'needs_protection') {
      secondaryLabel = 'Enable protection'
      secondaryRoute = latestRoute
    } else if (status === 'rerun_needed') {
      secondaryLabel = 'Re-run protected scan'
      secondaryRoute = isDemo
        ? '/red-team/configure?target=demo'
        : `/red-team/target?type=${latestRun.target_type}`
    }

    summaries.push({
      key,
      label: isDemo ? 'Demo Endpoint' : truncateLabel(endpoint, 50),
      pack: humanPack(packName),
      icon: isDemo ? 'mdi-robot-outline' : 'mdi-web',
      status,
      statusLabel,
      statusColor,
      baselineScore: bestBaseline != null ? `${bestBaseline}/100` : '—',
      protectedScore: bestProtected != null ? `${bestProtected}/100` : null,
      uplift,
      ctaLabel,
      ctaRoute,
      secondaryLabel,
      secondaryRoute,
      latestRun,
      olderRuns: runs.slice(1, 7),
      olderRunCount: Math.max(0, runs.length - 1),
      showHistory: false,
    })
  }

  // Sort: needs_protection first, then rerun_needed, then protected_verified
  summaries.sort((a, b) => STATUS_PRIORITY[a.status] - STATUS_PRIORITY[b.status])
  return summaries
})

// ---------------------------------------------------------------------------
// Proof filter chips
// ---------------------------------------------------------------------------
const activeProofFilter = ref<'all' | ProofStatus>('all')

const proofFilters = computed(() => {
  const counts = { needs_protection: 0, protected_verified: 0, rerun_needed: 0 }
  for (const p of proofSummaries.value) counts[p.status]++
  return [
    { label: 'All', value: 'all' as const, count: proofSummaries.value.length },
    { label: 'Needs protection', value: 'needs_protection' as const, count: counts.needs_protection },
    { label: 'Verified', value: 'protected_verified' as const, count: counts.protected_verified },
    { label: 'Re-run needed', value: 'rerun_needed' as const, count: counts.rerun_needed },
  ]
})

const filteredProofSummaries = computed(() => {
  if (activeProofFilter.value === 'all') return proofSummaries.value
  return proofSummaries.value.filter((p) => p.status === activeProofFilter.value)
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
