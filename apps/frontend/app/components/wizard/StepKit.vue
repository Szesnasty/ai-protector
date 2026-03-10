<template>
  <v-card flat>
    <v-card-title class="text-h6 d-flex align-center justify-space-between">
      <span>Integration Kit</span>
      <div class="d-flex ga-2">
        <v-btn
          size="small"
          color="primary"
          prepend-icon="mdi-cog-outline"
          :loading="isGenerating"
          @click="doGenerate"
        >
          Generate Kit
        </v-btn>
        <v-btn
          v-if="kit"
          size="small"
          variant="tonal"
          prepend-icon="mdi-download"
          @click="download"
        >
          Download ZIP
        </v-btn>
      </div>
    </v-card-title>
    <v-card-subtitle>Generated integration files for your agent</v-card-subtitle>

    <v-card-text>
      <div v-if="isGenerating" class="text-center py-12">
        <v-progress-circular indeterminate size="48" class="mb-4" />
        <p class="text-body-2 text-medium-emphasis">Generating integration kit...</p>
      </div>

      <div v-else-if="!kit?.files || !Object.keys(kit.files).length" class="text-center py-12">
        <v-icon icon="mdi-package-variant" size="64" color="primary" class="mb-4" />
        <p class="text-body-2 text-medium-emphasis mb-4">
          Click "Generate Kit" to create your integration files
        </p>
      </div>

      <template v-else>
        <v-tabs v-model="activeTab" density="compact" class="mb-2">
          <v-tab v-for="fname in fileNames" :key="fname" :value="fname">
            <v-icon :icon="fileIcon(fname)" size="16" class="mr-1" />
            {{ fname }}
          </v-tab>
        </v-tabs>

        <v-card variant="outlined" class="code-preview">
          <div class="d-flex justify-end pa-1">
            <v-btn
              size="x-small"
              variant="text"
              prepend-icon="mdi-content-copy"
              @click="doCopy"
            >
              Copy
            </v-btn>
          </div>
          <pre class="pa-3 text-caption">{{ activeContent }}</pre>
        </v-card>
        <v-snackbar v-model="copied" :timeout="2000" color="success">
          Copied to clipboard
        </v-snackbar>
      </template>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useAgentKit } from '~/composables/useAgentKit'

const props = defineProps<{
  agentId: string
}>()

const emit = defineEmits<{
  valid: [valid: boolean]
}>()

const { kit, isGenerating, generate, download, copyFile } = useAgentKit(() => props.agentId)

const activeTab = ref('')
const copied = ref(false)

const fileNames = computed(() => {
  if (!kit.value?.files) return []
  return Object.keys(kit.value.files)
})

const activeContent = computed(() => {
  if (!kit.value?.files || !activeTab.value) return ''
  return (kit.value.files as Record<string, string>)[activeTab.value] ?? ''
})

// Set first tab when kit loads
watch(fileNames, (names) => {
  if (names.length && !activeTab.value) {
    activeTab.value = names[0] ?? ''
  }
})

const fileIcon = (name: string): string => {
  if (name.endsWith('.py')) return 'mdi-language-python'
  if (name.endsWith('.yaml') || name.endsWith('.yml')) return 'mdi-file-code'
  if (name.endsWith('.md')) return 'mdi-language-markdown'
  if (name.endsWith('.env') || name.startsWith('.env')) return 'mdi-file-cog'
  return 'mdi-file-document'
}

const doGenerate = async () => {
  try {
    await generate()
  }
  catch {
    // handled by vue-query
  }
}

const doCopy = async () => {
  if (activeContent.value) {
    await copyFile(activeContent.value)
    copied.value = true
  }
}

watch(kit, (k) => emit('valid', !!k?.files && Object.keys(k.files).length > 0), { immediate: true })
</script>

<style lang="scss" scoped>
.code-preview {
  max-height: 500px;
  overflow: auto;
  background: rgba(0, 0, 0, 0.2);

  pre {
    white-space: pre-wrap;
    word-break: break-word;
    font-family: 'Fira Code', monospace;
  }
}
</style>
