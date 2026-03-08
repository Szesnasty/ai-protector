<template>
  <v-chip
    :color="chipColor"
    :variant="expanded ? 'flat' : 'tonal'"
    size="small"
    label
    class="tool-call-chip"
    @click="expanded = !expanded"
  >
    <v-icon start size="14">
      {{ chipIcon }}
    </v-icon>
    <span class="text-caption font-weight-medium">{{ props.tool.tool }}</span>
    <v-icon end size="14">
      {{ expanded ? 'mdi-chevron-up' : 'mdi-chevron-down' }}
    </v-icon>
  </v-chip>

  <v-expand-transition>
    <v-card
      v-if="expanded"
      variant="outlined"
      :color="chipColor"
      class="tool-call-chip__details mt-1"
      density="compact"
    >
      <v-card-text class="pa-2">
        <div v-if="Object.keys(props.tool.args).length" class="mb-1">
          <span class="text-caption text-medium-emphasis">Args:</span>
          <pre class="tool-call-chip__pre text-caption">{{ JSON.stringify(props.tool.args, null, 2) }}</pre>
        </div>
        <div v-if="props.tool.result_preview">
          <span class="text-caption text-medium-emphasis">Result:</span>
          <div class="text-caption text-body-2 mt-1">{{ props.tool.result_preview }}</div>
        </div>
        <v-chip
          v-if="!props.tool.allowed"
          color="error"
          size="x-small"
          variant="flat"
          class="mt-1"
        >
          Blocked by RBAC
        </v-chip>
      </v-card-text>
    </v-card>
  </v-expand-transition>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { ToolCall } from '~/types/agent'

const props = defineProps<{
  tool: ToolCall
  verdict?: string
}>()

/** Tool chip color logic:
 *  - Tool blocked by RBAC → always red (error)
 *  - Tool allowed + overall ALLOW → green (success)
 *  - Tool allowed + overall BLOCK → neutral amber (ran, but request was blocked)
 */
const chipColor = computed(() => {
  if (!props.tool.allowed) return 'error'
  if (props.verdict?.toLowerCase() === 'block') return 'blue-grey'
  return 'success'
})

const chipIcon = computed(() => {
  if (!props.tool.allowed) return 'mdi-close-circle'
  if (props.verdict?.toLowerCase() === 'block') return 'mdi-minus-circle-outline'
  return 'mdi-check-circle'
})

const expanded = ref(false)
</script>

<style lang="scss" scoped>
.tool-call-chip {
  cursor: pointer;

  &__details {
    border-radius: 4px;
  }

  &__pre {
    background: rgba(var(--v-theme-on-surface), 0.05);
    border-radius: 4px;
    padding: 4px 8px;
    margin-top: 2px;
    overflow-x: auto;
    white-space: pre-wrap;
    word-break: break-all;
  }
}
</style>
