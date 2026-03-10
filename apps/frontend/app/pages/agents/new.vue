<template>
  <v-container fluid class="wizard-page">
    <div class="d-flex align-center mb-4">
      <v-btn icon="mdi-arrow-left" variant="text" @click="navigateTo('/agents')" />
      <div class="ml-2">
        <h1 class="text-h5">{{ isEditing ? 'Edit Agent' : 'Register New Agent' }}</h1>
        <v-breadcrumbs :items="breadcrumbs" density="compact" class="pa-0" />
      </div>
    </div>

    <wizard-agent-wizard-stepper
      v-model="currentStep"
      :step-valid="stepValid"
      :agent-id="agentId"
      @complete="onComplete"
    >
      <template #step-1>
        <wizard-step-describe
          ref="describeRef"
          :initial-data="editAgent ?? undefined"
          @valid="v => stepValidity[1] = v"
        />
      </template>

      <template #step-2>
        <wizard-step-tools v-if="agentId" :agent-id="agentId" @valid="v => stepValidity[2] = v" />
        <v-alert v-else type="info" variant="tonal">
          Complete Step 1 first to register the agent.
        </v-alert>
      </template>

      <template #step-3>
        <wizard-step-roles v-if="agentId" :agent-id="agentId" @valid="v => stepValidity[3] = v" />
        <v-alert v-else type="info" variant="tonal">
          Complete Step 1 first.
        </v-alert>
      </template>

      <template #step-4>
        <wizard-step-security v-if="agentId" :agent-id="agentId" @valid="v => stepValidity[4] = v" />
      </template>

      <template #step-5>
        <wizard-step-kit v-if="agentId" :agent-id="agentId" @valid="v => stepValidity[5] = v" />
      </template>

      <template #step-6>
        <wizard-step-validate v-if="agentId" :agent-id="agentId" @valid="v => stepValidity[6] = v" />
      </template>

      <template #step-7>
        <wizard-step-deploy v-if="agentId" :agent-id="agentId" @valid="v => stepValidity[7] = v" />
      </template>
    </wizard-agent-wizard-stepper>
  </v-container>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useAgents } from '~/composables/useAgents'
import type { AgentRead } from '~/types/wizard'

definePageMeta({ title: 'New Agent' })

const route = useRoute()
const isEditing = computed(() => !!route.params.id)

const { createAgent, getAgent, updateAgent } = useAgents()

const currentStep = ref(1)
const agentId = ref<string | null>(null)
const editAgent = ref<AgentRead | null>(null)
const describeRef = ref<{ getData: () => Record<string, unknown>; setError: (msg: string) => void } | null>(null)

const stepValidity = reactive<Record<number, boolean>>({
  1: false,
  2: false,
  3: false,
  4: false,
  5: false,
  6: false,
  7: false,
})

const stepValid = computed(() => stepValidity[currentStep.value] ?? false)

const breadcrumbs = computed(() => [
  { title: 'Agents', to: '/agents' },
  { title: isEditing.value ? 'Edit' : 'New Agent' },
])

// Handle step transitions — create agent on step 1 → 2
watch(currentStep, async (newStep, oldStep) => {
  if (oldStep === 1 && newStep === 2 && !agentId.value && describeRef.value) {
    try {
      const data = describeRef.value.getData()
      if (isEditing.value && agentId.value) {
        await updateAgent({ id: agentId.value, body: data })
      }
      else {
        const created = await createAgent(data as unknown as Parameters<typeof createAgent>[0])
        agentId.value = created.id
      }
    }
    catch (e: unknown) {
      currentStep.value = 1
      const msg = e instanceof Error ? e.message : 'Failed to create agent'
      if (describeRef.value) describeRef.value.setError(msg)
    }
  }
})

// Load agent data if editing
onMounted(async () => {
  if (route.params.id) {
    try {
      const agent = await getAgent(route.params.id as string)
      editAgent.value = agent
      agentId.value = agent.id
    }
    catch {
      navigateTo('/agents')
    }
  }
  else {
    // Fresh wizard entry — always start clean
    localStorage.removeItem('ai-protector-wizard-state')
    currentStep.value = 1
    agentId.value = null
    editAgent.value = null
    Object.keys(stepValidity).forEach(k => { stepValidity[Number(k)] = false })
  }
})

const onComplete = () => {
  // Clear wizard state and navigate to agent detail
  localStorage.removeItem('ai-protector-wizard-state')
  if (agentId.value) {
    navigateTo(`/agents/${agentId.value}`)
  }
  else {
    navigateTo('/agents')
  }
}
</script>
