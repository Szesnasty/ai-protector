<template>
  <v-navigation-drawer
    :model-value="modelValue"
    location="right"
    :width="400"
    temporary
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div class="attack-panel">
      <!-- Header -->
      <div class="attack-panel__header">
        <div class="d-flex align-center ga-2">
          <v-icon size="20" class="mr-1">mdi-bullseye-arrow</v-icon>
          <span style="font-size: 16px; font-weight: 600">Attack Scenarios</span>
          <v-chip size="x-small" color="primary" variant="tonal">
            {{ totalCount }}
          </v-chip>
        </div>
        <v-btn
          icon="mdi-close"
          variant="text"
          size="small"
          @click="emit('update:modelValue', false)"
        />
      </div>

      <!-- Search -->
      <div class="attack-panel__search">
        <v-text-field
          v-model="search"
          placeholder="Filter scenarios..."
          prepend-inner-icon="mdi-magnify"
          variant="outlined"
          density="compact"
          hide-details
          clearable
        />
      </div>

      <!-- Tag filter -->
      <div v-if="allTags.length" class="attack-panel__tags px-3 pb-3 pt-3">
        <v-autocomplete
          v-model="selectedTags"
          :items="allTags"
          label="Filter by attack type"
          multiple
          chips
          closable-chips
          variant="outlined"
          density="compact"
          hide-details
          clearable
        />
      </div>

      <v-divider />

      <!-- Scenario groups -->
      <div class="attack-panel__body">
        <!-- Loading state -->
        <div v-if="loading" class="pa-4">
          <v-skeleton-loader v-for="i in 4" :key="i" type="list-item-two-line" class="mb-2" />
        </div>

        <v-expansion-panels
          v-if="!loading && filteredGroups.length"
          v-model="expandedPanels"
          multiple
        >
          <v-expansion-panel
            v-for="group in filteredGroups"
            :key="group.label"
          >
            <v-expansion-panel-title class="attack-panel__group-title">
              <div class="d-flex align-center ga-2" style="min-width: 0">
                <v-icon size="20" class="flex-shrink-0">{{ group.icon }}</v-icon>
                <span class="text-caption font-weight-bold" style="word-break: break-word; white-space: normal; line-height: 1.3">{{ group.label }}</span>
                <v-chip size="x-small" variant="tonal" :color="group.color">
                  {{ group.items.length }}
                </v-chip>
              </div>
            </v-expansion-panel-title>

            <v-expansion-panel-text>
              <div class="d-flex flex-column ga-2">
                <template v-for="item in group.items" :key="item.label">
                  <v-tooltip location="start" :max-width="380" open-delay="300">
                    <template #activator="{ props: tp }">
                      <v-btn
                        v-bind="tp"
                        block
                        variant="flat"
                        class="attack-panel__scenario-btn text-left"
                        :class="`attack-panel__scenario-btn--${(item.expectedDecision || '').toLowerCase()}`"
                        @click="handleSend(item)"
                      >
                  <div class="attack-panel__scenario-content">
                    <div class="d-flex align-center justify-space-between w-100">
                      <span class="text-caption" style="word-break: break-word; white-space: normal; line-height: 1.3">{{ item.label }}</span>
                      <v-chip
                        :color="decisionColor(item.expectedDecision)"
                        size="x-small"
                        variant="outlined"
                        class="ml-2 flex-shrink-0"
                      >
                        {{ item.expectedDecision }}
                      </v-chip>
                    </div>
                    <div class="attack-panel__scenario-tags mt-1">
                      <v-chip
                        v-for="tag in item.tags"
                        :key="tag"
                        :text="tag"
                        size="x-small"
                        variant="outlined"
                        label
                      />
                    </div>
                  </div>
                      </v-btn>
                    </template>
                    <div class="attack-panel__tooltip-prompt">{{ item.prompt }}</div>
                  </v-tooltip>
                </template>
              </div>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>

        <!-- Empty state -->
        <div v-else-if="!loading" class="attack-panel__empty">
          <v-icon size="32" color="grey">mdi-magnify-close</v-icon>
          <p class="text-body-2 text-grey mt-2">No matching scenarios</p>
          <v-btn
            size="small"
            variant="tonal"
            class="mt-2"
            @click="search = ''; selectedTags = []"
          >
            Clear filters
          </v-btn>
        </div>
      </div>
    </div>
  </v-navigation-drawer>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { ScenarioGroup, ScenarioItem } from '~/types/scenarios'
