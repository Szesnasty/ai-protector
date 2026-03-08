<template>
  <div>
    <!-- Category group filter chips -->
    <div class="d-flex flex-wrap ga-2 mb-3">
      <v-chip
        v-for="group in CATEGORY_GROUPS"
        :key="group.value ?? 'all'"
        :variant="selectedGroup === group.value ? 'flat' : 'outlined'"
        :color="selectedGroup === group.value ? 'primary' : undefined"
        :prepend-icon="group.icon"
        size="small"
        @click="selectedGroup = group.value"
      >
        {{ group.label }}
      </v-chip>
    </div>

    <!-- Action filter + search -->
    <div class="d-flex ga-3 mb-3 align-center">
      <div class="d-flex flex-wrap ga-2">
        <v-chip
          v-for="a in ACTIONS"
          :key="a.value ?? 'all'"
          :variant="selectedAction === a.value ? 'flat' : 'outlined'"
          :color="selectedAction === a.value ? 'primary' : undefined"
          size="small"
          @click="selectedAction = a.value"
        >
          {{ a.label }}
        </v-chip>
      </div>
      <v-spacer />
      <v-text-field
        v-model="searchQuery"
        density="compact"
        variant="outlined"
        label="Search"
        prepend-inner-icon="mdi-magnify"
        hide-details
        clearable
        style="max-width: 280px"
      />
    </div>

    <!-- Data table -->
    <v-data-table
      :headers="headers"
      :items="filteredRules"
      :loading="loading"
      density="compact"
      items-per-page="25"
      hover
      class="elevation-1 rounded"
    >
      <template #item.phrase="{ item }">
        <v-tooltip :text="item.phrase" location="top" max-width="500">
          <template #activator="{ props }">
            <span v-bind="props" class="text-mono text-truncate d-inline-block" style="max-width: 300px">
              {{ item.phrase }}
            </span>
          </template>
        </v-tooltip>
      </template>

      <template #item.category="{ item }">
        <v-chip size="x-small" :prepend-icon="getGroupIcon(item.category)" variant="tonal">
          {{ item.category }}
        </v-chip>
      </template>

      <template #item.description="{ item }">
        <v-tooltip v-if="item.description" :text="item.description" location="top" max-width="400">
          <template #activator="{ props }">
            <span v-bind="props" class="text-truncate d-inline-block" style="max-width: 200px">
              {{ item.description }}
            </span>
          </template>
        </v-tooltip>
        <span v-else class="text-disabled">—</span>
      </template>

      <template #item.action="{ item }">
        <v-chip :color="actionColor(item.action)" size="x-small" variant="flat" label>
          {{ item.action }}
        </v-chip>
      </template>

      <template #item.severity="{ item }">
        <v-chip :color="severityColor(item.severity)" size="x-small" variant="tonal" label>
          {{ item.severity }}
        </v-chip>
      </template>

      <template #item.is_regex="{ item }">
        <v-icon v-if="item.is_regex" size="small" color="success">mdi-check</v-icon>
        <span v-else class="text-disabled">—</span>
      </template>

      <template #item.actions="{ item }">
        <v-btn icon="mdi-pencil" size="small" variant="text" @click="$emit('edit', item)" />
        <v-btn icon="mdi-delete" size="small" variant="text" color="error" @click="$emit('delete', item)" />
        <v-btn icon="mdi-test-tube" size="small" variant="text" color="info" @click="$emit('test', item)" />
      </template>
    </v-data-table>
  </div>
</template>

<script setup lang="ts">
import type { Rule, RuleAction } from '~/types/api'

const props = defineProps<{
  rules: Rule[]
  loading: boolean
}>()

defineEmits<{
  edit: [rule: Rule]
  delete: [rule: Rule]
  test: [rule: Rule]
}>()

const { getGroupIcon } = useRulePresets()

const selectedGroup = ref<string | null>(null)
const selectedAction = ref<string | null>(null)
const searchQuery = ref('')

const CATEGORY_GROUPS = [
  { label: 'All', value: null, icon: 'mdi-all-inclusive' },
  { label: 'Intent', value: 'intent:', icon: 'mdi-target' },
  { label: 'OWASP', value: 'owasp_', icon: 'mdi-shield-check' },
  { label: 'PII', value: 'pii_', icon: 'mdi-lock' },
  { label: 'Brand', value: 'brand_', icon: 'mdi-bullhorn' },
  { label: 'Legal', value: 'legal_', icon: 'mdi-gavel' },
  { label: 'General', value: 'general', icon: 'mdi-cog' },
]

const ACTIONS = [
  { label: 'All', value: null },
  { label: 'Block', value: 'block' },
  { label: 'Flag', value: 'flag' },
  { label: 'Score Boost', value: 'score_boost' },
] as const

const headers = [
  { title: 'Phrase', key: 'phrase', width: '28%' },
  { title: 'Category', key: 'category', width: '14%' },
  { title: 'Description', key: 'description', width: '20%' },
  { title: 'Action', key: 'action', width: '8%' },
  { title: 'Severity', key: 'severity', width: '8%' },
  { title: 'Regex', key: 'is_regex', width: '6%' },
  { title: 'Actions', key: 'actions', width: '16%', sortable: false },
]

const filteredRules = computed(() => {
  let result = props.rules

  if (selectedGroup.value) {
    const prefix = selectedGroup.value
    result = result.filter(r =>
      prefix === 'general'
        ? !r.category.includes(':') && !r.category.includes('_')
        : r.category.startsWith(prefix),
    )
  }

  if (selectedAction.value) {
    result = result.filter(r => r.action === selectedAction.value)
  }

  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    result = result.filter(r =>
      r.phrase.toLowerCase().includes(q)
      || r.description.toLowerCase().includes(q)
      || r.category.toLowerCase().includes(q),
    )
  }

  return result
})

function actionColor(action: RuleAction): string {
  const map: Record<string, string> = { block: 'error', flag: 'warning', score_boost: 'info' }
  return map[action] ?? 'default'
}

function severityColor(severity: string): string {
  const map: Record<string, string> = { critical: 'error', high: 'orange', medium: 'warning', low: 'grey' }
  return map[severity] ?? 'default'
}
</script>

<style scoped>
.text-mono {
  font-family: 'Roboto Mono', monospace;
  font-size: 0.8rem;
}
</style>
