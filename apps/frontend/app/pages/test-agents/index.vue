<template>
  <v-container fluid class="pa-0">
    <v-tabs v-model="activeTab" class="px-4 pt-3" color="primary">
      <v-tab value="langgraph" prepend-icon="mdi-graph-outline">LangGraph</v-tab>
      <v-tab value="python" prepend-icon="mdi-language-python">Pure Python</v-tab>
    </v-tabs>
    <v-divider />

    <v-tabs-window v-model="activeTab">
      <v-tabs-window-item value="langgraph" class="pa-0">
        <TestAgentsTestAgentChat
          :base-url="graphAgentUrl"
          framework="langgraph"
          title="LangGraph Agent"
        />
      </v-tabs-window-item>
      <v-tabs-window-item value="python" class="pa-0">
        <TestAgentsTestAgentChat
          :base-url="pythonAgentUrl"
          framework="raw_python"
          title="Pure Python Agent"
        />
      </v-tabs-window-item>
    </v-tabs-window>
  </v-container>
</template>

<script setup lang="ts">
definePageMeta({ title: 'Agent Sandbox' })

const config = useRuntimeConfig()
const graphAgentUrl = (config.public.testAgentGraphUrl as string) || 'http://localhost:8004'
const pythonAgentUrl = (config.public.testAgentPythonUrl as string) || 'http://localhost:8003'

const route = useRoute()
const activeTab = ref((route.query.tab as string) || 'langgraph')

watch(activeTab, (tab) => {
  navigateTo({ query: { tab } }, { replace: true })
})
</script>
