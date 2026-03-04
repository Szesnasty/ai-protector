<template>
  <v-container fluid class="compare-page pa-0">
    <!-- Top config bar -->
    <div class="compare-page__config">
      <div class="d-flex align-center flex-wrap ga-3 px-4 py-2">
        <v-icon size="20" color="primary">mdi-compare</v-icon>
        <span class="text-subtitle-2 font-weight-bold">Compare Playground</span>

        <v-divider vertical class="mx-1" />

        <v-select
          v-model="config.policy"
          :items="policyItems"
          :loading="policiesLoading"
          :disabled="isBusy"
          label="Policy"
          variant="outlined"
          density="compact"
          hide-details
          style="max-width: 180px"
        />

        <v-select
          v-model="config.model"
          :items="modelItems"
          :loading="modelsLoading"
          :disabled="isBusy"
          label="Model"
          variant="outlined"
          density="compact"
          hide-details
          style="max-width: 240px"
        >
          <template #item="{ item, props: itemProps }">
            <v-list-item
              v-bind="itemProps"
              :disabled="item.raw.disabled"
              :subtitle="item.raw.disabled ? 'Add key in Settings' : item.raw.providerLabel"
            />
          </template>
        </v-select>

        <v-spacer />

        <v-btn
          size="small"
          variant="tonal"
          prepend-icon="mdi-delete"
          :disabled="isBusy"
          @click="clear"
        >
          Clear
        </v-btn>
      </div>
      <v-divider />

      <!-- Explainer bar -->
      <div class="compare-page__explainer px-4 py-2">
        <v-icon size="16" color="info" class="mr-1">mdi-information</v-icon>
        <span class="text-caption">
          Both panels send <strong>the same prompt</strong> to <strong>the same model ({{ config.model }})</strong>.
          The left panel routes through the AI Protector security pipeline. The right panel bypasses all protection.
          Compare the results to see what the firewall catches.
        </span>
      </div>
      <v-divider />
    </div>

    <!-- Two-column panels -->
    <div class="compare-page__panels">
      <div class="compare-page__panel">
        <compare-compare-panel
          variant="protected"
          :messages="protectedMessages"
          :is-streaming="isProtectedStreaming"
          :decision="protectedDecision"
          :timing="timings.protected"
        />
      </div>

      <v-divider vertical />

      <div class="compare-page__panel">
        <compare-compare-panel
          variant="direct"
          :messages="directMessages"
          :is-streaming="isDirectStreaming"
          :timing="timings.direct"
        />
      </div>
    </div>

    <!-- Shared input at the bottom -->
    <div class="compare-page__input">
      <v-divider />
      <div class="px-4 py-2">
        <playground-chat-input
          ref="chatInputRef"
          :disabled="isBusy"
          @send="send"
        />
      </div>
    </div>

    <!-- Attack scenarios panel -->
    <attack-scenarios-panel
      v-model="showScenarios"
      :scenarios="scenarios ?? []"
      :loading="scenariosLoading"
      @send="handleAttackSend"
    />

    <v-btn
      icon
      size="large"
      :color="showScenarios ? 'error' : 'surface-variant'"
      class="compare-page__fab"
      elevation="8"
      @click="showScenarios = !showScenarios"
    >
      <v-icon>mdi-skull-crossbones</v-icon>
      <v-tooltip activator="parent" location="left">Attack Scenarios</v-tooltip>
    </v-btn>
  </v-container>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useCompareChat } from '~/composables/useCompareChat'
import { useScenarios } from '~/composables/useScenarios'
import { usePolicies } from '~/composables/usePolicies'
import { useModels } from '~/composables/useModels'

const ATTACK_SUBMIT_DELAY_MS = 300

definePageMeta({ title: 'Compare' })

const {
  protectedMessages,
  directMessages,
  isProtectedStreaming,
  isDirectStreaming,
  protectedDecision,
  timings,
  config,
  send,
  clear,
} = useCompareChat()

const { scenarios, isLoading: scenariosLoading } = useScenarios('playground')
const { policies, isLoading: policiesLoading } = usePolicies()
const { groupedModels, isLoading: modelsLoading } = useModels()

const showScenarios = ref(true)
const chatInputRef = ref<{ setText: (s: string) => void } | null>(null)

const isBusy = computed(() => isProtectedStreaming.value || isDirectStreaming.value)

const policyItems = computed(() =>
  (policies.value ?? []).map((p) => ({
    title: p.name,
    value: p.name,
  })),
)

const PROVIDER_LABELS: Record<string, string> = {
  openai: 'OpenAI',
  anthropic: 'Anthropic',
  google: 'Google AI',
  mistral: 'Mistral',
  ollama: 'Ollama (local)',
}

const modelItems = computed(() =>
  (groupedModels.value ?? []).map((m) => ({
    title: m.name,
    value: m.id,
    disabled: !m.available,
    providerLabel: PROVIDER_LABELS[m.provider] ?? m.provider,
  })),
)

function handleAttackSend(prompt: string) {
  chatInputRef.value?.setText(prompt)
  setTimeout(() => send(prompt), ATTACK_SUBMIT_DELAY_MS)
}
</script>

<style lang="scss" scoped>
.compare-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 64px);

  &__config {
    flex-shrink: 0;
  }

  &__explainer {
    display: flex;
    align-items: flex-start;
    background: rgba(var(--v-theme-info), 0.05);
  }

  &__panels {
    flex: 1;
    display: flex;
    min-height: 0;
    overflow: hidden;
  }

  &__panel {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
  }

  &__input {
    flex-shrink: 0;
  }

  &__fab {
    position: fixed !important;
    top: 80px;
    right: 24px;
    z-index: 1000;
  }
}
</style>
