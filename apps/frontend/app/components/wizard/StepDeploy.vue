<template>
  <v-card flat>
    <v-card-title class="text-h6">Deploy Agent</v-card-title>
    <v-card-subtitle>Choose a rollout mode and activate your agent</v-card-subtitle>

    <v-card-text>
      <template v-if="!activated">
        <!-- Mode cards -->
        <v-row class="mb-6">
          <v-col v-for="mode in modes" :key="mode.value" cols="12" md="4">
            <v-card
              :variant="selectedMode === mode.value ? 'tonal' : 'outlined'"
              :color="selectedMode === mode.value ? mode.color : undefined"
              class="mode-card"
              @click="selectedMode = mode.value"
            >
              <v-card-title class="text-subtitle-1">
                <v-icon :icon="mode.icon" class="mr-2" />
                {{ mode.title }}
              </v-card-title>
              <v-card-text class="text-body-2">
                {{ mode.description }}
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>

        <div class="text-center">
          <v-btn
            color="success"
            size="large"
            prepend-icon="mdi-rocket-launch"
            :loading="isPromoting"
            @click="doActivate"
          >
            Activate in {{ selectedMode }} mode
          </v-btn>
        </div>
      </template>

      <!-- Success state -->
      <template v-else>
        <div class="text-center py-8">
          <v-icon icon="mdi-check-circle" size="80" color="success" class="mb-4" />
          <h2 class="text-h5 mb-2">Agent Activated!</h2>
          <p class="text-body-1 text-medium-emphasis mb-6">
            Your agent is now running in <strong>{{ selectedMode }}</strong> mode.
          </p>

          <v-alert type="info" variant="tonal" class="mb-6 text-left" max-width="500" style="margin: 0 auto">
            <strong>Next steps:</strong>
            <ul class="mt-2">
              <li>Monitor traces on the agent detail page</li>
              <li>Promote to <strong>warn</strong> mode when ready</li>
              <li>Promote to <strong>enforce</strong> mode after full validation</li>
            </ul>
          </v-alert>

          <v-btn
            color="primary"
            prepend-icon="mdi-arrow-right"
            @click="navigateTo(`/agents/${agentId}`)"
          >
            Go to Agent Detail
          </v-btn>
        </div>
      </template>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useAgentRollout } from '~/composables/useAgentRollout'
import type { RolloutMode } from '~/types/wizard'

const props = defineProps<{
  agentId: string
}>()

const emit = defineEmits<{
  valid: [valid: boolean]
}>()

const { promote, isPromoting } = useAgentRollout(() => props.agentId)

const selectedMode = ref<RolloutMode>('observe')
const activated = ref(false)

const modes = [
  {
    value: 'observe' as RolloutMode,
    title: 'Observe',
    icon: 'mdi-eye-outline',
    color: 'blue',
    description: 'Monitor only — log decisions without enforcing. Safe to start with.',
  },
  {
    value: 'warn' as RolloutMode,
    title: 'Warn',
    icon: 'mdi-alert-outline',
    color: 'amber',
    description: 'Log and warn on violations but allow requests through.',
  },
  {
    value: 'enforce' as RolloutMode,
    title: 'Enforce',
    icon: 'mdi-shield-check',
    color: 'green',
    description: 'Full enforcement — block violations. Requires prior validation.',
  },
]

const doActivate = async () => {
  try {
    await promote(selectedMode.value)
    activated.value = true
  }
  catch {
    // handled by vue-query
  }
}

watch(activated, (v) => emit('valid', v), { immediate: true })
</script>

<style lang="scss" scoped>
.mode-card {
  cursor: pointer;
  transition: all 0.2s;
  height: 100%;

  &:hover {
    transform: translateY(-2px);
  }
}
</style>
