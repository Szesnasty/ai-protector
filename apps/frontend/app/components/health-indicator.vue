<template>
  <v-menu :close-on-content-click="false" location="bottom end" max-width="340">
    <template #activator="{ props: menuProps }">
      <v-btn variant="text" size="small" v-bind="menuProps">
        <v-icon :color="dotColor" size="12">
          {{ isLoading ? 'mdi-loading' : 'mdi-circle' }}
        </v-icon>
      </v-btn>
    </template>

    <v-card class="health-card" min-width="300">
      <!-- Header -->
      <v-card-title class="d-flex align-center py-2 px-4">
        <v-icon :color="dotColor" size="14" class="mr-2">mdi-circle</v-icon>
        <span class="text-subtitle-2">Status: <strong>{{ status }}</strong></span>
        <v-spacer />
        <span v-if="lastChecked" class="text-caption text-grey">
          {{ lastChecked.toLocaleTimeString() }}
        </span>
      </v-card-title>

      <v-divider />

      <!-- Services -->
      <v-card-text class="pb-1 pt-2 px-4">
        <div class="text-overline text-grey mb-1">Services</div>
        <div
          v-for="(svc, name) in services"
          :key="String(name)"
          class="d-flex align-center mb-1"
        >
          <v-icon
            :color="svc.status === 'ok' ? 'success' : 'error'"
            size="10"
            class="mr-2"
          >
            mdi-circle
          </v-icon>
          <span class="text-body-2">{{ name }}</span>
          <v-spacer />
          <span v-if="svc.detail" class="text-caption text-error">{{ svc.detail }}</span>
        </div>
      </v-card-text>

      <v-divider v-if="metrics" />

      <!-- System Metrics -->
      <v-card-text v-if="metrics" class="pt-2 pb-3 px-4">
        <div class="text-overline text-grey mb-2">System Resources</div>

        <!-- RAM -->
        <div class="metric-row">
          <div class="d-flex align-center justify-space-between mb-1">
            <span class="text-caption d-flex align-center">
              <v-icon size="14" class="mr-1">mdi-memory</v-icon>RAM
            </span>
            <span class="text-caption font-weight-medium">
              {{ metrics.memory_used_mb.toLocaleString(undefined, { maximumFractionDigits: 0 }) }} /
              {{ metrics.memory_total_mb.toLocaleString(undefined, { maximumFractionDigits: 0 }) }} MB
            </span>
          </div>
          <v-progress-linear
            :model-value="metrics.memory_percent"
            :color="barColor(metrics.memory_percent)"
            height="6"
            rounded
          />
        </div>

        <!-- CPU -->
        <div class="metric-row mt-2">
          <div class="d-flex align-center justify-space-between mb-1">
            <span class="text-caption d-flex align-center">
              <v-icon size="14" class="mr-1">mdi-chip</v-icon>CPU
            </span>
            <span class="text-caption font-weight-medium">{{ metrics.cpu_percent }}%</span>
          </div>
          <v-progress-linear
            :model-value="metrics.cpu_percent"
            :color="barColor(metrics.cpu_percent)"
            height="6"
            rounded
          />
        </div>

        <!-- Disk -->
        <div class="metric-row mt-2">
          <div class="d-flex align-center justify-space-between mb-1">
            <span class="text-caption d-flex align-center">
              <v-icon size="14" class="mr-1">mdi-harddisk</v-icon>Disk
            </span>
            <span class="text-caption font-weight-medium">
              {{ metrics.disk_used_gb }} / {{ metrics.disk_total_gb }} GB
            </span>
          </div>
          <v-progress-linear
            :model-value="metrics.disk_percent"
            :color="barColor(metrics.disk_percent)"
            height="6"
            rounded
          />
        </div>

        <v-divider class="my-2" />

        <!-- Stats row -->
        <div class="d-flex justify-space-between text-caption">
          <div class="text-center">
            <div class="font-weight-bold text-body-2">{{ formatUptime(metrics.uptime_seconds) }}</div>
            <div class="text-grey">Uptime</div>
          </div>
          <div class="text-center">
            <div class="font-weight-bold text-body-2">{{ metrics.total_requests.toLocaleString() }}</div>
            <div class="text-grey">Requests</div>
          </div>
          <div class="text-center">
            <div class="font-weight-bold text-body-2">{{ metrics.threads }}</div>
            <div class="text-grey">Threads</div>
          </div>
        </div>
      </v-card-text>
    </v-card>
  </v-menu>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useHealth } from '~/composables/useHealth'

const { status, services, metrics, lastChecked, isLoading } = useHealth()

const dotColor = computed(() => {
  switch (status.value) {
    case 'ok': return 'success'
    case 'degraded': return 'warning'
    case 'error': return 'error'
    case 'loading': return 'grey'
    default: return 'grey'
  }
})

function barColor(percent: number): string {
  if (percent >= 90) return 'error'
  if (percent >= 70) return 'warning'
  return 'success'
}

function formatUptime(seconds: number): string {
  const d = Math.floor(seconds / 86400)
  const h = Math.floor((seconds % 86400) / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (d > 0) return `${d}d ${h}h`
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}
</script>

<style lang="scss" scoped>
.health-card {
  border-radius: 12px;
}
.metric-row {
  line-height: 1;
}
</style>