import { decisionColor as _dc } from '~/utils/colors'

const props = defineProps<{
  scenarios: ScenarioGroup[]
  modelValue: boolean
  loading?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'send': [prompt: string, scenario: ScenarioItem]
}>()

const search = ref('')
const selectedTags = ref<string[]>([])

// Collect all unique tags from all scenarios
const allTags = computed(() => {
  const tags = new Set<string>()
  for (const group of props.scenarios) {
    for (const item of group.items) {
      for (const tag of item.tags) {
        tags.add(tag)
      }
    }
  }
  return [...tags].sort()
})

// Total scenario count
const totalCount = computed(() =>
  props.scenarios.reduce((sum, g) => sum + g.items.length, 0),
)

// Filter scenarios based on search + selected tags, sort groups alphabetically
const filteredGroups = computed(() => {
  const q = search.value?.toLowerCase().trim() ?? ''
  const activeTags = selectedTags.value

  return props.scenarios
    .map(group => ({
      ...group,
      items: group.items.filter((item) => {
        // Tag filter
        if (activeTags.length > 0) {
          const hasTag = activeTags.some(t => item.tags.includes(t))
          if (!hasTag) return false
        }
        // Text search
        if (q) {
          return (
            item.label.toLowerCase().includes(q)
            || item.prompt.toLowerCase().includes(q)
            || item.tags.some(t => t.toLowerCase().includes(q))
          )
        }
        return true
      }),
    }))
    .filter(group => group.items.length > 0)
    .sort((a, b) => a.label.localeCompare(b.label))
})

// Default: all panels collapsed
const expandedPanels = ref<number[]>([])

function decisionColor(decision: string) {
  return _dc(decision)
}

function handleSend(item: ScenarioItem) {
  // Emit immediately so parent can set the input text,
  // then the parent handles the 300ms delay + submit
  emit('send', item.prompt, item)
}
</script>

<style lang="scss" scoped>
.attack-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding-top: 16px;

  &__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
  }

  &__search {
    padding: 0 12px 16px;
  }

  &__tags {
    padding: 0 12px 8px;
  }

  &__body {
    flex: 1;
    overflow-y: auto;
    padding: 8px;
  }

  &__group-title {
    padding: 8px 12px !important;
    min-height: 36px !important;
  }

  &__scenario-btn {
    height: auto !important;
    min-height: 36px;
    padding: 8px 12px 8px 14px !important;
    text-transform: none;
    letter-spacing: normal;
    white-space: normal;
    word-break: break-word;
    background: rgb(var(--v-theme-surface)) !important;
    border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
    border-left: 3px solid transparent;
    border-radius: 8px !important;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06), 0 1px 2px rgba(0, 0, 0, 0.04);
    transition: all 0.2s ease;

    :deep(.v-btn__content) {
      justify-content: flex-start !important;
      width: 100%;
    }

    &:hover {
      background: rgba(var(--v-theme-on-surface), 0.04) !important;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1), 0 2px 4px rgba(0, 0, 0, 0.06);
      transform: translateY(-1px);
    }

    &:active {
      transform: translateY(0);
      box-shadow: 0 1px 2px rgba(0, 0, 0, 0.08);
    }

    &--block {
      border-left-color: rgba(var(--v-theme-error), 0.35);
    }

    &--modify {
      border-left-color: rgb(var(--v-theme-warning));
    }

    &--allow {
      border-left-color: rgb(var(--v-theme-success));
    }
  }

  &__scenario-content {
    width: 100%;
  }

  &__scenario-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }

  &__tooltip-prompt {
    font-size: 0.75rem;
    line-height: 1.4;
    max-height: 200px;
    overflow-y: auto;
    white-space: pre-wrap;
    word-break: break-word;
  }

  &__empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 32px 16px;
  }
}

:deep(.v-expansion-panel-text__wrapper) {
  padding: 8px 8px 16px !important;
}

.attack-panel :deep(.v-chip) {
  font-size: 12px !important;
}
</style>
