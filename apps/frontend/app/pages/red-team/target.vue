<template>
  <v-container fluid class="target-page">
    <v-row justify="center">
      <v-col cols="12" md="8" lg="6">
        <div class="d-flex align-center mb-4">
          <v-btn
            icon="mdi-arrow-left"
            variant="text"
            size="small"
            class="mr-2"
            :to="'/red-team'"
          />
          <h1 class="text-h5">Test Your Endpoint</h1>
        </div>
        <RedTeamTargetForm
          :target-type="targetType"
          @continue="onContinue"
        />
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup lang="ts">
import type { TargetFormConfig } from '~/components/RedTeamTargetForm.vue'

definePageMeta({ layout: 'default' })

const route = useRoute()
const router = useRouter()

const targetType = computed(() => {
  const t = route.query.type as string
  if (t === 'hosted_endpoint') return 'hosted_endpoint' as const
  return 'local_agent' as const
})

function onContinue(config: TargetFormConfig) {
  // Pass target config to configure page via query/state
  router.push({
    path: '/red-team/configure',
    query: {
      target: targetType.value,
      endpoint_url: config.endpoint_url as string,
      target_name: (config.target_name as string) || undefined,
      agent_type: config.agent_type as string,
      timeout_s: String(config.timeout_s),
      safe_mode: String(config.safe_mode),
      environment: (config.environment as string) || undefined,
      // Auth handled separately — not in query params
    },
  })
}
</script>
