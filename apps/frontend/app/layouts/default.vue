<template>
  <v-app>
    <v-app-bar density="compact" elevation="1">
      <v-app-bar-nav-icon
        class="d-md-none"
        @click="drawer = !drawer"
      />
      <v-app-bar-title>AI Protector</v-app-bar-title>

      <template #append>
        <health-indicator />
        <v-btn
          :icon="isDark ? 'mdi-weather-sunny' : 'mdi-weather-night'"
          variant="text"
          @click="toggle"
        />
      </template>
    </v-app-bar>

    <v-navigation-drawer v-model="drawer">
      <v-list-item
        title="AI Protector"
        subtitle="LLM Firewall"
        prepend-icon="mdi-shield-check"
        nav
      />
      <v-divider />
      <app-nav-drawer />
    </v-navigation-drawer>

    <v-main>
      <slot />
    </v-main>
  </v-app>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useAppTheme } from '~/composables/useAppTheme'

const drawer = ref(true)
const { isDark, toggle } = useAppTheme()
</script>

<style lang="scss" scoped>
// Ensure main content fills viewport
.v-main {
  min-height: 100vh;
}
</style>
