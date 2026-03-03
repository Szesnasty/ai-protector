# 05a — Layout Shell

| | |
|---|---|
| **Parent** | [Step 05 — Frontend Foundation](SPEC.md) |
| **Next sub-step** | [05b — Theme & Health Indicator](05b-theme-health.md) |
| **Estimated time** | 1.5–2 hours |

---

## Goal

Replace `<NuxtWelcome />` with a Vuetify-based layout: persistent navigation drawer, top app bar, and file-based routing with placeholder pages for all MVP screens.

> **Convention:** All `.vue` files use `<script setup lang="ts">` (Composition API + TypeScript).
> Component files use **kebab-case** (`app-nav-drawer.vue`), templates use `<app-nav-drawer />`.

---

## Tasks

### 1. Clean up `app/app.vue`

- [ ] Remove `<NuxtWelcome />`
- [ ] Replace with:
  ```vue
  <template>
    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>
  </template>
  ```

### 2. Create layout (`app/layouts/default.vue`)

- [ ] `<script setup lang="ts">` — Composition API + TypeScript
- [ ] `v-app` wrapper (required by Vuetify)
- [ ] `v-app-bar` with:
  - App title: **"AI Protector"** (left side, `density="compact"`)
  - Hamburger toggle button for drawer (mobile)
  - Right side: placeholder slot for `<health-indicator />` + theme toggle (step 05b)
- [ ] `v-navigation-drawer` with:
  - `rail` mode support (collapse to icons on small screens)
  - Logo/title area at top
  - `v-list` with navigation items
- [ ] `v-main` wrapping `<slot />` for page content

### 3. Create navigation component (`app/components/app-nav-drawer.vue`)

- [ ] `<script setup lang="ts">` — Composition API + TypeScript
- [ ] Define typed nav items:
  ```typescript
  interface NavItem {
    title: string
    icon: string
    to: string
  }

  const navItems: NavItem[] = [
    { title: 'Playground', icon: 'mdi-chat-processing', to: '/playground' },
    { title: 'Agent Demo', icon: 'mdi-robot', to: '/agent' },
    { title: 'Policies', icon: 'mdi-shield-lock', to: '/policies' },
    { title: 'Request Log', icon: 'mdi-format-list-bulleted', to: '/requests' },
    { title: 'Analytics', icon: 'mdi-chart-bar', to: '/analytics' },
  ]
  ```
- [ ] Each item uses `<v-list-item :to="item.to">` with NuxtLink integration
- [ ] Active item highlighted via Vuetify's built-in `active` prop (matches route)
- [ ] Divider after first 2 items (separates "Use" from "Manage" sections)

### 4. Create placeholder pages

Create minimal placeholder pages — just enough to verify navigation works:

- [ ] `app/pages/index.vue` — redirect to `/playground`:
  ```vue
  <script setup lang="ts">
  navigateTo('/playground')
  </script>
  ```
- [ ] Each page uses `<script setup lang="ts">` + `<template>` (no Options API):
  ```vue
  <!-- app/pages/playground.vue -->
  <script setup lang="ts">
  definePageMeta({ title: 'Playground' })
  </script>

  <template>
    <v-container>
      <h1>Playground</h1>
      <p>Chat with LLM — coming in Step 10</p>
    </v-container>
  </template>
  ```
- [ ] `app/pages/agent.vue` — same pattern, title: `'Agent Demo'`, text: `'Coming in Step 13'`
- [ ] `app/pages/policies.vue` — title: `'Policies'`, text: `'Coming in Step 14'`
- [ ] `app/pages/requests.vue` — title: `'Request Log'`, text: `'Coming in Step 14'`
- [ ] `app/pages/analytics.vue` — title: `'Analytics'`, text: `'Coming in Step 15'`

---

## Definition of Done

- [ ] `npm run dev` → opens app with Vuetify layout (no NuxtWelcome)
- [ ] Navigation drawer visible with 5 items and correct icons
- [ ] Clicking each nav item navigates to the matching page (URL changes, content changes)
- [ ] Active nav item is visually highlighted
- [ ] `v-app-bar` shows "AI Protector" title
- [ ] Layout is responsive: drawer collapses to rail on `< md` breakpoint
- [ ] `http://localhost:3000/` redirects to `/playground`
- [ ] No console errors in browser
- [ ] No TypeScript errors

---

| **Parent** | **Next** |
|---|---|
| [Step 05 — Frontend Foundation](SPEC.md) | [05b — Theme & Health Indicator](05b-theme-health.md) |
