<template>
  <v-container fluid class="red-team-page">
    <!-- Header -->
    <div class="mb-6">
      <h1 class="text-h5 mb-1">Security Tests</h1>
      <p class="text-body-2 text-medium-emphasis">
        Run a baseline benchmark to see how your model behaves without protection, then add AI Protector to measure the difference.
      </p>
    </div>

    <!-- Primary cards — simplified to 2 main paths -->
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
            <!-- Best first step badge for demo -->
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

    <!-- Hidden legacy cards preserved in data but not rendered above.
         To restore: set card.hidden = false or use showAllCards = true -->

    <!-- Recent Runs — compact (max 8) -->
    <div v-if="recentRuns && recentRuns.length > 0" class="mt-8">
      <h2 class="text-subtitle-1 font-weight-medium mb-2">Recent Runs</h2>

      <v-card variant="flat">
        <v-list density="compact" class="py-0">
          <v-list-item
            v-for="run in compactRuns"
            :key="run.id"
            :to="`/red-team/${run.status === 'running' ? 'run' : 'results'}/${run.id}`"
            class="px-4"
          >
            <template #prepend>
              <v-icon
                :icon="runStatusIcon(run.status)"
                :color="runStatusColor(run.status)"
                size="small"
                class="mr-3"
              />
            </template>
            <v-list-item-title class="text-body-2 font-weight-medium">
              {{ humanPack(run.pack) }}
              <v-chip
                v-if="run.score_simple !== null && run.score_simple !== undefined"
                :color="scoreLabel(run.score_simple).vuetifyColor"
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
              {{ run.target_type === 'demo' ? 'Demo' : run.target_type }}
              &nbsp;·&nbsp; {{ timeAgo(run.completed_at ?? run.created_at) }}
              &nbsp;·&nbsp; {{ run.passed }}/{{ run.executed }} {{ classifyRun(run).type === 'baseline' ? 'handled' : 'blocked' }}
              <v-chip
                :color="classifyRun(run).color"
                variant="outlined"
                size="x-small"
                class="ml-1"
              >
                {{ classifyRun(run).type === 'protected' ? 'Protected by AI Protector' : classifyRun(run).label }}
              </v-chip>
            </v-list-item-subtitle>
            <template #append>
              <v-btn variant="text" size="x-small" color="primary">View</v-btn>
            </template>
          </v-list-item>
        </v-list>
        <div v-if="recentRuns.length > 8" class="text-center py-2">
          <v-btn variant="text" size="small" color="primary" to="/red-team/runs">
            View all runs
          </v-btn>
        </div>
      </v-card>
    </div>

    <!-- Loading runs -->
    <div v-else-if="runsLoading" class="mt-8 text-center">
      <v-progress-circular indeterminate color="primary" size="24" />
    </div>

    <!-- Empty state — minimal -->
    <div v-else class="mt-8 text-center">
      <p class="text-body-2 text-medium-emphasis">
        No runs yet. Start a demo benchmark to see your first score.
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
  /** Small badge shown above the icon (e.g. "No setup") */
  badge?: string
  /** When true, card is kept in data but hidden from the main view */
  hidden: boolean
}

// Toggle to show all legacy cards (set to true to restore old 4-card view)
const _showAllCards = false

const targetCards: TargetCard[] = [
  {
    key: 'demo',
    title: 'Run Demo',
    description: 'See a sample benchmark in under a minute. No setup required.',
    microcopy: 'Get your first score instantly',
    icon: 'mdi-play-circle-outline',
    color: 'primary',
    disabled: false,
    recommended: true,
    ctaLabel: 'Start Demo',
    ctaIcon: 'mdi-play',
    badge: 'No setup needed',
    hidden: false,
  },
  {
    key: 'hosted_endpoint',
    title: 'Test Your Endpoint',
    description: 'Run security tests on your own AI endpoint using a URL and optional auth.',
    icon: 'mdi-web',
    color: 'info',
    disabled: false,
    recommended: false,
    ctaLabel: 'Configure Endpoint',
    ctaIcon: 'mdi-cog',
    hidden: false,
  },
  // --- Hidden cards (still in data, easy to re-enable) ---
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
    hidden: true, // hidden from main view — set to false to restore
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
    hidden: true, // hidden from main view — set to false to restore
  },
]

/** Only non-hidden cards are rendered */
const visibleCards = computed(() =>
  _showAllCards ? targetCards : targetCards.filter((c) => !c.hidden),
)

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

/** Only show 8 in the compact view */
const compactRuns = computed(() => recentRuns.value.slice(0, 8))

async function fetchRecentRuns() {
  runsLoading.value = true
  try {
    recentRuns.value = await benchmarkService.listRuns(10)
  } catch {
    recentRuns.value = []
  } finally {
    runsLoading.value = false
  }
}

function runStatusIcon(status: string): string {
  if (status === 'completed') return 'mdi-check-circle'
  if (status === 'running') return 'mdi-loading mdi-spin'
  if (status === 'failed') return 'mdi-close-circle'
  if (status === 'cancelled') return 'mdi-cancel'
  return 'mdi-clock-outline'
}

function runStatusColor(status: string): string {
  if (status === 'completed') return 'success'
  if (status === 'running') return 'primary'
  if (status === 'failed') return 'error'
  if (status === 'cancelled') return 'grey'
  return 'grey'
}

function timeAgo(ts: string | null | undefined): string {
  if (!ts) return ''
  const diff = Math.round((Date.now() - new Date(ts).getTime()) / 1000)
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.round(diff / 60)} min ago`
  if (diff < 86400) return `${Math.round(diff / 3600)}h ago`
  return `${Math.round(diff / 86400)}d ago`
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
