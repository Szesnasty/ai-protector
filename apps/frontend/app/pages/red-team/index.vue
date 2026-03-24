<template>
  <v-container fluid class="red-team-page">
    <!-- Header -->
    <div class="mb-6">
      <h1 class="text-h5 mb-1">Red Team — Security Tests</h1>
      <p class="text-body-2 text-medium-emphasis">
        Test your AI endpoint in minutes. No setup for demo. URL-only for your own endpoint.
      </p>
    </div>

    <!-- Target cards -->
    <v-row>
      <v-col
        v-for="card in targetCards"
        :key="card.key"
        cols="12"
        sm="6"
        md="6"
        lg="3"
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
            <!-- Recommended badge -->
            <v-chip
              v-if="card.recommended"
              size="x-small"
              color="primary"
              variant="tonal"
              class="mb-2"
            >
              ★ Recommended
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

            <v-chip
              v-if="card.disabled"
              size="small"
              variant="tonal"
              color="grey"
            >
              Coming soon
            </v-chip>
            <p v-if="card.disabled && card.disabledNote" class="text-caption text-medium-emphasis mt-2 mb-0">
              {{ card.disabledNote }}
            </p>
            <v-btn
              v-if="!card.disabled"
              :color="card.recommended ? 'primary' : 'default'"
              :variant="card.recommended ? 'flat' : 'outlined'"
              :size="card.recommended ? 'default' : 'small'"
              :prepend-icon="card.key === 'demo' ? 'mdi-play' : 'mdi-cog'"
            >
              {{ card.key === 'demo' ? 'Start Now' : 'Configure' }}
            </v-btn>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Recent Runs -->
    <div class="mt-10">
      <h2 class="text-h6 mb-3">Recent Runs</h2>

      <!-- Loading -->
      <v-card v-if="runsLoading" variant="flat" class="pa-6 text-center">
        <v-progress-circular indeterminate color="primary" size="32" />
      </v-card>

      <!-- Empty state -->
      <v-card v-else-if="!recentRuns || recentRuns.length === 0" variant="flat" class="pa-6 text-center">
        <v-icon icon="mdi-test-tube-empty" size="48" color="grey" class="mb-3" />
        <p class="text-body-2 text-medium-emphasis mb-2">
          Run your first benchmark to see history and compare improvements.
        </p>
        <v-btn
          color="primary"
          variant="tonal"
          size="small"
          prepend-icon="mdi-play"
          @click="onCardClick('demo')"
        >
          Start with Demo Agent
        </v-btn>
      </v-card>

      <!-- Runs list -->
      <v-card v-else variant="flat">
        <v-list density="compact">
          <v-list-item
            v-for="run in recentRuns"
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
              {{ run.target_type === 'demo' ? 'Demo Agent' : run.target_type }}
              &nbsp;·&nbsp; {{ timeAgo(run.completed_at ?? run.created_at) }}
              &nbsp;·&nbsp; {{ run.passed }}/{{ run.executed }} blocked
            </v-list-item-subtitle>
          </v-list-item>
        </v-list>
      </v-card>
    </div>
  </v-container>
</template>

<script setup lang="ts">
import { benchmarkService } from '~/services/benchmarkService'
import type { RunDetail } from '~/services/benchmarkService'
import { humanPack, scoreLabel } from '~/utils/redTeamLabels'

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
}

const targetCards: TargetCard[] = [
  {
    key: 'demo',
    title: 'Demo Agent',
    description: 'Test a pre-configured demo agent — zero config required.',
    microcopy: 'Get your first score in under 1 minute',
    icon: 'mdi-robot',
    color: 'primary',
    disabled: false,
    recommended: true,
  },
  {
    key: 'local_agent',
    title: 'Local Agent',
    description: 'Test before you deploy. Agent running on localhost.',
    icon: 'mdi-laptop',
    color: 'secondary',
    disabled: false,
    recommended: false,
  },
  {
    key: 'hosted_endpoint',
    title: 'Hosted Endpoint',
    description: 'Test a real staging or internal endpoint.',
    icon: 'mdi-web',
    color: 'info',
    disabled: false,
    recommended: false,
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
  },
]

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
    recentRuns.value = await benchmarkService.listRuns(5)
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
