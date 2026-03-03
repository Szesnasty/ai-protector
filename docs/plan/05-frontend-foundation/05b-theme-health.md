# 05b — Theme & Health Indicator

| | |
|---|---|
| **Parent** | [Step 05 — Frontend Foundation](SPEC.md) |
| **Prev sub-step** | [05a — Layout Shell](05a-layout-shell.md) |
| **Next sub-step** | [05c — API Layer (Axios + Vue Query + VeeValidate)](05c-api-layer.md) |
| **Estimated time** | 1.5–2 hours |

> **Note:** This sub-step creates the health composable with a basic `$fetch` call first.
> In step 05c it gets refactored to use `healthService.ts` (Axios) + Vue Query `useQuery`.
> This order avoids a chicken-and-egg problem — we need the health dot working before the full API layer is wired.

---

## Goal

Add a dark/light theme toggle (persisted to `localStorage`) and a live health indicator that polls the proxy service `GET /health` endpoint. Both live in the app bar.

> **Convention:** All `.vue` files use `<script setup lang="ts">` (Composition API + TypeScript).
> Component files use **kebab-case** (`health-indicator.vue`), templates use `<health-indicator />`.

---

## Tasks

### 1. Theme toggle

- [ ] Create `app/composables/useAppTheme.ts`:
  ```typescript
  export const useAppTheme = () => {
    const theme = useTheme()           // Vuetify's useTheme()
    const isDark = computed(() => theme.global.current.value.dark)

    const toggle = () => {
      theme.global.name.value = isDark.value ? 'light' : 'dark'
      localStorage.setItem('ai-protector-theme', theme.global.name.value)
    }

    // Restore from localStorage on init
    onMounted(() => {
      const saved = localStorage.getItem('ai-protector-theme')
      if (saved && ['dark', 'light'].includes(saved)) {
        theme.global.name.value = saved
      }
    })

    return { isDark, toggle }
  }
  ```
- [ ] Add `v-btn` with `mdi-weather-sunny` / `mdi-weather-night` icon in app bar
- [ ] Toggle calls `useAppTheme().toggle()`
- [ ] Icon changes reactively based on `isDark`

### 2. Health composable (`app/composables/useHealth.ts`) — initial version

This is the **initial version** using raw `$fetch`. It gets refactored in 05c to Vue Query + Axios.

- [ ] Calls `GET {apiBase}/health` (from `runtimeConfig.public.apiBase`)
- [ ] Returns reactive state:
  ```typescript
  interface HealthState {
    status: 'ok' | 'degraded' | 'error' | 'loading'
    services: Record<string, { status: string; detail?: string }>
    lastChecked: Date | null
    error: string | null
  }
  ```
- [ ] Polls every **30 seconds** (`setInterval`)
- [ ] First call fires immediately on composable init
- [ ] Clears interval on component unmount (`onUnmounted`)
- [ ] On fetch error → sets `status: 'error'`
- [ ] Timeout: 5 seconds per request (don't hang if proxy is unreachable)

### 3. Health indicator component (`app/components/health-indicator.vue`)

Uses `<script setup lang="ts">` + **Vuetify components** throughout:

- [ ] Small colored dot in the app bar (right side, before theme toggle):
  | Status | Color | Vuetify icon |
  |--------|-------|------|
  | `ok` | `success` (green) | `mdi-circle` via `v-icon` |
  | `degraded` | `warning` (orange) | `mdi-circle` via `v-icon` |
  | `error` | `error` (red) | `mdi-circle` via `v-icon` |
  | `loading` | `grey` | `mdi-loading` via `v-progress-circular` |
- [ ] `v-tooltip` on hover showing:
  - Overall status text + last checked time (formatted with `toLocaleTimeString()`)
  - Per-service status as `v-list` with `v-list-item` per service
  - Each `v-list-item` has prepend `v-icon` color-coded by service status
  - Error detail shown as `v-list-item-subtitle` if any service is unhealthy
- [ ] Wrap the whole thing in a `v-btn` with `variant="text"` for consistent app bar spacing

### 4. Wire into layout

- [ ] Add `<health-indicator />` and theme toggle `v-btn` to app bar's `append` slot
- [ ] Order: `<health-indicator />` → theme toggle (left to right)
- [ ] Ensure both render correctly in both dark and light themes

---

## Proxy Health Response (reference)

The `GET /health` endpoint returns:

```json
{
  "status": "ok",
  "services": {
    "database": { "status": "ok" },
    "redis": { "status": "ok" },
    "ollama": { "status": "ok" },
    "langfuse": { "status": "ok" }
  },
  "version": "0.1.0"
}
```

When a service is down:
```json
{
  "status": "degraded",
  "services": {
    "database": { "status": "ok" },
    "redis": { "status": "error", "detail": "Connection refused" },
    "ollama": { "status": "ok" },
    "langfuse": { "status": "error", "detail": "HTTP 503" }
  },
  "version": "0.1.0"
}
```

---

## Definition of Done

- [ ] Theme toggle `v-btn` visible in app bar (sun/moon icon)
- [ ] Clicking toggle switches between dark and light themes instantly
- [ ] Refreshing browser preserves selected theme (localStorage key: `ai-protector-theme`)
- [ ] All `.vue` files use `<script setup lang="ts">` (Composition API)
- [ ] Health dot shows green `v-icon` when proxy-service + infra are running
- [ ] Health dot shows red `v-icon` when proxy-service is stopped
- [ ] Hovering health dot shows `v-tooltip` with `v-list` of per-service breakdown
- [ ] Tooltip shows last checked time
- [ ] Health polls every 30s (verify in Network tab: periodic GET /health)
- [ ] No CORS errors in console (proxy serves `Access-Control-Allow-Origin: http://localhost:3000`)
- [ ] Both features work in dark and light themes

---

| **Prev** | **Next** |
|---|---|
| [05a — Layout Shell](05a-layout-shell.md) | [05c — API Layer & Composables](05c-api-layer.md) |
