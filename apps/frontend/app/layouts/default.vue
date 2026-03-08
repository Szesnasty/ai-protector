<template>
  <v-app>
    <v-app-bar density="compact" elevation="0" class="app-bar--shadow">
      <v-app-bar-nav-icon
        class="d-md-none"
        @click="drawer = !drawer"
      />
      <v-app-bar-title></v-app-bar-title>

      <template #append>
        <health-indicator />
        <v-btn
          :icon="isDark ? 'mdi-weather-sunny' : 'mdi-weather-night'"
          variant="text"
          @click="toggle"
        />
      </template>
    </v-app-bar>

    <v-navigation-drawer v-model="drawer" width="280">
      <nuxt-link to="/playground" class="sidebar-logo-item d-block text-decoration-none">
        <img :src="isDark ? '/logo-white.png' : '/logo.png'" alt="AI Protector" class="sidebar-logo" />
        <div class="text-caption text-secondary mt-1">LLM Firewall</div>
      </nuxt-link>
      <v-divider color="primary" thickness="2" />
      <app-nav-drawer />
    </v-navigation-drawer>

    <v-main>
      <slot />
    </v-main>
  </v-app>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAppTheme } from '~/composables/useAppTheme'
import { useAppMode } from '~/composables/useAppMode'

const drawer = ref(true)
const { isDark, toggle } = useAppTheme()
const { fetchMode } = useAppMode()

onMounted(() => {
  fetchMode()
})
</script>

<style lang="scss" scoped>
// Ensure main content fills viewport
.v-main {
  min-height: 100vh;
}

.sidebar-logo-item {
  padding: 16px 16px 8px !important;
  text-align: center;
}

.sidebar-logo {
  width: 100%;
  max-width: 140px;
  height: auto;
  object-fit: contain;
}

.app-bar--shadow {
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08) !important;
}
</style>
