# Step 23b — Frontend: API Key Settings & Model Selector

| | |
|---|---|
| **Parent** | [Step 23 — External LLM Providers](SPEC.md) |
| **Estimated time** | 3–4 hours |
| **Depends on** | [23a — Backend Provider Routing](23a-provider-routing.md) |
| **Produces** | `app/pages/settings.vue`, `app/composables/useApiKeys.ts`, `app/composables/useModels.ts`, updated model selectors |

---

## Goal

Create a "Settings" page where users can paste API keys for external LLM providers.
Keys are stored in the **browser** (SessionStorage by default, localStorage opt-in) —
**never sent to the server for storage**. Update the Playground and Agent Demo model
selectors to show available external models and inject the `x-api-key` header into
every chat request.

---

## Tasks

### 1. API Keys Composable

**File**: `app/composables/useApiKeys.ts`

```typescript
const STORAGE_PREFIX = 'aiprotector:apiKey:'
const REMEMBER_PREFIX = 'aiprotector:remember:'

interface StoredKey {
  provider: string      // "openai", "anthropic", etc.
  maskedKey: string     // "sk-...xyz" (for display)
  remembered: boolean   // localStorage or sessionStorage
}

export function useApiKeys() {
  const keys = ref<StoredKey[]>([])

  function saveKey(provider: string, apiKey: string, remember: boolean): void {
    const storage = remember ? localStorage : sessionStorage
    storage.setItem(`${STORAGE_PREFIX}${provider}`, apiKey)

    // Track "remember" preference in localStorage (survives session)
    if (remember) {
      localStorage.setItem(`${REMEMBER_PREFIX}${provider}`, 'true')
    } else {
      localStorage.removeItem(`${REMEMBER_PREFIX}${provider}`)
    }

    refreshKeys()
  }

  function getKey(provider: string): string | null {
    // Check both storages — localStorage takes precedence if "remembered"
    return localStorage.getItem(`${STORAGE_PREFIX}${provider}`)
        ?? sessionStorage.getItem(`${STORAGE_PREFIX}${provider}`)
  }

  function removeKey(provider: string): void {
    sessionStorage.removeItem(`${STORAGE_PREFIX}${provider}`)
    localStorage.removeItem(`${STORAGE_PREFIX}${provider}`)
    localStorage.removeItem(`${REMEMBER_PREFIX}${provider}`)
    refreshKeys()
  }

  function getKeyForModel(model: string): string | null {
    // Detect provider from model name (client-side mirror of backend logic)
    const provider = detectProviderClient(model)
    if (provider === 'ollama') return null  // Ollama needs no key
    return getKey(provider)
  }

  function hasKeyForProvider(provider: string): boolean {
    return getKey(provider) !== null
  }

  function refreshKeys(): void {
    // Scan both storages for all known providers
    keys.value = PROVIDERS
      .map(p => {
        const key = getKey(p.id)
        if (!key) return null
        return {
          provider: p.id,
          maskedKey: maskKey(key),
          remembered: localStorage.getItem(`${REMEMBER_PREFIX}${p.id}`) === 'true',
        }
      })
      .filter(Boolean) as StoredKey[]
  }

  // Initialize on mount
  onMounted(refreshKeys)

  return { keys, saveKey, getKey, removeKey, getKeyForModel, hasKeyForProvider, refreshKeys }
}
```

**Helper functions:**
```typescript
function maskKey(key: string): string {
  if (key.length <= 8) return '****'
  return `${key.slice(0, 3)}...${key.slice(-4)}`
}

const PROVIDERS = [
  { id: 'openai',    name: 'OpenAI',    icon: 'mdi-creation' },
  { id: 'anthropic', name: 'Anthropic', icon: 'mdi-robot' },
  { id: 'google',    name: 'Google',    icon: 'mdi-google' },
  { id: 'mistral',   name: 'Mistral',   icon: 'mdi-wind' },
] as const

function detectProviderClient(model: string): string {
  const m = model.toLowerCase()
  if (m.startsWith('gpt-') || m.startsWith('o1') || m.startsWith('o3')) return 'openai'
  if (m.startsWith('claude-') || m.startsWith('anthropic/')) return 'anthropic'
  if (m.startsWith('gemini/') || m.startsWith('gemini-')) return 'google'
  if (m.startsWith('mistral-') || m.startsWith('mistral/') || m.startsWith('codestral')) return 'mistral'
  return 'ollama'
}
```

