<template>
  <v-container fluid>
    <div class="d-flex align-center mb-4">
      <v-btn icon="mdi-arrow-left" variant="text" @click="navigateTo(`/agents/${route.params.id}`)" />
      <div class="ml-2">
        <h1 class="text-h5">Edit Agent</h1>
        <v-breadcrumbs
          :items="[
            { title: 'Agents', to: '/agents' },
            { title: agent?.name ?? 'Agent', to: `/agents/${route.params.id}` },
            { title: 'Edit' },
          ]"
          density="compact"
          class="pa-0"
        />
      </div>
    </div>

    <div v-if="loading" class="text-center py-12">
      <v-progress-circular indeterminate size="48" />
    </div>

    <template v-else-if="agent">
      <wizard-agent-wizard-stepper
        v-model="currentStep"
        :step-valid="true"
        :agent-id="agent.id"
      >
        <template #step-1>
          <wizard-step-describe :initial-data="agent" @valid="() => {}" />
        </template>
        <template #step-2>
          <wizard-step-tools :agent-id="agent.id" @valid="() => {}" />
        </template>
        <template #step-3>
          <wizard-step-roles :agent-id="agent.id" @valid="() => {}" />
        </template>
        <template #step-4>
          <wizard-step-security :agent-id="agent.id" @valid="() => {}" />
        </template>
        <template #step-5>
          <wizard-step-kit :agent-id="agent.id" @valid="() => {}" />
        </template>
        <template #step-6>
          <wizard-step-validate :agent-id="agent.id" @valid="() => {}" />
        </template>
        <template #step-7>
          <wizard-step-deploy :agent-id="agent.id" @valid="() => {}" />
        </template>
      </wizard-agent-wizard-stepper>
    </template>
  </v-container>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useAgents } from '~/composables/useAgents'
import type { AgentRead } from '~/types/wizard'

definePageMeta({ title: 'Edit Agent' })

const route = useRoute()
const { getAgent } = useAgents()

const loading = ref(true)
const agent = ref<AgentRead | null>(null)
const currentStep = ref(1)

onMounted(async () => {
  try {
    agent.value = await getAgent(route.params.id as string)
  }
  catch {
    navigateTo('/agents')
  }
  finally {
    loading.value = false
  }
})
</script>
