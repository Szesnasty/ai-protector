<template>
  <v-card flat>
    <v-card-title class="text-h6 d-flex align-center justify-space-between">
      <span>Validate Configuration</span>
      <v-btn
        size="small"
        color="primary"
        prepend-icon="mdi-play"
        :loading="isRunning"
        @click="doRun"
      >
        {{ latest ? 'Re-run Validation' : 'Run Validation' }}
      </v-btn>
    </v-card-title>
    <v-card-subtitle>Test your agent's security configuration</v-card-subtitle>

    <v-card-text>
      <div v-if="isRunning" class="text-center py-12">
        <v-progress-circular indeterminate size="48" class="mb-4" />
        <p class="text-body-2 text-medium-emphasis">Running validation tests...</p>
      </div>

      <div v-else-if="!latest" class="text-center py-12">
        <v-icon icon="mdi-clipboard-check-outline" size="64" color="primary" class="mb-4" />
        <p class="text-body-2 text-medium-emphasis">
          Click "Run Validation" to test your configuration
        </p>
      </div>

      <template v-else>
        <!-- Scorecard -->
        <v-card
          :color="latest.score >= 1.0 ? 'success' : 'error'"
          variant="tonal"
          class="mb-6 pa-4 text-center"
        >
          <div class="text-h3 font-weight-bold">
            {{ latest.passed }}/{{ latest.total }}
          </div>
          <div class="text-subtitle-1">
            <v-icon :icon="latest.score >= 1.0 ? 'mdi-check-circle' : 'mdi-alert-circle'" class="mr-1" />
            {{ latest.score >= 1.0 ? 'All tests passed' : `${latest.failed} test(s) failed` }}
          </div>
        </v-card>

        <!-- Results breakdown -->
        <v-list lines="two">
          <v-list-item
            v-for="(result, i) in latest.results"
            :key="i"
            :title="result.name"
            :subtitle="result.message"
          >
            <template #prepend>
              <v-icon
                :icon="result.passed ? 'mdi-check-circle' : 'mdi-close-circle'"
                :color="result.passed ? 'green' : 'red'"
              />
            </template>
            <template #append>
              <v-chip size="x-small" variant="tonal">
                {{ result.category }}
              </v-chip>
            </template>

            <!-- Recommendation for failed tests -->
            <template v-if="!result.passed && result.recommendation" #default>
              <div>
                <div class="text-body-2">{{ result.name }}</div>
                <div class="text-caption text-medium-emphasis">{{ result.message }}</div>
                <v-alert type="warning" variant="tonal" density="compact" class="mt-2">
                  <strong>Recommendation:</strong> {{ result.recommendation }}
                </v-alert>
              </div>
            </template>
          </v-list-item>
        </v-list>
      </template>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { watch } from 'vue'
import { useAgentValidation } from '~/composables/useAgentValidation'

const props = defineProps<{
  agentId: string
}>()

const emit = defineEmits<{
  valid: [valid: boolean]
}>()

const { latest, isRunning, run } = useAgentValidation(() => props.agentId)

watch(latest, (v) => emit('valid', !!v), { immediate: true })

const doRun = async () => {
  try {
    await run()
  }
  catch {
    // handled by vue-query
  }
}
</script>
