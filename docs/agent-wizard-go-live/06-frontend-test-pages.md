# Step 06 — Frontend Test Pages

> **Effort:** 4 hours
> **Depends on:** steps 03, 04, 05 (agents running and reachable)
> **Blocks:** step 07 (E2E verification needs UI)

---

## Context

We add two new pages to the Nuxt frontend for testing wizard-generated configs
against the two test agents. Each page has the same layout: agent selector,
role selector, chat panel, and a gate log panel showing security decisions in real time.

---

## File Structure

```
apps/frontend/app/
  pages/
    test-agents/
      python.vue           ← /test-agents/python (port 8003)
      graph.vue            ← /test-agents/graph  (port 8004)
  components/
    test-agents/
      TestAgentChat.vue    ← Shared chat + gate log component
  composables/
    useTestAgent.ts        ← API calls to test agent endpoints
```

---

## Implementation Plan

### Step 1: Create `composables/useTestAgent.ts`

Composable that communicates with test agent endpoints.

```typescript
interface TestAgentConfig {
  baseUrl: string   // http://localhost:8003 or :8004
}

interface ChatRequest {
  message: string
  role: string
  tool?: string
  tool_args?: Record<string, any>
  confirmed?: boolean
}

interface GateLogEntry {
  gate: string
  decision: string
  reason?: string
  tool?: string
  role?: string
  findings?: Array<{ type: string; detail: string }>
  scan_findings?: Array<{ type: string; detail: string }>
}

interface ChatResponse {
  response: string
  blocked: boolean
  requires_confirmation?: boolean
  tool?: string
  tool_args?: Record<string, any>
  gate_log: GateLogEntry[]
}

interface ConfigStatus {
  loaded: boolean
  roles: string[]
  tools_in_rbac?: number
  policy_pack: string
}

// Composable:
// - loadConfig(agentId: string) → POST /load-config
// - chat(req: ChatRequest) → POST /chat
// - getConfigStatus() → GET /config-status
// - getHealth() → GET /health
// All using the provided baseUrl
```

**Key behaviors:**
- `loadConfig` calls `POST {baseUrl}/load-config` with `{ agent_id }` — fetches wizard kit
  from proxy-service and loads it into the running test agent
- `chat` calls `POST {baseUrl}/chat` — sends message with role, returns response + gate_log
- Uses TanStack Vue Query for `configStatus` (auto-refresh on invalidation)
- No global state needed — each page passes its own `baseUrl`

### Step 2: Create `components/test-agents/TestAgentChat.vue`

Shared component used by both pages. Props: `baseUrl`, `framework` (display label).

**Layout (3-column):**

```
┌──────────────────────────────────────────────────────────────────┐
│  Test Agent: Pure Python                   Config: ✅ Loaded     │
│  ┌─────────────────┐  ┌─────────────┐  ┌──────────────────────┐ │
│  │ Agent Selector   │  │ Role: [user]│  │ [Load Config]        │ │
│  │ [Order Manager ▼]│  │       [admin]│  │ Pack: customer_support│ │
│  └─────────────────┘  └─────────────┘  │ Roles: user, admin   │ │
│                                         └──────────────────────┘ │
├──────────────────────────────────┬───────────────────────────────┤
│  CHAT                            │  GATE LOG                     │
│                                  │                               │
│  You: Show me all orders         │  ┌─────────────────────────┐  │
│  🤖: {"orders": [...]}          │  │ ✅ pre_tool: ALLOW       │  │
│                                  │  │    tool: getOrders       │  │
│  You: Update order ORD-001       │  │    role: user            │  │
│  🤖: ❌ BLOCKED: Role 'user'    │  ├─────────────────────────┤  │
│     cannot use 'updateOrder'     │  │ 🔎 post_tool: FLAGGED   │  │
│                                  │  │    PII: email detected   │  │
│  You: List all users             │  ├─────────────────────────┤  │
│  🤖: {"users": [...]}          │  │ ❌ pre_tool: BLOCK       │  │
│                                  │  │    tool: updateOrder     │  │
│  ┌──────────────────────────┐    │  │    reason: RBAC denied   │  │
│  │ Type a message...   [Send]│    │  └─────────────────────────┘  │
│  └──────────────────────────┘    │                               │
└──────────────────────────────────┴───────────────────────────────┘
```

**Component features:**
1. **Agent selector** — dropdown of wizard agents filtered by framework (`raw_python` or `langgraph`).
   Uses `useAgents` composable (already exists) to fetch `/v1/agents`.
2. **Load Config button** — calls `POST /load-config` with selected agent's ID.
   Shows spinner while loading, then displays config status (roles, pack).
3. **Role selector** — radio buttons or segmented control: `user` / `admin`.
   Roles come from `configStatus.roles` after config is loaded.
