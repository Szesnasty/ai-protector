<template>
  <v-card
    variant="outlined"
    :color="cardColor"
    class="policy-card"
    hover
  >
    <v-card-text>
      <div class="d-flex align-center mb-3">
        <v-avatar :color="cardColor" variant="tonal" size="40" class="mr-3">
          <v-icon :icon="policyIcon" />
        </v-avatar>
        <div class="flex-grow-1">
          <div class="text-subtitle-1 font-weight-bold">{{ policy.name }}</div>
          <v-chip
            :color="policy.is_active ? 'success' : 'grey'"
            size="x-small"
            variant="tonal"
            class="mr-1"
          >
            {{ policy.is_active ? 'Active' : 'Inactive' }}
          </v-chip>
          <v-chip size="x-small" variant="outlined">
            v{{ policy.version }}
          </v-chip>
        </div>
      </div>

      <p class="text-body-2 text-medium-emphasis mb-3" style="min-height: 40px;">
        {{ policy.description || 'No description' }}
      </p>

      <div class="d-flex ga-3 text-caption text-medium-emphasis">
        <span>
          <v-icon size="14" icon="mdi-shield-search" class="mr-1" />
          {{ scannerCount }} scanners
        </span>
        <span>
          <v-icon size="14" icon="mdi-speedometer" class="mr-1" />
          risk {{ maxRisk }}
        </span>
      </div>
    </v-card-text>

    <v-card-actions>
      <v-btn size="small" variant="text" prepend-icon="mdi-pencil" @click="$emit('edit', policy)">
        Edit
      </v-btn>
      <v-spacer />
      <v-btn
        v-if="!isBuiltin"
        size="small"
        variant="text"
        color="error"
        prepend-icon="mdi-delete"
        @click="$emit('delete', policy)"
      >
        Delete
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup lang="ts">
import type { Policy } from '~/types/api'

const props = defineProps<{ policy: Policy }>()
defineEmits<{
  edit: [policy: Policy]
  delete: [policy: Policy]
}>()

const BUILTIN = new Set(['fast', 'balanced', 'strict', 'paranoid'])
const isBuiltin = computed(() => BUILTIN.has(props.policy.name))

const COLORS: Record<string, string> = {
  fast: 'success',
  balanced: 'warning',
  strict: 'orange',
  paranoid: 'error',
}
const ICONS: Record<string, string> = {
  fast: 'mdi-speedometer',
  balanced: 'mdi-scale-balance',
  strict: 'mdi-shield-alert',
  paranoid: 'mdi-shield-lock',
}

const cardColor = computed(() => COLORS[props.policy.name] ?? 'primary')
const policyIcon = computed(() => ICONS[props.policy.name] ?? 'mdi-shield')

const config = computed(() => props.policy.config as { nodes?: string[]; thresholds?: { max_risk?: number } } | undefined)
const scannerCount = computed(() => config.value?.nodes?.length ?? 0)
const maxRisk = computed(() => config.value?.thresholds?.max_risk?.toFixed(2) ?? '—')
</script>