### 2. Models Composable

**File**: `app/composables/useModels.ts`

```typescript
export function useModels() {
  const { hasKeyForProvider } = useApiKeys()

  // Fetch model catalog from backend
  const { data: allModels, isLoading } = useQuery<ModelInfo[]>({
    queryKey: ['models'],
    queryFn: () => api.get('/v1/models').then(r => r.data.models),
  })

  // Computed: models grouped by provider, with availability flag
  const groupedModels = computed(() => {
    if (!allModels.value) return []
    return allModels.value.map(m => ({
      ...m,
      available: m.provider === 'ollama' || hasKeyForProvider(m.provider),
    }))
  })

  // Only available models (have key or Ollama)
  const availableModels = computed(() =>
    groupedModels.value.filter(m => m.available)
  )

  return { allModels, groupedModels, availableModels, isLoading }
}
```

### 3. Inject `x-api-key` Header in Chat Requests

**File**: `app/services/chatService.ts` (or `app/composables/useChat.ts`)

When sending chat/streaming requests, include the API key from browser storage:

```typescript
export async function streamChat(options: StreamOptions, callbacks: StreamCallbacks) {
  const { getKeyForModel } = useApiKeys()
  const apiKey = getKeyForModel(options.model)

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (apiKey) {
    headers['x-api-key'] = apiKey    // ← injected from SessionStorage
  }

  const response = await fetch(`${baseURL}/v1/chat/completions`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ ... }),
  })
  // ... streaming logic
}
```

**Key point**: The API key goes in the **request header**, not in the body.
Backend reads `request.headers.get("x-api-key")` and passes to LiteLLM.

### 4. Settings Page

**File**: `app/pages/settings.vue`

**Layout:**

```
┌─────────────────────────────────────────────────────────┐
│  ⚙️ Settings                                            │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  API Keys                                               │
│  Keys are stored in your browser only.                  │
│  We never send them to our server for storage.          │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  ✨ OpenAI                        sk-...xyz      │   │
│  │  ☑ Remember on this device          [Remove]    │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  🤖 Anthropic                     sk-...abc      │   │
│  │  ☐ Remember on this device          [Remove]    │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  🔷 Google                        [Add Key]      │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  💨 Mistral                       [Add Key]      │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  │
│  ℹ️  Ollama (local) is always available — no key needed │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Add Key Dialog:**

```
┌─────────────────────────────────────────────┐
│  Add OpenAI API Key                         │
│                                             │
│  API Key:  [sk-proj-..._______________]     │
│  ☐ Remember on this device                  │
│                                             │
│  🔒 Your key is stored in this browser      │
│     only and never sent to our server       │
│     for storage.                            │
│                                             │
│            [Cancel]  [Save]                 │
└─────────────────────────────────────────────┘
```

**Behavior:**
- Each provider has a card — either showing masked key + Remove button, or an "Add Key" button
- "Remember on this device" checkbox → localStorage (persists) vs SessionStorage (closes with tab)
- Toast notification: "✓ OpenAI key saved (session only)" or "✓ OpenAI key saved (remembered)"
- Remove → instant delete from storage, no confirmation needed (it's just browser storage)
- No `POST` to server — everything is client-side

### 5. Navigation

**File**: `app/components/app-nav-drawer.vue`

Add "Settings" to the `manageItems` array:

```typescript
const manageItems: NavItem[] = [
  { title: 'Policies', icon: 'mdi-shield-lock', to: '/policies' },
  { title: 'Request Log', icon: 'mdi-format-list-bulleted', to: '/requests' },
  { title: 'Analytics', icon: 'mdi-chart-bar', to: '/analytics' },
  { title: 'Settings', icon: 'mdi-cog', to: '/settings' },     // ← NEW
]
```

### 6. Update Playground Model Selector

**File**: `app/components/playground/playground-config-sidebar.vue` (or wherever model selector lives)

Currently the model is hardcoded or static. After this step:

```typescript
const { groupedModels, availableModels } = useModels()

