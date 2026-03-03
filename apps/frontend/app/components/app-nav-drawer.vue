<template>
  <v-list density="compact" nav>
    <v-list-item
      v-for="item in navItems"
      :key="item.to"
      :to="item.to"
      :prepend-icon="item.icon"
      :title="item.title"
      exact
    />
    <v-divider class="my-2" />
    <v-list-subheader>Manage</v-list-subheader>
    <v-list-item
      v-for="item in manageItems"
      :key="item.to"
      :to="item.to"
      :prepend-icon="item.icon"
      :title="item.title"
      exact
    />
  </v-list>
</template>

<script setup lang="ts">
interface NavItem {
  title: string
  icon: string
  to: string
}

const navItems: NavItem[] = [
  { title: 'Playground', icon: 'mdi-chat-processing', to: '/playground' },
  { title: 'Agent Demo', icon: 'mdi-robot', to: '/agent' },
  { title: 'Security Rules', icon: 'mdi-shield-lock-outline', to: '/rules' },
]

const manageItems: NavItem[] = [
  { title: 'Policies', icon: 'mdi-shield-lock', to: '/policies' },
  { title: 'Request Log', icon: 'mdi-format-list-bulleted', to: '/requests' },
  { title: 'Analytics', icon: 'mdi-chart-bar', to: '/analytics' },
]
</script>
