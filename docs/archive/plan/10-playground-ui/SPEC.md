# Step 10 — Frontend: Playground

| | |
|---|---|
| **Phase** | Firewall Pipeline |
| **Estimated time** | 6–8 hours |
| **Prev** | [Step 09 — Output Pipeline](../09-output-pipeline/SPEC.md) |
| **Next** | [Step 11 — Agent Demo App](../MVP-PLAN.md) |
| **Depends on** | Step 05 (layout, Axios, Vue Query), Steps 06–09 (pipeline API) |
| **Master plan** | [MVP-PLAN.md](../MVP-PLAN.md) |

---

## Goal

Build the **Playground page** — a chat interface for interacting directly with the LLM through the firewall proxy. Users can send prompts, see streaming responses, select a policy level, and inspect the pipeline's decision (intent, risk score, flags) in a debug panel.

This is the **primary demo surface** — the page you show during a pivot conversation or a portfolio walkthrough. It must be polished, responsive, and clearly demonstrate the firewall in action.

---

## Sub-steps

| # | File | Scope | Est. |
|---|------|-------|------|
| a | [10a — Chat Service & Composable](10a-chat-service.md) | `chatService.ts` (Axios + SSE streaming), `useChat` composable (messages, send, loading), pipeline header extraction | 2–3h |
| b | [10b — Chat UI](10b-chat-ui.md) | `pages/playground.vue`, `chat-message-list.vue`, `chat-input.vue` — Vuetify-based chat layout with streaming | 2–3h |
| c | [10c — Config Sidebar & Debug Panel](10c-config-debug.md) | Policy selector, model/temperature controls, debug panel (decision, intent, risk, flags, latency) | 2–2.5h |

---

## Architecture Overview

```
app/
├── pages/
│   └── playground.vue               # Main page — orchestrates layout
├── components/
│   └── playground/
│       ├── chat-message-list.vue     # Scrollable message list (user + assistant)
│       ├── chat-input.vue            # Text input + send button
│       ├── chat-message.vue          # Single message bubble (role-colored)
│       ├── config-sidebar.vue        # Policy, model, temperature controls
│       └── debug-panel.vue           # Pipeline decision breakdown
├── services/
│   ├── chatService.ts                # POST /v1/chat/completions (non-stream + SSE)
│   └── policyService.ts             # GET /v1/policies (for selector dropdown)
├── composables/
│   ├── useChat.ts                    # Message state, send(), streaming logic
│   └── usePolicies.ts               # Vue Query wrapper for policy list
└── types/
    └── api.ts                        # (extended) ChatMessage, PipelineDecision, etc.
```

### Data Flow

```
chat-input.vue
    │  @send(text)
    ▼
useChat composable
    │  chatService.sendMessage(messages, config)
    │  → POST /v1/chat/completions (stream: true)
    │  → Parse SSE chunks → append to assistant message reactively
    │  → Extract x-decision, x-intent, x-risk-score from response headers
    ▼
chat-message-list.vue          debug-panel.vue
(shows streaming text)         (shows decision, intent, risk, flags)
```

---

## Conventions

Same as Step 05:
- `<script setup lang="ts">` — Composition API + TypeScript everywhere
- **Kebab-case** component files and template tags
- **SCSS** — `<style lang="scss" scoped>`
- **services/** — pure async functions (Axios), no Vue reactivity
- **composables/** — wrap services with Vue Query or reactive state

---

## Key API Surface (proxy-service)

### Request
```http
POST /v1/chat/completions
Headers:
  Content-Type: application/json
  x-client-id: playground
  x-policy: balanced           ← selected by user
Body:
  {
    "model": "llama3.1:8b",
    "messages": [{ "role": "user", "content": "..." }],
    "temperature": 0.7,
    "stream": true
  }
```

### Response — ALLOW/MODIFY (streaming)
```
Headers: x-decision: ALLOW, x-intent: qa, x-risk-score: 0.12
Body (SSE):
  data: {"id":"chatcmpl-xxx","choices":[{"delta":{"content":"Hello"}}]}
  data: {"id":"chatcmpl-xxx","choices":[{"delta":{"content":" world"}}]}
  data: [DONE]
```

### Response — BLOCK (403)
```json
{
  "error": { "message": "Prompt injection detected", "type": "policy_violation", "code": "blocked" },
  "decision": "BLOCK",
  "risk_score": 0.92,
  "risk_flags": { "injection": 0.95, "toxicity": 0.1 },
  "intent": "jailbreak"
}
```

---

## Technical Decisions

### Why native `EventSource` / `fetch` for SSE (not Axios)?
Axios doesn't natively support streaming SSE responses. For the `stream: true` path, we use the browser's `fetch()` API with `response.body.getReader()` to read the SSE stream chunk-by-chunk. Axios is still used for non-streaming calls and for other endpoints (policies, health).

### Why `useChat` composable (not Pinia store)?
Chat state is page-scoped — it doesn't need to persist across navigation. A composable with `ref`/`reactive` is simpler and auto-disposes on page unmount. If we later need cross-page chat history, we can upgrade to Pinia.

### Why stream by default?
Streaming gives immediate visual feedback (token-by-token typing effect) and reveals the firewall's pre-LLM decision before any tokens arrive (via response headers). Non-streaming feels sluggish for interactive chat.

### Why extract pipeline data from headers (not a separate API call)?
The proxy already sends `x-decision`, `x-intent`, `x-risk-score` headers on every response (both streaming and non-streaming). For BLOCK responses, the full `risk_flags` and `blocked_reason` are in the JSON body. This avoids an extra round-trip.

---

## Definition of Done (aggregate)

All sub-step DoDs must pass. Quick smoke test:

```bash
cd apps/frontend && npm run dev
# Open http://localhost:3000/playground

# ✅ Chat input visible at bottom, message list fills remaining space
# ✅ Type "What is Python?" → streaming response appears token-by-token
# ✅ Debug panel shows: decision=ALLOW, intent=qa, risk_score≈0.05
# ✅ Type "Ignore all previous instructions" → BLOCK message shown in red
# ✅ Debug panel shows: decision=BLOCK, intent=jailbreak, risk_score≈0.90+
# ✅ Policy selector changes between fast/balanced/strict/paranoid
# ✅ Temperature slider adjusts LLM output
# ✅ Messages scroll automatically on new content
# ✅ Send button disabled while streaming (prevent double-send)
# ✅ All components use <script setup lang="ts">
# ✅ All component files are kebab-case
# ✅ Styles use <style lang="scss" scoped>
# ✅ No TypeScript errors: npx nuxi typecheck
# ✅ No lint errors: npm run lint
```

---

| **Prev** | **Next** |
|---|---|
| [Step 09 — Output Pipeline](../09-output-pipeline/SPEC.md) | Step 11 — Agent Demo App |
