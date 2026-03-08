<template>
  <v-dialog v-model="dialog" max-width="600" persistent>
    <v-card>
      <v-card-title>Test Rules</v-card-title>
      <v-card-text>
        <v-alert v-if="focusRule" type="info" variant="tonal" density="compact" class="mb-3">
          Testing rule: <strong>{{ focusRule.phrase }}</strong>
          <span class="text-caption ml-2">({{ focusRule.category }})</span>
        </v-alert>

        <v-textarea
          v-model="testText"
          label="Enter sample text to test against rules"
          variant="outlined"
          rows="3"
          auto-grow
          class="mb-3"
        />

        <v-btn class="btn-action mb-4" :loading="testing" :disabled="!testText" block @click="runTest">
          <v-icon start>mdi-test-tube</v-icon>
          Test
        </v-btn>

        <!-- Results -->
        <div v-if="results !== null">
          <v-alert v-if="results.length === 0" type="success" variant="tonal" density="compact">
            No rules matched.
          </v-alert>

          <v-list v-else density="compact">
            <v-list-subheader>{{ results.length }} rule(s) matched</v-list-subheader>
            <v-list-item v-for="(r, i) in results" :key="i">
              <template #prepend>
                <v-icon :color="r.matched ? 'error' : 'grey'" size="small">
                  {{ r.matched ? 'mdi-alert-circle' : 'mdi-check-circle' }}
                </v-icon>
              </template>
              <v-list-item-title class="text-mono text-body-2">
                {{ r.phrase }}
              </v-list-item-title>
              <v-list-item-subtitle>
                <v-chip size="x-small" variant="tonal" class="mr-1">{{ r.category }}</v-chip>
                <v-chip size="x-small" :color="actionColor(r.action)" variant="flat" class="mr-1">{{ r.action }}</v-chip>
                <v-chip size="x-small" variant="tonal">{{ r.severity }}</v-chip>
                <span v-if="r.match_details" class="ml-2 text-caption text-success">
                  matched: "{{ r.match_details }}"
                </span>
              </v-list-item-subtitle>
            </v-list-item>
          </v-list>
        </div>
      </v-card-text>

      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="close">Close</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import type { Rule, RuleTestResult } from '~/types/api'
import { actionColor as _actionColor } from '~/utils/colors'

const props = defineProps<{
  modelValue: boolean
  focusRule?: Rule | null
  testing?: boolean
  results: RuleTestResult[] | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'test': [text: string]
}>()

const dialog = computed({
  get: () => props.modelValue,
  set: v => emit('update:modelValue', v),
})

const testText = ref('')

function runTest() {
  emit('test', testText.value)
}

function close() {
  testText.value = ''
  dialog.value = false
}

function actionColor(action: string): string {
  return _actionColor(action)
}
</script>

<style scoped>
.text-mono {
  font-family: 'Roboto Mono', monospace;
  font-size: 0.8rem;
}
</style>
