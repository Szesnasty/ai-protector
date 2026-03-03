<template>
  <v-btn variant="text" size="small">
    <v-icon :color="dotColor" size="12">
      {{ isLoading ? 'mdi-loading' : 'mdi-circle' }}
    </v-icon>
    <v-tooltip activator="parent" location="bottom">
      <div class="health-tooltip">
        <div class="text-subtitle-2 mb-1">
          Status: <strong>{{ status }}</strong>
        </div>
        <div v-if="lastChecked" class="text-caption text-grey mb-2">
          Last checked: {{ lastChecked.toLocaleTimeString() }}
        </div>
        <v-list density="compact" bg-color="transparent" class="pa-0">
          <v-list-item
            v-for="(svc, name) in services"
            :key="String(name)"
            density="compact"
            class="px-0"
          >
            <template #prepend>
              <v-icon
                :color="svc.status === 'ok' ? 'success' : 'error'"
                size="10"
                class="mr-2"
              >
                mdi-circle
              </v-icon>
            </template>
            <v-list-item-title class="text-caption">{{ name }}</v-list-item-title>
            <v-list-item-subtitle v-if="svc.detail" class="text-caption">
              {{ svc.detail }}
            </v-list-item-subtitle>
          </v-list-item>
        </v-list>
      </div>
    </v-tooltip>
  </v-btn>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useHealth } from '~/composables/useHealth'

const { status, services, lastChecked, isLoading } = useHealth()

const dotColor = computed(() => {
  switch (status.value) {
    case 'ok': return 'success'
    case 'degraded': return 'warning'
    case 'error': return 'error'
    case 'loading': return 'grey'
    default: return 'grey'
  }
})
</script>

<style lang="scss" scoped>
.health-tooltip {
  min-width: 180px;
}
</style>
