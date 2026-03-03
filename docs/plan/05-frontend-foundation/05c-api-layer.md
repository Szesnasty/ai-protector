# 05c — API Layer (Axios + Vue Query + VeeValidate)

| | |
|---|---|
| **Parent** | [Step 05 — Frontend Foundation](SPEC.md) |
| **Prev sub-step** | [05b — Theme & Health Indicator](05b-theme-health.md) |
| **Estimated time** | 2–3 hours |

---

## Goal

Set up the three core frontend infrastructure pieces:

1. **Axios** — typed HTTP client in `services/` with interceptors and error mapping
2. **Vue Query** — Nuxt plugin + service wrapping pattern, refactor health to use it
3. **VeeValidate** — Vuetify input integration + Zod resolver (ready for policies form in Step 14)

After this step, the data-fetching and form-validation patterns are established and every future feature follows the same shape.

> **Convention:** All code uses TypeScript. All `.vue` files use `<script setup lang="ts">`.
> Component files use **kebab-case**. Templates use kebab-case tags.

---

## Tasks

### 1. Install dependencies

- [ ] Install packages:
  ```bash
  cd apps/frontend
  npm install axios @tanstack/vue-query vee-validate @vee-validate/zod
  ```
- [ ] Verify all resolve in `node_modules` and `npm run dev` still starts

### 2. Axios instance (`app/services/api.ts`)

- [ ] Create `app/services/api.ts`:
  ```typescript
  import axios from 'axios'
  import type { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from 'axios'

  const api: AxiosInstance = axios.create({
    baseURL: useRuntimeConfig().public.apiBase as string,
    timeout: 30_000,
    headers: {
      'Content-Type': 'application/json',
    },
  })

  // Request interceptor — attach correlation ID
  api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
    config.headers['x-correlation-id'] = crypto.randomUUID()
    return config
  })

  // Response interceptor — extract data, map errors
  api.interceptors.response.use(
    (response) => response,
    (error: AxiosError<ApiError>) => {
      const mapped = mapApiError(error)
      return Promise.reject(mapped)
    },
  )

  export { api }
  ```
- [ ] **Note:** Because `useRuntimeConfig()` is a Nuxt composable (only available in Vue setup context), the actual pattern should use a **lazy init** or a Nuxt plugin to set `baseURL`. Implementation options:
  - Option A: Hardcode `import.meta.env.NUXT_PUBLIC_API_BASE` (simpler)
  - Option B: Create a `createApi()` factory called from a Nuxt plugin that sets `api.defaults.baseURL`
  - Either works; pick whichever feels cleaner during implementation

### 3. Error mapping utility (`app/services/api.ts` or `app/utils/apiErrors.ts`)

- [ ] Map Axios errors to user-friendly messages:
  ```typescript
  export interface AppError {
    message: string
    status: number | null
    code: string
    raw?: unknown
  }

  export function mapApiError(error: AxiosError<ApiError>): AppError {
    if (!error.response) {
      return {
        message: 'Cannot reach AI Protector service',
        status: null,
        code: 'NETWORK_ERROR',
      }
    }

    const { status, data } = error.response
    const serverMessage = data?.error?.message

    const map: Record<number, AppError> = {
      403: {
        message: serverMessage ?? 'Request blocked by policy',
        status: 403,
        code: 'BLOCKED',
        raw: data,
      },
      404: { message: 'Resource not found', status: 404, code: 'NOT_FOUND' },
      502: { message: 'LLM provider unavailable', status: 502, code: 'LLM_DOWN' },
      504: { message: 'LLM request timed out', status: 504, code: 'LLM_TIMEOUT' },
    }

    return map[status] ?? {
      message: serverMessage ?? `Server error (${status})`,
      status,
      code: 'SERVER_ERROR',
    }
  }
  ```

### 4. Health service (`app/services/healthService.ts`)

- [ ] Plain async function (no Vue reactivity):
  ```typescript
  import { api } from './api'
  import type { HealthResponse } from '~/types/api'

  export const healthService = {
    getHealth: (): Promise<HealthResponse> =>
      api.get<HealthResponse>('/health').then((r) => r.data),
  }
  ```

### 5. Vue Query plugin (`app/plugins/vue-query.ts`)

- [ ] Create Nuxt plugin:
  ```typescript
  import { VueQueryPlugin, QueryClient } from '@tanstack/vue-query'
  import type { VueQueryPluginOptions } from '@tanstack/vue-query'

  export default defineNuxtPlugin((nuxtApp) => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          staleTime: 30_000,          // 30s before considered stale
          retry: 1,                   // 1 retry on failure
          refetchOnWindowFocus: true,  // refetch when tab regains focus
        },
      },
    })

    const options: VueQueryPluginOptions = { queryClient }

    nuxtApp.vueApp.use(VueQueryPlugin, options)
  })
  ```
- [ ] Verify Vue Query Devtools are accessible (floating button in bottom-right in dev mode)

### 6. Refactor `useHealth` to Vue Query (`app/composables/useHealth.ts`)

- [ ] Replace manual `setInterval` polling with Vue Query's `useQuery`:
  ```typescript
  import { useQuery } from '@tanstack/vue-query'
  import { healthService } from '~/services/healthService'
  import type { HealthResponse } from '~/types/api'

  export const useHealth = () => {
    const { data, error, isLoading, dataUpdatedAt } = useQuery<HealthResponse>({
      queryKey: ['health'],
      queryFn: healthService.getHealth,
      refetchInterval: 30_000,        // poll every 30s
      refetchIntervalInBackground: true,
    })

    const status = computed(() => {
      if (isLoading.value) return 'loading'
      if (error.value) return 'error'
      return data.value?.status ?? 'error'
    })

    const services = computed(() => data.value?.services ?? {})

    const lastChecked = computed(() =>
      dataUpdatedAt.value ? new Date(dataUpdatedAt.value) : null,
    )

    return { status, services, lastChecked, error, isLoading }
  }
  ```
