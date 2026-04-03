# Step 05 — Frontend Foundation

| | |
|---|---|
| **Phase** | Foundation |
| **Estimated time** | 5–7 hours |
| **Prev** | [Step 04 — Basic LLM Proxy](../04-basic-llm-proxy/SPEC.md) |
| **Next** | [Step 06 — Pipeline Core (LangGraph)](../06-pipeline-core/SPEC.md) |
| **Master plan** | [MVP-PLAN.md](../MVP-PLAN.md) |

---

## Goal

Replace the default `<NuxtWelcome />` with a complete **application shell**: Vuetify layout with sidebar navigation, top app bar, dark/light theme toggle, and a live health indicator that pings the proxy service. Set up the core data-fetching stack (**Axios** + **Vue Query**) and form validation (**VeeValidate** + **Vuetify**). No page content yet — just the frame and infrastructure that all future steps (10–15) will fill.

After this step, `npm run dev` shows a professional-looking empty dashboard with working navigation, a green/red health dot, and the entire API/form layer ready for feature development.

---

## Sub-steps

| # | File | Scope | Est. |
|---|------|-------|------|
| a | [05a — Layout Shell](05a-layout-shell.md) | `default.vue` layout, `v-app-bar`, `v-navigation-drawer`, `NuxtPage`, nav items | 1.5–2h |
| b | [05b — Theme & Health Indicator](05b-theme-health.md) | Dark/light toggle (persisted), health indicator with Vue Query polling | 1.5–2h |
| c | [05c — API Layer (Axios + Vue Query + VeeValidate)](05c-api-layer.md) | Axios instance in `services/`, Vue Query plugin, VeeValidate + Vuetify integration, types | 2–3h |

---

## Architecture Overview

```
app/
├── app.vue                      # <VueQueryProvider> + <NuxtLayout> + <NuxtPage>
├── layouts/
│   └── default.vue              # AppBar + NavDrawer + <slot />
├── pages/
│   ├── index.vue                # Redirect → /playground
│   ├── playground.vue           # Placeholder (Step 10)
│   ├── agent.vue                # Placeholder (Step 13)
│   ├── policies.vue             # Placeholder (Step 14)
│   ├── requests.vue             # Placeholder (Step 14)
│   └── analytics.vue            # Placeholder (Step 15)
├── services/
│   ├── api.ts                   # Axios instance (baseURL, interceptors, error mapping)
│   └── healthService.ts         # getHealth() → axios GET /health
├── composables/
│   ├── useAppTheme.ts           # Dark/light toggle, persisted to localStorage
│   └── useHealth.ts             # Vue Query useQuery wrapper around healthService
├── plugins/
│   └── vue-query.ts             # VueQueryPlugin registration + devtools
├── components/
│   ├── app-nav-drawer.vue       # Navigation drawer with route items
│   └── health-indicator.vue     # Colored dot + tooltip with service details
├── types/
│   └── api.ts                   # Shared TS interfaces (Health, Chat, Policy, Error)
└── assets/
    └── styles/
        └── main.scss            # Global overrides (minimal)
```

### Data Flow Pattern

```
Component → useQuery/useMutation (composable)
                ↓
         services/xxxService.ts (Axios calls)
                ↓
         services/api.ts (Axios instance + interceptors)
                ↓
         Proxy Service (FastAPI)
```

This pattern is consistent across all features:
- **services/** — pure functions returning Axios promises (no Vue reactivity)
- **composables/** — wrap services with `useQuery`/`useMutation` (caching, loading, error states)
- **components/** — consume composables, never call services directly

---

## Key Dependencies (new in this step)

| Package | Role |
|---------|------|
| `axios` | HTTP client — interceptors, typed responses, cancel tokens |
| `@tanstack/vue-query` | Server state management — caching, polling, mutations, devtools |
| `vee-validate` | Form validation — composable API, Zod integration |
| `@vee-validate/zod` | Zod schema resolver for VeeValidate |

> Zod is already in `package.json`. Vuetify is already configured.

---

## Conventions

- **Composition API only** — every `.vue` file uses `<script setup lang="ts">`, no Options API
- **TypeScript strict** — all composables, services, utils, and components are fully typed
- **SCSS** — `<style lang="scss" scoped>` in components, global styles in `assets/styles/main.scss`
- **Kebab-case components** — file names like `app-nav-drawer.vue`, used in templates as `<app-nav-drawer />`
- **Kebab-case in templates** — `<v-app-bar>`, `<health-indicator>`, never `<HealthIndicator>`

---

## Technical Decisions

### Why `layouts/default.vue` (not inline in `app.vue`)?
Nuxt layout system lets us swap layouts per page later (e.g. a fullscreen login page). Keeps `app.vue` minimal.

### Why placeholder pages instead of creating them in later steps?
Navigation items need real routes or Nuxt throws 404. Placeholder pages (`<h1>Coming soon</h1>`) cost nothing and let us verify navigation works end-to-end now.

### Why Axios (not Nuxt `$fetch`/`ofetch`)?
Axios provides request/response **interceptors** (global error handling, auth headers), **cancel tokens** (abort in-flight requests on unmount), and a familiar API that pairs cleanly with Vue Query. The `services/` folder pattern keeps HTTP concerns out of components and composables.

### Why Vue Query (not Pinia for server state)?
Pinia is for **client state** (theme, UI toggles, form drafts). Vue Query handles **server state** — automatic caching, background refetching, stale-while-revalidate, retry, polling (`refetchInterval`), and loading/error states out of the box. Using both: Pinia for UI, Vue Query for API data.

### Why VeeValidate + Zod (not manual validation)?
VeeValidate's composable API (`useForm`, `useField`) integrates with Vuetify inputs via scoped slots. Zod schemas are shared with the backend types, giving end-to-end type safety. We get field-level errors, dirty tracking, and submit handling for free.

### Why `services/` folder (not composables calling Axios directly)?
Separation of concerns: services are pure async functions (testable without Vue), composables add reactivity. This means services can be reused in Pinia actions, server routes, or tests without importing Vue Query.

### Why poll health every 30s (not WebSocket)?
Health status is not latency-critical. Polling via Vue Query's `refetchInterval: 30_000` is simpler, works behind proxies, and `GET /health` is already cheap (<10ms). WebSocket adds complexity for no real benefit here.

---

## Definition of Done (aggregate)

All sub-step DoDs must pass. Quick smoke test:

```bash
# Install new deps
cd apps/frontend && npm install

# Start frontend
npm run dev

# In browser → http://localhost:3000
# ✅ Dark theme by default
# ✅ Navigation drawer with 5 items (Playground, Agent Demo, Policies, Request Log, Analytics)
# ✅ Clicking nav items navigates to placeholder pages
# ✅ App bar with "AI Protector" title
# ✅ Theme toggle switches dark ↔ light and persists on reload
# ✅ Health indicator shows green dot (Vue Query polling) when proxy-service is running
# ✅ Health indicator shows red dot when proxy-service is down
# ✅ All .vue files use <script setup lang="ts"> (Composition API)
# ✅ All component files are kebab-case (app-nav-drawer.vue, health-indicator.vue)
# ✅ Vue Query Devtools accessible in browser (dev mode)
# ✅ `import { api } from '~/services/api'` works from any file
# ✅ No TypeScript errors: npx nuxi typecheck
# ✅ No lint errors: npm run lint
```

---

| **Prev** | **Next** |
|---|---|
| [Step 04 — Basic LLM Proxy](../04-basic-llm-proxy/SPEC.md) | [Step 06 — Pipeline Core](../06-pipeline-core/SPEC.md) |
