# Step 24b — Compare Playground UI

| | |
|---|---|
| **Parent** | [Step 24 — Compare Playground](SPEC.md) |
| **Estimated time** | 4–5 hours |
| **Depends on** | [24a — Direct Endpoint](24a-direct-endpoint.md), [23b — Frontend Settings](../23-external-providers/23b-frontend-settings.md) |
| **Produces** | `app/pages/compare.vue`, `app/composables/useCompareChat.ts`, compare components |

---

## Goal

Build a dual-panel chat page that sends the same prompt to **both** the protected proxy
and the unprotected direct endpoint simultaneously, showing results side-by-side.
This is the demo "wow" page that instantly proves AI Protector's value.

---

## Tasks

### 1. Navigation

**File**: `app/components/app-nav-drawer.vue`

Add "Compare" to `navItems`:

```typescript
const navItems: NavItem[] = [
  { title: 'Playground', icon: 'mdi-chat-processing', to: '/playground' },
  { title: 'Compare', icon: 'mdi-compare', to: '/compare' },           // ← NEW
  { title: 'Agent Demo', icon: 'mdi-robot', to: '/agent' },
  { title: 'Security Rules', icon: 'mdi-shield-lock-outline', to: '/rules' },
]
```

### 2. Compare Chat Composable

**File**: `app/composables/useCompareChat.ts`

```typescript
export function useCompareChat() {
  // Shared state
  const protectedMessages = ref<ChatMessage[]>([])
  const directMessages = ref<ChatMessage[]>([])
  const isProtectedStreaming = ref(false)
  const isDirectStreaming = ref(false)
  const protectedDecision = ref<PipelineDecision | null>(null)
  const protectedTiming = ref<number>(0)   // ms
  const directTiming = ref<number>(0)      // ms

  const config = reactive({
    policy: 'balanced',
    model: 'ollama/llama3.1:8b',
    temperature: 0.7,
  })

  async function send(text: string) {
    // 1. Push user message to BOTH panels
    // 2. Fire BOTH requests simultaneously (Promise.allSettled)
    //    - Left: streamChat({ url: '/v1/chat/completions', headers: { 'x-policy': config.policy } })
    //    - Right: streamChat({ url: '/v1/chat/direct' })
    // 3. Stream tokens into respective message arrays
    // 4. Capture timing for both
    // 5. Extract decision from protected response headers
  }

  function clear() { /* reset both panels */ }

  return {
    protectedMessages, directMessages,
    isProtectedStreaming, isDirectStreaming,
    protectedDecision, protectedTiming, directTiming,
    config, send, clear,
  }
}
```

**Key design**: Both streams fire simultaneously via `Promise.allSettled()`.
The user sees tokens appearing in both panels at the same time.

### 3. Compare Page

**File**: `app/pages/compare.vue`

