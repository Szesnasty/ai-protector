<template>
  <TestAgentChat
    :base-url="graphAgentUrl"
    framework="langgraph"
    title="LangGraph Agent"
  />
</template>

<script setup lang="ts">
const config = useRuntimeConfig()
const graphAgentUrl = (config.public.testAgentGraphUrl as string) || 'http://localhost:8004'
</script>
