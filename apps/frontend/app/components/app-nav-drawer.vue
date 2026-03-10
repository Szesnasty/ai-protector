<template>
  <div>
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
      <v-list-item
        v-for="item in navItems"
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
      <v-list-subheader>Manage</v-list-subheader>
      <v-list-item
        v-for="item in manageItems"
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
}

const navItems: NavItem[] = [
  { title: 'Agents', icon: 'mdi-robot-outline', to: '/agents' },
  { title: 'Playground', icon: 'mdi-chat-processing', to: '/playground' },
  { title: 'Compare', icon: 'mdi-compare', to: '/compare' },
  { title: 'Agent Demo', icon: 'mdi-robot', to: '/agent' },
  { title: 'Agent Traces', icon: 'mdi-chart-timeline-variant', to: '/agent-traces' },
  { title: 'Security Rules', icon: 'mdi-shield-lock-outline', to: '/rules' },
]

const manageItems: NavItem[] = [
  { title: 'Policies', icon: 'mdi-shield-lock', to: '/policies' },
  { title: 'Request Log', icon: 'mdi-format-list-bulleted', to: '/requests' },
  { title: 'Analytics', icon: 'mdi-chart-bar', to: '/analytics' },
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
</style>
