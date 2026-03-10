<template>
  <v-card flat>
    <v-card-title class="text-h6">Configure Security</v-card-title>
    <v-card-subtitle>Select a policy pack and configure limits</v-card-subtitle>

    <v-card-text>
      <!-- Policy pack cards -->
      <p class="text-subtitle-2 mb-3">Policy Pack</p>
      <v-row class="mb-6">
        <v-col
          v-for="pack in policyPacks"
          :key="pack.name"
          cols="12"
          sm="6"
          md="4"
        >
          <v-card
            :variant="selectedPack === pack.name ? 'tonal' : 'outlined'"
            :color="selectedPack === pack.name ? 'primary' : undefined"
            class="pack-card"
            @click="selectPack(pack.name)"
          >
            <v-card-title class="text-subtitle-1">
              <v-icon :icon="packIcon(pack.name)" class="mr-2" />
              {{ pack.name }}
            </v-card-title>
            <v-card-subtitle>{{ pack.description }}</v-card-subtitle>
            <v-card-text v-if="pack.risk_levels?.length">
              <v-chip
                v-for="rl in pack.risk_levels"
                :key="rl"
                size="x-small"
                variant="tonal"
                class="mr-1"
              >
                {{ rl }}
              </v-chip>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <!-- Generated config preview -->
      <template v-if="config">
        <v-divider class="mb-4" />
        <p class="text-subtitle-2 mb-3">Generated Configuration Preview</p>

        <v-tabs v-model="previewTab" density="compact" class="mb-2">
          <v-tab value="rbac">RBAC</v-tab>
          <v-tab value="limits">Limits</v-tab>
          <v-tab value="policy">Policy</v-tab>
        </v-tabs>

        <v-card variant="outlined" class="config-preview pa-3">
          <pre class="text-caption">{{ previewContent }}</pre>
        </v-card>
      </template>

      <v-alert v-if="isGenerating" type="info" variant="tonal" class="mt-4">
        <v-progress-circular indeterminate size="16" class="mr-2" />
        Generating configuration...
      </v-alert>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useAgents } from '~/composables/useAgents'
import { useAgentConfig } from '~/composables/useAgentConfig'
import type { GeneratedConfig } from '~/types/wizard'

const props = defineProps<{
  agentId: string
}>()

const emit = defineEmits<{
  valid: [valid: boolean]
}>()

const { getAgent } = useAgents()
const { config, policyPacks, generate, isGenerating } = useAgentConfig(() => props.agentId)
const { updateAgent } = useAgents()

const selectedPack = ref<string>('standard')
const previewTab = ref('rbac')

const previewContent = computed(() => {
  if (!config.value) return ''
  const c = config.value as GeneratedConfig
  const map: Record<string, string> = {
    rbac: c.rbac_yaml ?? '',
    limits: c.limits_yaml ?? '',
    policy: c.policy_yaml ?? '',
  }
  return map[previewTab.value] ?? ''
})

const packIcon = (name: string): string => {
  const icons: Record<string, string> = {
    strict: 'mdi-shield-lock',
    standard: 'mdi-shield-check',
    permissive: 'mdi-shield-outline',
    minimal: 'mdi-shield-off-outline',
    custom: 'mdi-tune',
  }
  return icons[name] ?? 'mdi-shield'
}

const selectPack = async (name: string) => {
  selectedPack.value = name
  try {
    await updateAgent({ id: props.agentId, body: { policy_pack: name } })
    await generate()
  }
  catch {
    // handled by vue-query
  }
}

// Load initial pack from agent
watch(
  () => props.agentId,
  async (id) => {
    if (id) {
      try {
        const agent = await getAgent(id)
        if (agent.policy_pack) selectedPack.value = agent.policy_pack
      }
      catch { /* */ }
    }
  },
  { immediate: true },
)

watch(config, (c) => emit('valid', !!c), { immediate: true })
</script>

<style lang="scss" scoped>
.pack-card {
  cursor: pointer;
  transition: all 0.2s;
  height: 100%;

  &:hover {
    transform: translateY(-2px);
  }
}

.config-preview {
  max-height: 400px;
  overflow: auto;
  background: rgba(0, 0, 0, 0.2);

  pre {
    white-space: pre-wrap;
    word-break: break-word;
    font-family: 'Fira Code', monospace;
  }
}
</style>
