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
        <v-alert
          v-if="showReauthBanner"
          type="info"
          variant="tonal"
          density="compact"
          class="mb-4"
        >
          <strong>Re-enter your auth headers to run again.</strong>
          Your endpoint URL is pre-filled. Headers are deleted after each run for security.
        </v-alert>
        <RedTeamTargetForm
          :target-type="targetType"
          :initial-endpoint-url="initialEndpointUrl"
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
  const t = (route.query.type as string) || (route.query.target as string)
  if (t === 'hosted_endpoint') return 'hosted_endpoint' as const
  return 'local_agent' as const
})

// Pre-fill URL when coming back from results page re-run
const initialEndpointUrl = computed(() => (route.query.url as string) || '')
// Show re-auth banner when token expired and user needs to re-enter headers
const showReauthBanner = computed(() => route.query.reauth === 'true')
// Carry pack/policy/protected intent through to configure
const rerunPack = computed(() => (route.query.pack as string) || '')
const rerunPolicy = computed(() => (route.query.policy as string) || '')
const rerunProtected = computed(() => route.query.protected === 'true')

function onContinue(config: TargetFormConfig) {
  // Store headers in memory only (never sessionStorage/localStorage)
  const { stash } = useEphemeralHeaders()
  const hdrs = config.custom_headers
  if (hdrs && Object.keys(hdrs).length > 0) {
    stash(hdrs as Record<string, string>)
  }

  // Persist scan config (template + response paths) in sessionStorage
  const { save } = useScanConfig()
  save({
    requestTemplate: config.request_template || '',
    responseTextPaths: config.response_text_paths || [],
  })

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
      // Carry re-run intent
      ...(rerunPack.value ? { pack: rerunPack.value } : {}),
      ...(rerunPolicy.value ? { policy: rerunPolicy.value } : {}),
      ...(rerunProtected.value ? { protected: 'true' } : {}),
    },
  })
}
</script>
