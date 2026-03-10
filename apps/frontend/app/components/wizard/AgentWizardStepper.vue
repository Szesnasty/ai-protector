<template>
  <v-stepper
    v-model="currentStep"
    :items="stepItems"
    alt-labels
    flat
    class="wizard-stepper"
  >
    <template #item.1>
      <slot name="step-1" />
    </template>
    <template #item.2>
      <slot name="step-2" />
    </template>
    <template #item.3>
      <slot name="step-3" />
    </template>
    <template #item.4>
      <slot name="step-4" />
    </template>
    <template #item.5>
      <slot name="step-5" />
    </template>
    <template #item.6>
      <slot name="step-6" />
    </template>
    <template #item.7>
      <slot name="step-7" />
    </template>

    <template #actions>
      <div class="d-flex justify-space-between pa-4">
        <v-btn
          v-if="currentStep > 1"
          variant="text"
          prepend-icon="mdi-arrow-left"
          @click="prev"
        >
          Back
        </v-btn>
        <v-spacer v-else />

        <v-btn
          v-if="currentStep < 7"
          color="primary"
          append-icon="mdi-arrow-right"
          :disabled="!stepValid"
          @click="next"
        >
          Next
        </v-btn>
        <v-btn
          v-else
          color="success"
          append-icon="mdi-check"
          :disabled="!stepValid"
          @click="$emit('complete')"
        >
          Finish
        </v-btn>
      </div>
    </template>
  </v-stepper>
</template>

<script setup lang="ts">
import { onMounted, watch } from 'vue'

const STORAGE_KEY = 'ai-protector-wizard-state'

const props = defineProps<{
  stepValid?: boolean
  agentId?: string | null
}>()

defineEmits<{
  complete: []
}>()

const currentStep = defineModel<number>('modelValue', { default: 1 })

const stepItems = [
  { title: 'Describe Agent', value: 1 },
  { title: 'Register Tools', value: 2 },
  { title: 'Define Roles', value: 3 },
  { title: 'Configure Security', value: 4 },
  { title: 'Generate Kit', value: 5 },
  { title: 'Validate', value: 6 },
  { title: 'Deploy', value: 7 },
]

const next = () => {
  if (currentStep.value < 7) currentStep.value++
}

const prev = () => {
  if (currentStep.value > 1) currentStep.value--
}

// Persist state to localStorage
watch(
  () => [currentStep.value, props.agentId],
  () => {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ step: currentStep.value, agentId: props.agentId }),
      )
    }
    catch {
      // localStorage unavailable
    }
  },
)

// Restore from localStorage
onMounted(() => {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) {
      const state = JSON.parse(saved)
      if (state.step && typeof state.step === 'number') {
        currentStep.value = state.step
      }
    }
  }
  catch {
    // ignore
  }
})

const clearState = () => {
  localStorage.removeItem(STORAGE_KEY)
  currentStep.value = 1
}

defineExpose({ next, prev, clearState })
</script>

<style lang="scss" scoped>
.wizard-stepper {
  background: transparent;
}
</style>