4. **Chat panel** — message list + input. Each message shows:
   - User messages right-aligned
   - Agent responses left-aligned
   - Blocked responses in red with ❌
   - Confirmation prompts in amber with ⚠️ and a "Confirm" button
5. **Gate log panel** — chronological list of all gate decisions from all chat messages.
   Color-coded: green (allow), red (block), amber (confirm), blue (flagged/PII).
   Each entry shows: gate type, decision, tool, role, reason, findings.
6. **Confirmation flow** — when response has `requires_confirmation: true`, show a
   "Confirm Execution" button. Clicking re-sends the same request with `confirmed: true`.

### Step 3: Create `pages/test-agents/python.vue`

```vue
<template>
  <div>
    <TestAgentChat
      :base-url="pythonAgentUrl"
      framework="raw_python"
      title="Pure Python Agent"
    />
  </div>
</template>

<script setup lang="ts">
const config = useRuntimeConfig()
const pythonAgentUrl = config.public.testAgentPythonUrl || 'http://localhost:8003'
</script>
```

### Step 4: Create `pages/test-agents/graph.vue`

```vue
<template>
  <div>
    <TestAgentChat
      :base-url="graphAgentUrl"
      framework="langgraph"
      title="LangGraph Agent"
    />
  </div>
</template>

<script setup lang="ts">
const config = useRuntimeConfig()
const graphAgentUrl = config.public.testAgentGraphUrl || 'http://localhost:8004'
</script>
```

### Step 5: Add navigation

Add sidebar entries to the existing navigation (likely in a layout or nav component):

```
Test Agents
  ├── Python Agent    → /test-agents/python
  └── LangGraph Agent → /test-agents/graph
```

Use a beaker/flask icon to distinguish from the main "Agents" section (which is the wizard).

### Step 6: Add runtime config to `nuxt.config.ts`

```typescript
runtimeConfig: {
  public: {
    apiBase: 'http://localhost:8000',
    agentApiBase: 'http://localhost:8002',
    testAgentPythonUrl: 'http://localhost:8003',   // NEW
    testAgentGraphUrl: 'http://localhost:8004',    // NEW
  }
}
```

---

## UX Flow

### First use (no config loaded):

1. User opens `/test-agents/python`
2. Sees agent selector dropdown → picks "Order Manager" (created in wizard)
3. Clicks "Load Config" → spinner → config loaded indicator turns green
4. Role defaults to "user"
5. Chat input is now enabled

### Chat interactions:

| User types | Role | Expected response | Gate log entry |
|-----------|------|-------------------|----------------|
| "show me orders" | user | JSON with 5 orders | ✅ pre_tool: ALLOW, getOrders |
| "list all users" | user | JSON with 4 users | ✅ pre_tool: ALLOW + 🔎 post_tool: FLAGGED (PII) |
| "search products laptop" | user | JSON with filtered products | ✅ pre_tool: ALLOW, searchProducts |
| "update order ORD-001" | user | ❌ BLOCKED | ❌ pre_tool: BLOCK, RBAC denied |
| "update user USR-001" | user | ❌ BLOCKED | ❌ pre_tool: BLOCK, RBAC denied |
| "update order ORD-001 shipped" | admin | ⚠️ Requires confirmation | ⚠️ pre_tool: CONFIRM |
| [clicks Confirm] | admin | ✅ Order updated | ✅ executed after confirmation |

### Switching agents:

1. User selects a different agent from dropdown
2. Clicks "Load Config" → new RBAC/policy loaded
3. Chat history clears (different security context)
4. Gate log clears
5. New roles appear in role selector

---

## Quick Action Buttons (optional enhancement)

Below the chat input, show preset quick-action buttons for easy testing:

```
[Get Orders] [Get Users] [Search Products] [Update Order ORD-001] [Update User USR-001]
```

Each button pre-fills the message and sends it. This makes testing faster than typing.

---

## Definition of Done

- [ ] `/test-agents/python` page loads and shows agent selector
- [ ] `/test-agents/graph` page loads and shows agent selector
- [ ] Agent dropdown shows only agents matching the page's framework
- [ ] "Load Config" fetches kit from wizard API and loads it into test agent
- [ ] Config status shows loaded roles and policy pack
- [ ] Chat works: user types message, sees response
- [ ] Gate log shows color-coded entries for every interaction
- [ ] RBAC block: user role + write tool → red blocked response + red gate log entry
- [ ] PII detection: getUsers → response shown + blue "flagged" entry in gate log
- [ ] Confirmation flow: admin + write tool → amber prompt → confirm button → success
- [ ] Role switcher changes the role used in chat requests
- [ ] Sidebar has "Test Agents" section with links to both pages
- [ ] Quick action buttons work (if implemented)