- [ ] Update `health-indicator.vue` if needed (should mostly work — same interface)
- [ ] Delete the old `setInterval` logic

### 7. VeeValidate + Vuetify integration

- [ ] Create a **thin integration helper** (`app/utils/vuetifyField.ts`) that bridges VeeValidate field state to Vuetify input props:
  ```typescript
  import { useField } from 'vee-validate'

  /**
   * Wraps useField() and returns props compatible with Vuetify inputs.
   * Usage in template: <v-text-field v-bind="field" />
   */
  export function useVuetifyField(name: string) {
    const { value, errorMessage, handleBlur } = useField<string>(name)

    const field = computed(() => ({
      modelValue: value.value,
      'onUpdate:modelValue': (v: string) => { value.value = v },
      errorMessages: errorMessage.value ? [errorMessage.value] : [],
      onBlur: handleBlur,
    }))

    return { field, value, errorMessage }
  }
  ```
- [ ] Create a **demo/smoke test** component to verify the integration works — this can be a hidden `/dev/form-test` page or just verified manually during development and removed:
  ```vue
  <!-- Verify VeeValidate + Vuetify + Zod work together -->
  <script setup lang="ts">
  import { useForm } from 'vee-validate'
  import { toTypedSchema } from '@vee-validate/zod'
  import { z } from 'zod'

  const schema = toTypedSchema(
    z.object({
      name: z.string().min(3, 'Min 3 characters'),
      email: z.string().email('Invalid email'),
    }),
  )

  const { handleSubmit } = useForm({ validationSchema: schema })
  const onSubmit = handleSubmit((values) => {
    console.log('Form submitted:', values)
  })
  </script>
  ```
- [ ] This is **infrastructure only** — actual forms come in Step 14 (Policies CRUD)

### 8. Types (`app/types/api.ts`)

- [ ] Shared TypeScript interfaces matching proxy schemas:
  ```typescript
  // ─── Health ───
  export interface ServiceHealth {
    status: 'ok' | 'error'
    detail?: string
  }

  export interface HealthResponse {
    status: 'ok' | 'degraded'
    services: Record<string, ServiceHealth>
    version: string
  }

  // ─── Chat (used in Step 10) ───
  export interface ChatMessage {
    role: 'system' | 'user' | 'assistant' | 'tool'
    content: string
    name?: string
  }

  export interface ChatCompletionRequest {
    model?: string
    messages: ChatMessage[]
    temperature?: number
    max_tokens?: number
    stream?: boolean
  }

  export interface ChatCompletionResponse {
    id: string
    object: string
    created: number
    model: string
    choices: Array<{
      index: number
      message: ChatMessage
      finish_reason: string | null
    }>
    usage: {
      prompt_tokens: number
      completion_tokens: number
      total_tokens: number
    } | null
  }

  // ─── Pipeline metadata (from response headers + block body) ───
  export interface PipelineDecision {
    decision: 'ALLOW' | 'MODIFY' | 'BLOCK'
    intent: string
    riskScore: number
    riskFlags: Record<string, unknown>
    blockedReason?: string
  }

  // ─── Policy (used in Step 14) ───
  export interface Policy {
    id: string
    name: string
    description: string | null
    config: Record<string, unknown>
    is_active: boolean
    version: number
    created_at: string
    updated_at: string
  }

  // ─── API Error (from proxy 403/4xx/5xx) ───
  export interface ApiError {
    error: {
      message: string
      type: string
      code: string
    }
    decision?: string
    risk_score?: number
    risk_flags?: Record<string, unknown>
    intent?: string
  }
  ```

---

## File Summary

New files created in this sub-step:

```
app/
├── services/
│   ├── api.ts                   # Axios instance + interceptors + error mapping
│   └── healthService.ts         # getHealth() — plain async function
├── plugins/
│   └── vue-query.ts             # Vue Query registration with defaults
├── composables/
│   └── useHealth.ts             # ← refactored: now uses useQuery + healthService
├── utils/
│   └── vuetifyField.ts          # VeeValidate ↔ Vuetify bridge helper
└── types/
    └── api.ts                   # All shared interfaces
```

---

## Definition of Done

- [ ] `npm install` adds `axios`, `@tanstack/vue-query`, `vee-validate`, `@vee-validate/zod`
- [ ] `import { api } from '~/services/api'` resolves correctly
- [ ] `api.get('/health')` returns typed `AxiosResponse<HealthResponse>`
- [ ] Network errors map to `AppError` with `code: 'NETWORK_ERROR'`
- [ ] 403 responses map to `AppError` with server's blocked reason
- [ ] Vue Query plugin registered — `useQuery` works in any component
- [ ] Vue Query Devtools floating button visible in dev mode
- [ ] `useHealth()` now uses `useQuery` with `refetchInterval: 30_000` (no manual `setInterval`)
- [ ] Health indicator still works identically (green/red dot, tooltip)
- [ ] `useVuetifyField('name')` returns `{ field, value, errorMessage }` compatible with `<v-text-field v-bind="field" />`
- [ ] VeeValidate + Zod schema validation works (verified manually or via test page)
- [ ] All types in `app/types/api.ts` match proxy service schemas
- [ ] `npx nuxi typecheck` passes
- [ ] `npm run lint` passes

---

| **Prev** | **Parent** |
|---|---|
| [05b — Theme & Health Indicator](05b-theme-health.md) | [Step 05 — Frontend Foundation](SPEC.md) |