**Layout:**

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Compare: Protected vs Unprotected          [Policy: balanced ▼]       │
│                                              [Model: gpt-4o ▼]        │
├─────────────────────────────────┬───────────────────────────────────────┤
│  🛡️ Protected (AI Protector)    │  ⚠️ Unprotected (Direct)             │
│                                 │                                       │
│  User: Ignore instructions...   │  User: Ignore instructions...         │
│                                 │                                       │
│  ⛔ BLOCKED                     │  Assistant: Sure! As DAN, I can       │
│  ┌───────────────────────────┐  │  do anything now! Here's how to       │
│  │ Risk: 0.92                │  │  bypass security...                   │
│  │ NeMo: role_bypass (0.85)  │  │                                       │
│  │ Injection: 0.99           │  │                                       │
│  │ Pipeline: 340ms           │  │  Direct: 2.1s                         │
│  └───────────────────────────┘  │                                       │
│                                 │                                       │
├─────────────────────────────────┴───────────────────────────────────────┤
│  [Type your message...                                        ] [Send] │
└─────────────────────────────────────────────────────────────────────────┘
```

**Components structure:**
```
compare.vue
├── compare-panel.vue (×2)     # Reusable panel with messages + metadata
│   ├── chat-message-list      # Reuse from playground
│   └── compare-decision-card  # Decision badge, risk, timing
├── compare-config-bar.vue     # Policy + model selectors (horizontal)
└── chat-input                 # Reuse from playground (single input for both)
```

### 4. Compare Panel Component

**File**: `app/components/compare/compare-panel.vue`

Each panel shows:
- **Header badge**: "🛡️ Protected" (green) or "⚠️ Unprotected" (orange/red)
- **Chat messages**: Streamed content (reuse existing message list component)
- **Decision card** (protected panel only):
  - Decision badge (ALLOW/BLOCK/MODIFY)
  - Risk score with color
  - Scanner results breakdown (NeMo, LLM Guard, Presidio)
  - Pipeline elapsed time
- **Timing** (both panels): elapsed time in ms
- **"Unprotected" warning** (direct panel): subtle banner explaining no scanning happened

### 5. Decision Comparison Card

**File**: `app/components/compare/compare-decision-card.vue`

When protected side blocks and direct side responds:

```
┌────────────────────────────────────┐
│  ⛔ This prompt was BLOCKED        │
│                                    │
│  Risk Score: ████████░░  0.92      │
│  Injection:  ████████░░  0.99      │
│  NeMo:       ███████░░░  0.85      │
│  Toxicity:   ░░░░░░░░░░  0.00      │
│                                    │
│  ⏱️ Scanned in 340ms               │
│                                    │
│  →  The unprotected side let this  │
│     attack through. ←              │
└────────────────────────────────────┘
```

### 6. Attack Scenarios Integration

The same `AttackScenariosPanel` (from Step 20) should work on the Compare page.
When an attack is selected:
1. Prompt auto-fills in the shared input
2. Sent to both endpoints simultaneously
3. User sees the attack blocked on left, passing on right

### 7. Streaming Service Extension

**File**: `app/services/chatService.ts` — add or modify to support custom URL:

```typescript
export async function streamChat(
  options: StreamOptions & { url?: string },  // ← allow custom URL
  callbacks: StreamCallbacks,
): Promise<Response> {
  const baseURL = import.meta.env.NUXT_PUBLIC_API_BASE ?? 'http://localhost:8000'
  const url = options.url
    ? `${baseURL}${options.url}`
    : `${baseURL}/v1/chat/completions`
  // ... rest remains the same
}
```

---

## Tests

| Test | Assertion |
|------|-----------|
| `test_compare_page_renders` | Both panels visible with correct headers |
| `test_compare_send_fires_both` | Single prompt → two simultaneous API calls |
| `test_compare_block_vs_allow` | Attack prompt → left BLOCKED, right has content |
| `test_compare_timing_displayed` | Both panels show elapsed time |
| `test_compare_decision_card` | Protected blocked → shows risk, scanner results |
| `test_compare_streaming` | Both panels stream tokens independently |
| `test_compare_clear` | Clear button resets both panels |
| `test_compare_attack_scenarios` | Attack panel sends to both endpoints |
| `test_compare_model_selector` | Models from `/v1/models` populate dropdown, external grayed without key |

---

## Definition of Done

- [ ] `app/pages/compare.vue` with dual-panel layout
- [ ] `app/composables/useCompareChat.ts` managing both streams
- [ ] `compare-panel.vue` reusable component for each side
- [ ] `compare-decision-card.vue` showing risk breakdown
- [ ] Single input sends to both endpoints simultaneously
- [ ] Protected panel: decision badge, risk score, scanner results, timing
- [ ] Direct panel: streamed response, timing, "Unprotected" warning
- [ ] "Compare" item in navigation drawer
- [ ] Model selector populated from `/v1/models` (grays out providers without browser-stored key)
- [ ] Attack Scenarios Panel integrated
- [ ] Both panels stream independently (one can block while other streams)

---

| **Prev** | **Next** |
|---|---|
| [Step 24a — Direct Endpoint](24a-direct-endpoint.md) | — |
