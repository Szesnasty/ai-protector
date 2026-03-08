<template>
  <v-card
    variant="flat"
    class="policy-card"
    :class="`policy-card--${policy.name}`"
    hover
    @click="$emit('edit', policy)"
  >
    <v-card-text>
      <div class="d-flex align-center mb-3">
        <v-avatar :color="cardColor" variant="tonal" size="40" class="mr-3">
          <v-icon :icon="policyIcon" />
        </v-avatar>
        <div class="flex-grow-1">
          <div class="d-flex align-center ga-2">
            <span class="text-subtitle-1 font-weight-bold">{{ policy.name }}</span>
            <v-chip
              v-if="policy.name === 'balanced'"
              size="x-small"
              variant="tonal"
              color="primary"
            >
              Default
            </v-chip>
          </div>
          <div class="d-flex align-center ga-1 mt-1">
            <v-chip
              :color="policy.is_active ? 'success' : 'grey'"
              size="x-small"
              variant="tonal"
            >
              {{ policy.is_active ? 'Active' : 'Inactive' }}
            </v-chip>
            <v-chip size="x-small" variant="outlined">
              v{{ policy.version }}
            </v-chip>
          </div>
        </div>
      </div>

      <p class="text-body-2 text-medium-emphasis mb-3" style="min-height: 40px;">
        {{ policy.description || 'No description' }}
      </p>

      <div class="d-flex ga-4 text-caption text-medium-emphasis">
        <span class="d-flex align-center ga-1">
          <v-icon size="14" icon="mdi-shield-search" />
          {{ scannerCount }} scanners
        </span>
        <span class="d-flex align-center ga-1">
          <v-icon size="14" icon="mdi-speedometer" />
          risk {{ maxRisk }}
        </span>
      </div>
    </v-card-text>

    <v-card-actions class="pt-0 px-4 pb-3">
      <v-btn
        size="small"
        variant="text"
        prepend-icon="mdi-eye"
        class="text-medium-emphasis"
      >
        View
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup lang="ts">
import type { Policy } from '~/types/api'
import { policyColor as _policyColor } from '~/utils/colors'

const props = defineProps<{ policy: Policy }>()
defineEmits<{
  edit: [policy: Policy]
}>()

const ICONS: Record<string, string> = {
  fast: 'mdi-speedometer',
  balanced: 'mdi-scale-balance',
  strict: 'mdi-shield-alert',
  paranoid: 'mdi-shield-lock',
}

const cardColor = computed(() => _policyColor(props.policy.name))
const policyIcon = computed(() => ICONS[props.policy.name] ?? 'mdi-shield')

const config = computed(() => props.policy.config as { nodes?: string[]; thresholds?: { max_risk?: number } } | undefined)
const scannerCount = computed(() => config.value?.nodes?.length ?? 0)
const maxRisk = computed(() => config.value?.thresholds?.max_risk?.toFixed(2) ?? '—')
</script>

<style lang="scss" scoped>
.policy-card {
  border-radius: 12px !important;
  background: rgb(var(--v-theme-surface)) !important;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25), 0 0 0 1px rgba(255, 255, 255, 0.06) !important;
  border-left: 3px solid transparent;
  transition: all 0.2s ease;
  cursor: pointer;

  &:hover {
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3), 0 0 0 1px rgba(255, 255, 255, 0.1) !important;
    transform: translateY(-2px);
  }

  &--fast { border-left-color: rgb(var(--v-theme-success)); }
  &--balanced { border-left-color: rgb(var(--v-theme-primary)); }
  &--strict { border-left-color: rgb(var(--v-theme-warning)); }
  &--paranoid { border-left-color: rgb(var(--v-theme-error)); }
}
</style>
