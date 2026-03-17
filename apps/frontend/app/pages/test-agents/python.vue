<template>
  <TestAgentsTestAgentChat
    :base-url="pythonAgentUrl"
    framework="raw_python"
    title="Pure Python Agent"
  />
</template>

<script setup lang="ts">
const config = useRuntimeConfig()
const pythonAgentUrl = (config.public.testAgentPythonUrl as string) || 'http://localhost:8003'
</script>
