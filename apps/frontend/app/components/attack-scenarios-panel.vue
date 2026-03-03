<template>
  <v-navigation-drawer
    :model-value="modelValue"
    location="right"
    :width="300"
    :temporary="isMobile"
    :permanent="!isMobile && modelValue"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div class="attack-panel">
      <!-- Header -->
      <div class="attack-panel__header">
        <div class="d-flex align-center ga-2">
          <span class="text-h6">🎯 Attack Scenarios</span>
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
      <div v-if="allTags.length" class="attack-panel__tags">
        <v-chip-group
          v-model="selectedTags"
          multiple
          column
        >
          <v-chip
            v-for="tag in allTags"
            :key="tag"
            :text="tag"
            size="x-small"
            variant="outlined"
            filter
          />
        </v-chip-group>
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
            <v-expansion-panel-title>
              <div class="d-flex align-center ga-2">
                <span>{{ group.icon }}</span>
                <span class="text-body-2 font-weight-bold">{{ group.label }}</span>
                <v-chip size="x-small" variant="tonal" :color="group.color">
                  {{ group.items.length }}
                </v-chip>
              </div>
            </v-expansion-panel-title>

            <v-expansion-panel-text>
              <div class="d-flex flex-column ga-2">
                <v-btn
                  v-for="item in group.items"
                  :key="item.label"
                  block
                  variant="tonal"
                  :color="group.color"
                  class="attack-panel__scenario-btn text-left"
                  @click="handleSend(item.prompt)"
                >
                  <div class="attack-panel__scenario-content">
                    <div class="d-flex align-center justify-space-between w-100">
                      <span class="text-body-2">{{ item.label }}</span>
                      <v-chip
                        :color="decisionColor(item.expectedDecision)"
                        size="x-small"
                        variant="flat"
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
import { useDisplay } from 'vuetify'
import type { ScenarioGroup } from '~/types/scenarios'

const ATTACK_SUBMIT_DELAY_MS = 300

const props = defineProps<{
  scenarios: ScenarioGroup[]
  modelValue: boolean
  loading?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'send': [prompt: string]
}>()

const { mobile: isMobile } = useDisplay()

const search = ref('')
const selectedTags = ref<number[]>([])

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

// Get the actual selected tag strings from indices
const selectedTagStrings = computed(() =>
  selectedTags.value.map(i => allTags.value[i]),
)

// Total scenario count
const totalCount = computed(() =>
  props.scenarios.reduce((sum, g) => sum + g.items.length, 0),
)

// Filter scenarios based on search + selected tags
const filteredGroups = computed(() => {
  const q = search.value?.toLowerCase().trim() ?? ''
  const activeTags = selectedTagStrings.value

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
})

// Default: all panels collapsed
const expandedPanels = ref<number[]>([])

function decisionColor(decision: string) {
  switch (decision) {
    case 'BLOCK': return 'error'
    case 'MODIFY': return 'warning'
    case 'ALLOW': return 'success'
    default: return 'grey'
  }
}

function handleSend(prompt: string) {
  // Emit immediately so parent can set the input text,
  // then the parent handles the 300ms delay + submit
  emit('send', prompt)
}
</script>

<style lang="scss" scoped>
.attack-panel {
  display: flex;
  flex-direction: column;
  height: 100%;

  &__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
  }

  &__search {
    padding: 0 12px 8px;
  }

  &__tags {
    padding: 0 12px 8px;
    max-height: 120px;
    overflow-y: auto;
  }

  &__body {
    flex: 1;
    overflow-y: auto;
    padding: 8px;
  }

  &__scenario-btn {
    height: auto !important;
    min-height: 40px;
    padding: 8px 12px !important;
    text-transform: none;
    letter-spacing: normal;
    white-space: normal;
  }

  &__scenario-content {
    width: 100%;
  }

  &__scenario-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }

  &__empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 32px 16px;
  }
}
</style>
