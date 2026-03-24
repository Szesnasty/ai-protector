<template>
  <v-container fluid class="red-team-page">
    <!-- Header -->
    <div class="mb-6">
      <h1 class="text-h5 mb-1">Red Team — Security Tests</h1>
      <p class="text-body-2 text-medium-emphasis">
        Test your AI endpoint in minutes.
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
          :class="{ 'card--disabled': card.disabled }"
          class="target-card"
          @click="card.disabled ? null : onCardClick(card.key)"
        >
          <v-card-text class="d-flex flex-column align-center text-center pa-6">
            <v-avatar :color="card.color" variant="tonal" size="56" class="mb-3">
              <v-icon :icon="card.icon" size="28" />
            </v-avatar>

            <span class="text-subtitle-1 font-weight-bold mb-1">
              {{ card.title }}
            </span>

            <p class="text-body-2 text-medium-emphasis mb-3" style="min-height: 40px;">
              {{ card.description }}
            </p>

            <v-chip
              v-if="card.disabled"
              size="small"
              variant="tonal"
              color="grey"
            >
              Coming soon
            </v-chip>
            <v-btn
              v-else
              color="primary"
              variant="flat"
              size="small"
              :prepend-icon="card.key === 'demo' ? 'mdi-play' : 'mdi-cog'"
            >
              {{ card.key === 'demo' ? 'Start' : 'Configure' }}
            </v-btn>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Recent Runs placeholder -->
    <div class="mt-10">
      <h2 class="text-h6 mb-3">Recent Runs</h2>
      <v-card variant="flat" class="pa-6 text-center">
        <v-icon icon="mdi-test-tube-empty" size="48" color="grey" class="mb-3" />
        <p class="text-body-2 text-medium-emphasis">
          No benchmark runs yet. Start one above!
        </p>
      </v-card>
    </div>
  </v-container>
</template>

<script setup lang="ts">
definePageMeta({ layout: 'default' })

interface TargetCard {
  key: string
  title: string
  description: string
  icon: string
  color: string
  disabled: boolean
}

const targetCards: TargetCard[] = [
  {
    key: 'demo',
    title: 'Demo Agent',
    description: 'Test a pre-configured demo agent — zero config required.',
    icon: 'mdi-robot',
    color: 'primary',
    disabled: false,
  },
  {
    key: 'local_agent',
    title: 'Local Agent',
    description: 'Agent running on localhost — test before you deploy.',
    icon: 'mdi-laptop',
    color: 'secondary',
    disabled: false,
  },
  {
    key: 'hosted_endpoint',
    title: 'Hosted Endpoint',
    description: 'Staging, prod, or internal URL behind auth.',
    icon: 'mdi-web',
    color: 'info',
    disabled: false,
  },
  {
    key: 'registered_agent',
    title: 'Registered Agent',
    description: 'Benchmark an agent registered in AI Protector (Iteration 2+).',
    icon: 'mdi-shield-check',
    color: 'success',
    disabled: true,
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
</style>
