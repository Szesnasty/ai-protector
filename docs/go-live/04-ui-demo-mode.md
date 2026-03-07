# 04 — UI Demo Mode

> **Priority:** Important | **Effort:** 1–2h | **Dependencies:** 01-mock-provider, 02-docker-profiles

---

## Goal

Tell the user clearly that they're in demo mode — what's real, what's mocked — without polluting every LLM response. One badge, one tooltip, clear model selector behavior.

---

## 1. Health endpoint extension

### 1.1 Proxy-service: extend `/health` response

Add `mode` and `provider` fields to `HealthResponse`:

```python
class HealthResponse(BaseModel):
    status: str                    # "ok" | "degraded"
    version: str
    mode: str                      # NEW: "demo" | "real"
    provider: str                  # NEW: "mock" | "ollama" | "external"
    services: dict[str, ServiceHealth]
    metrics: HealthMetrics | None
```

Logic for `provider`:
```python
settings = get_settings()
if settings.mode == "demo":
    provider = "mock"
elif any external keys configured:
    provider = "external"
else:
    provider = "ollama"
```

### 1.2 Agent-demo: extend `/health`

Same pattern — add `mode` field so frontend knows agent is also in demo.

---

## 2. Frontend: composable `useAppMode`

New composable that fetches mode info from health endpoint once on app load:

### `app/composables/useAppMode.ts`

```typescript
interface AppMode {
  mode: 'demo' | 'real'
  provider: 'mock' | 'ollama' | 'external'
  version: string
}

export function useAppMode() {
  const appMode = useState<AppMode | null>('appMode', () => null)
  const isDemo = computed(() => appMode.value?.mode === 'demo')
  const isMock = computed(() => appMode.value?.provider === 'mock')

  async function fetchMode() {
    if (appMode.value) return  // Already fetched
    try {
      const data = await $fetch<AppMode>(`${useRuntimeConfig().public.apiBase}/health`)
      appMode.value = {
        mode: data.mode ?? 'real',
        provider: data.provider ?? 'ollama',
        version: data.version ?? '0.1.0',
      }
    } catch {
      appMode.value = { mode: 'real', provider: 'ollama', version: '0.1.0' }
    }
  }

  return { appMode, isDemo, isMock, fetchMode }
}
```

Call `fetchMode()` in `app.vue` or layout on mount.

---

## 3. Demo mode badge

### 3.1 Location: `app-nav-drawer.vue` (sidebar header area)

Persistent chip visible on every page when in demo mode:

```vue
<v-chip
  v-if="isDemo"
  color="amber"
  variant="tonal"
  size="small"
  class="ml-2"
  prepend-icon="mdi-flask-outline"
>
  Demo Mode
  <v-tooltip activator="parent" location="bottom" max-width="320">
    <div class="text-body-2">
      <strong>LLM responses are simulated</strong> (mock provider).<br />
      The security pipeline runs for real — NeMo Guardrails, Presidio PII
      detection, custom rules, RBAC, and all agent gates are active.<br /><br />
      <strong>Want real LLM responses?</strong> Go to
      <em>Settings → API Keys</em> and paste an OpenAI or Anthropic key.
    </div>
  </v-tooltip>
</v-chip>
```

### 3.2 Design

- **Color:** Amber/warning (visible but not alarming)
- **Icon:** `mdi-flask-outline` (lab/experiment feel)
- **Always visible** in sidebar — user sees it on every page
- **Tooltip** explains: what's mocked, what's real, how to upgrade

---

## 4. Model selector behavior

### 4.1 Current state

Model selector dropdown in playground/agent shows models fetched from `/v1/models` (Ollama model list). In demo mode, Ollama is not running → empty list or error.

### 4.2 Changes

**In demo mode:**
- `/v1/models` endpoint returns a single mock model: `{ id: "demo", name: "Demo (Mock)" }`
- Model selector shows `Demo (Mock)` as the only option (pre-selected)
- Below the selector, a hint: "Paste an API key in Settings to unlock real models"
- If user has pasted API key → external models appear in the list alongside `Demo (Mock)`

**Proxy-service `src/routers/models.py`:**
```python
@router.get("/v1/models")
async def list_models(settings: Settings = Depends(get_settings)):
    models = []

    # Always include mock in demo mode
    if settings.mode == "demo":
        models.append({"id": "demo", "object": "model", "owned_by": "mock"})

    # Try Ollama models (skip in demo mode or if Ollama unavailable)
    if settings.mode == "real":
        try:
            ollama_models = await fetch_ollama_models()
            models.extend(ollama_models)
        except:
            pass

    # Always include external models catalog
    models.extend(EXTERNAL_MODELS)

    return {"object": "list", "data": models}
```

### 4.3 Playground model selector UI

```vue
<v-select
  v-model="selectedModel"
  :items="models"
  item-title="name"
  item-value="id"
  label="Model"
>
  <template #append-inner>
    <v-chip v-if="isDemo && selectedModel === 'demo'" size="x-small" color="amber">
      mock
    </v-chip>
  </template>
</v-select>

<p v-if="isDemo" class="text-caption text-medium-emphasis mt-1">
  <v-icon size="x-small">mdi-key</v-icon>
  Paste an API key in <router-link to="/settings">Settings</router-link> to use real models.
</p>
```

---

## 5. Response indicator (subtle)

When a response comes from MockProvider, the proxy includes `x-provider: mock` header. Frontend can show a small indicator per message:

```vue
<v-chip v-if="message.provider === 'mock'" size="x-small" variant="text" class="ml-1">
  <v-icon size="x-small" start>mdi-flask-outline</v-icon>
  simulated
</v-chip>
```

This is **per-message** (not blocking text in the response content) — subtle and non-intrusive.

---

## 6. Files to create / modify

### New files:
| File | Purpose |
|------|---------|
| `apps/frontend/app/composables/useAppMode.ts` | Fetch and expose mode/provider state |

### Modified files:
| File | Change |
|------|--------|
| `apps/proxy-service/src/routers/health.py` | Add `mode`, `provider` to response |
| `apps/proxy-service/src/routers/models.py` | Return mock model in demo mode |
| `apps/agent-demo/src/routers/health.py` | Add `mode` to response |
| `apps/frontend/app/components/app-nav-drawer.vue` | Demo mode badge + tooltip |
| `apps/frontend/app/pages/playground.vue` | Model selector hint |
| `apps/frontend/app/pages/agent.vue` | Model selector hint |

---

## 7. Test plan

| Test | What to verify |
|------|---------------|
| `/health` in demo mode | Returns `mode: "demo"`, `provider: "mock"` |
| `/v1/models` in demo mode | Returns `demo` model + external catalog |
| Nav drawer in demo mode | Amber "Demo Mode" chip visible with tooltip |
| Nav drawer in real mode | No badge |
| Model selector in demo | Shows "Demo (Mock)" pre-selected |
| Paste API key → re-check | Provider switches from mock to real; badge stays (mode is still demo) |