// v-select with:
// - All models listed, external ones grayed out if no key
// - Tooltip on disabled items: "Add API key in Settings"
// - Provider name as group header
// - Provider icon next to each model
```

The model selector shows:
- All Ollama models (always available, always selectable)
- External models listed but **disabled** (grayed out) if no API key in browser storage
- Clicking disabled model → snackbar: "Add your OpenAI key in Settings → API Keys"
- Provider icon + name as visual grouping

### 7. Update Agent Demo Model Selector

Same pattern as Playground — the Agent Demo should also allow selecting external models.
Reuse `useModels()` composable.

### 8. TypeScript Types

**File**: `app/types/api.ts` — add:

```typescript
export interface ModelInfo {
  id: string        // "gpt-4o" or "ollama/llama3.1:8b"
  provider: string  // "openai", "anthropic", "google", "mistral", "ollama"
  name: string      // "GPT-4o", "Llama 3.1 8B"
}
```

---

## Storage Keys Reference

| Key | Storage | Purpose |
|-----|---------|---------|
| `aiprotector:apiKey:openai` | Session or Local | OpenAI API key (raw) |
| `aiprotector:apiKey:anthropic` | Session or Local | Anthropic API key (raw) |
| `aiprotector:apiKey:google` | Session or Local | Google AI API key (raw) |
| `aiprotector:apiKey:mistral` | Session or Local | Mistral API key (raw) |
| `aiprotector:remember:openai` | Local | Whether to persist across sessions |

---

## Tests

| Test | Assertion |
|------|-----------|
| `test_save_key_session_storage` | `saveKey("openai", "sk-abc", false)` → `sessionStorage` has key |
| `test_save_key_local_storage` | `saveKey("openai", "sk-abc", true)` → `localStorage` has key |
| `test_get_key_returns_stored` | After save → `getKey("openai")` returns key |
| `test_remove_key_clears_both` | After remove → both storages empty for provider |
| `test_mask_key_long` | `maskKey("sk-proj-abc123xyz")` → `"sk-...3xyz"` |
| `test_mask_key_short` | `maskKey("abc")` → `"****"` |
| `test_get_key_for_model` | `getKeyForModel("gpt-4o")` → returns openai key |
| `test_get_key_for_ollama` | `getKeyForModel("ollama/llama3.1:8b")` → `null` |
| `test_settings_page_renders` | Page mounts, shows all provider cards |
| `test_settings_page_add_key` | Enter key → card shows masked key |
| `test_settings_page_remove_key` | Click remove → card shows "Add Key" |
| `test_model_selector_disables_without_key` | No openai key → GPT-4o grayed out |
| `test_model_selector_enables_with_key` | Add openai key → GPT-4o selectable |
| `test_chat_request_includes_header` | With key → fetch sends `x-api-key` header |
| `test_chat_request_no_header_for_ollama` | Ollama model → no `x-api-key` header |
| `test_detect_provider_client` | `detectProviderClient("gpt-4o")` → `"openai"` |

---

## Definition of Done

- [ ] `app/composables/useApiKeys.ts` — save/get/remove keys in browser storage
- [ ] `app/composables/useModels.ts` — fetch model catalog, compute availability
- [ ] `app/pages/settings.vue` — provider cards, add/remove keys, "Remember" checkbox
- [ ] "Settings" item in navigation drawer
- [ ] `x-api-key` header injected into all chat requests (when key exists)
- [ ] Playground model selector shows all models, disables those without key
- [ ] Agent Demo model selector updated similarly
- [ ] TypeScript `ModelInfo` type defined
- [ ] **Keys never leave the browser** — no POST/PUT to server for key storage
- [ ] SessionStorage (default) clears on tab close; localStorage on explicit opt-in
- [ ] Toast notifications for save/remove actions
- [ ] All unit tests pass

---

| **Prev** | **Next** |
|---|---|
| [Step 23a — Provider Routing](23a-provider-routing.md) | [Step 24 — Compare Playground](../24-compare-playground/SPEC.md) |
