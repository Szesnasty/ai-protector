<template>
  <div class="nav-drawer-wrapper">
    <v-chip
      v-if="modeChip"
      :color="modeChip.color"
      variant="tonal"
      size="small"
      class="mx-4 mt-2 mb-1"
      :prepend-icon="modeChip.icon"
    >
      {{ modeChip.label }}
      <v-tooltip activator="parent" location="bottom" max-width="320">
        <div class="text-body-2" v-html="modeChip.tooltip" />
      </v-tooltip>
    </v-chip>

    <v-list density="compact" nav color="primary">
      <!-- Test -->
      <v-list-subheader>Test</v-list-subheader>
      <v-list-item
        v-for="item in testItems"
        :key="item.to"
        :to="item.to"
        :title="item.title"
        active-class="nav-item--active"
      >
        <template #prepend>
          <v-icon :icon="item.icon" size="20" />
        </template>
      </v-list-item>

      <v-divider class="my-2" />

      <!-- Create -->
      <v-list-subheader>Create</v-list-subheader>
      <v-list-item
        v-for="item in createItems"
        :key="item.to"
        :to="item.to"
        :title="item.title"
        active-class="nav-item--active"
        :class="{ 'nav-item--highlight': item.highlight }"
        exact
      >
        <template #prepend>
          <v-icon :icon="item.icon" size="20" />
        </template>
      </v-list-item>

      <v-divider class="my-2" />

      <!-- Validate -->
      <v-list-subheader>Validate</v-list-subheader>
      <v-list-item
        v-for="item in validateItems"
        :key="item.to"
        :to="item.to"
        :title="item.title"
        active-class="nav-item--active"
        exact
      >
        <template #prepend>
          <v-icon :icon="item.icon" size="20" />
        </template>
      </v-list-item>

      <v-divider class="my-2" />

      <!-- Observe -->
      <v-list-subheader>Observe</v-list-subheader>
      <v-list-item
        v-for="item in observeItems"
        :key="item.to"
        :to="item.to"
        :title="item.title"
        active-class="nav-item--active"
        exact
      >
        <template #prepend>
          <v-icon :icon="item.icon" size="20" />
        </template>
      </v-list-item>

      <v-divider class="my-2" />

      <!-- Configure -->
      <v-list-subheader>Configure</v-list-subheader>
      <v-list-item
        v-for="item in configureItems"
        :key="item.to"
        :to="item.to"
        :title="item.title"
        active-class="nav-item--active"
        exact
      >
        <template #prepend>
          <v-icon :icon="item.icon" size="20" />
        </template>
      </v-list-item>
    </v-list>

    <div class="wizard-cta mx-4 mt-6">
      <p class="text-caption text-medium-emphasis text-center mb-0" style="opacity: 0.7">
        Ship agents with guardrails — not prayers.
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useAppMode } from '~/composables/useAppMode'

const { appMode } = useAppMode()

interface ModeChip {
  label: string
  color: string
  icon: string
  tooltip: string
}

const MODE_CHIPS: Record<string, ModeChip> = {
  demo: {
    label: 'Demo Mode',
    color: 'amber',
    icon: 'mdi-flask-outline',
    tooltip:
      '<strong>LLM responses are simulated</strong> (mock provider).<br />' +
      'The security pipeline runs for real — NeMo Guardrails, Presidio PII ' +
      'detection, custom rules, RBAC, and all agent gates are active.<br /><br />' +
      '<strong>Want real LLM responses?</strong> Go to ' +
      '<em>Settings → API Keys</em> and paste an OpenAI or Anthropic key.',
  },
  real: {
    label: 'Production',
    color: 'green',
    icon: 'mdi-shield-check-outline',
    tooltip:
      '<strong>Production mode</strong> — real LLM inference via Ollama ' +
      '(local) or external providers (Gemini, Mistral, OpenAI).<br /><br />' +
      '<strong>Active services:</strong><br />' +
      '• <strong>Ollama</strong> — local LLM (llama3.2:3b)<br />' +
      '• <strong>Security pipeline</strong> — LLM Guard, NeMo Guardrails, Presidio PII, output filter<br />' +
      '• <strong>Langfuse</strong> — request tracing &amp; observability<br />' +
      '• <strong>PostgreSQL + Redis</strong> — persistence &amp; caching<br /><br />' +
      'Add external provider keys in <em>Settings → API Keys</em>.',
  },
}

const modeChip = computed<ModeChip | null>(() => {
  const mode = appMode.value?.mode
  if (!mode) return null
  return MODE_CHIPS[mode] ?? { label: mode, color: 'grey', icon: 'mdi-help-circle-outline', tooltip: `Running in <strong>${mode}</strong> mode.` }
})

interface NavItem {
  title: string
  icon: string
  to: string
  highlight?: boolean
}

const testItems: NavItem[] = [
  { title: 'Red Team', icon: 'mdi-shield-search', to: '/red-team' },
]

const createItems: NavItem[] = [
  { title: 'Agent Wizard', icon: 'mdi-magic-staff', to: '/agents/new', highlight: true },
  { title: 'Agents', icon: 'mdi-robot-outline', to: '/agents' },
]

const validateItems: NavItem[] = [
  { title: 'Playground', icon: 'mdi-chat-processing', to: '/playground' },
  { title: 'Compare', icon: 'mdi-compare', to: '/compare' },
  { title: 'Python Agent', icon: 'mdi-language-python', to: '/test-agents/python' },
  { title: 'LangGraph Agent', icon: 'mdi-graph-outline', to: '/test-agents/graph' },
  { title: 'Agent Demo', icon: 'mdi-robot', to: '/agent' },
]

const observeItems: NavItem[] = [
  { title: 'Agent Traces', icon: 'mdi-chart-timeline-variant', to: '/agent-traces' },
  { title: 'Request Log', icon: 'mdi-format-list-bulleted', to: '/requests' },
  { title: 'Analytics', icon: 'mdi-chart-bar', to: '/analytics' },
]

const configureItems: NavItem[] = [
  { title: 'Policies', icon: 'mdi-shield-lock', to: '/policies' },
  { title: 'Security Rules', icon: 'mdi-shield-lock-outline', to: '/rules' },
  { title: 'Settings', icon: 'mdi-cog', to: '/settings' },
]
</script>

<style lang="scss" scoped>
:deep(.v-list-item-title) {
  font-size: 16px !important;
}

:deep(.nav-item--active) {
  border-radius: 12px !important;
  background: rgb(var(--v-theme-secondary)) !important;
  color: rgb(var(--v-theme-on-secondary)) !important;

  .v-list-item__overlay {
    opacity: 0 !important;
  }

  .v-icon {
    color: rgb(var(--v-theme-on-primary)) !important;
  }
}

.nav-item--highlight {
  background: rgba(var(--v-theme-primary), 0.08);
  border-radius: 12px;
  border-left: 3px solid rgb(var(--v-theme-primary));
  margin-bottom: 2px;

  :deep(.v-icon) {
    color: rgb(var(--v-theme-primary));
  }

  &.nav-item--active {
    border-left-color: transparent;
  }
}
</style>
