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

- [x] Remove `<NuxtWelcome />`
- [x] Replace with:
  ```vue
  <template>
    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>
  </template>
  ```

### 2. Create layout (`app/layouts/default.vue`)

- [x] `<script setup lang="ts">` — Composition API + TypeScript
- [x] `v-app` wrapper (required by Vuetify)
- [x] `v-app-bar` with:
  - App title: **"AI Protector"** (left side, `density="compact"`)
  - Hamburger toggle button for drawer (mobile)
  - Right side: placeholder slot for `<health-indicator />` + theme toggle (step 05b)
- [x] `v-navigation-drawer` with:
  - `rail` mode support (collapse to icons on small screens)
  - Logo/title area at top
  - `v-list` with navigation items
- [x] `v-main` wrapping `<slot />` for page content

### 3. Create navigation component (`app/components/app-nav-drawer.vue`)

- [x] `<script setup lang="ts">` — Composition API + TypeScript
- [x] Define typed nav items:
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
- [x] Each item uses `<v-list-item :to="item.to">` with NuxtLink integration
- [x] Active item highlighted via Vuetify's built-in `active` prop (matches route)
- [x] Divider after first 2 items (separates "Use" from "Manage" sections)

### 4. Create placeholder pages

Create minimal placeholder pages — just enough to verify navigation works:

- [x] `app/pages/index.vue` — redirect to `/playground`:
  ```vue
  <script setup lang="ts">
  navigateTo('/playground')
  </script>
  ```
- [x] Each page uses `<script setup lang="ts">` + `<template>` (no Options API):
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
- [x] `app/pages/agent.vue` — same pattern, title: `'Agent Demo'`, text: `'Coming in Step 13'`
- [x] `app/pages/policies.vue` — title: `'Policies'`, text: `'Coming in Step 14'`
- [x] `app/pages/requests.vue` — title: `'Request Log'`, text: `'Coming in Step 14'`
- [x] `app/pages/analytics.vue` — title: `'Analytics'`, text: `'Coming in Step 15'`

---

## Definition of Done

- [x] `npm run dev` → opens app with Vuetify layout (no NuxtWelcome)
- [x] Navigation drawer visible with 5 items and correct icons
- [x] Clicking each nav item navigates to the matching page (URL changes, content changes)
- [x] Active nav item is visually highlighted
- [x] `v-app-bar` shows "AI Protector" title
- [x] Layout is responsive: drawer collapses to rail on `< md` breakpoint
- [x] `http://localhost:3000/` redirects to `/playground`
- [x] No console errors in browser
- [x] No TypeScript errors

---

| **Parent** | **Next** |
|---|---|
| [Step 05 — Frontend Foundation](SPEC.md) | [05b — Theme & Health Indicator](05b-theme-health.md) |
