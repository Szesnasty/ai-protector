# Agent Wizard Go-Live — Master Plan

> **Goal:** After completing all steps, you can create an agent in the wizard UI,
> generate an integration kit, and immediately test it in two dedicated agent tabs
> (Pure Python + LangGraph) with real security enforcement.

## Current Status

| Layer | Status | Notes |
|-------|--------|-------|
| Backend wizard (7 routers, 9 services) | ✅ Complete | Spec 26–32 |
| Frontend wizard (7 steps + detail page) | ✅ Complete | Spec 33 |
| Backend tests (~410+) | ✅ Passing | 8 test files |
| Policy packs (5 presets) | ✅ | customer_support, internal_copilot, finance, hr, research |
| Kit generation (7 Jinja2 templates) | ✅ | LangGraph + Raw Python + Proxy Only |
| DB migrations (aw_001–005) | ⚠️ Incomplete | Missing migrations for traces/incidents/gate/promotion |

## What's Missing

1. **Missing Alembic migrations** — traces, incidents, gate decisions, promotion events
2. **Pure Python test agent** — service that loads the generated kit and exposes a chat endpoint
3. **LangGraph test agent** — same as above, but with a full LangGraph StateGraph
4. **Config loader** — mechanism to fetch the integration kit from the wizard API at runtime
5. **Docker compose** — two additional services for the test agents
6. **Frontend** — 2 tabs in the UI with chat and role selection
7. **E2E verification** — full flow: wizard → agent → chat

## Target Flow

```
┌─────────────────────────────────────────────────────┐
│  WIZARD (/agents/new)                               │
│  1. Describe → 2. Tools → 3. Roles → 4. Security   │
│  5. Kit → 6. Validate → 7. Deploy                   │
└──────────────────────┬──────────────────────────────┘
                       │ Generate Kit (7 files)
                       ▼
┌─────────────────────────────────────────────────────┐
│  TEST AGENTS                                        │
│  /test-agents/python    → Pure Python (port 8003)   │
│  /test-agents/langgraph → LangGraph   (port 8004)   │
│                                                     │
│  [Select Agent] [Load Config] [Role: user ▼]        │
│  ┌─────────────────────────────────────────────┐    │
│  │ Chat:                                       │    │
│  │ > Show me all orders                        │    │
│  │ ✅ getOrders → [order list]                  │    │
│  │ > Update order ORD-001 status to shipped    │    │
│  │ ❌ BLOCKED: Role 'user' cannot use          │    │
│  │    'updateOrder' (write, high sensitivity)  │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

## 5 Tools × 2 Roles

| Tool | Access | Sensitivity | user | admin |
|------|--------|-------------|------|-------|
| `getOrders` | read | low | ✅ | ✅ |
| `getUsers` | read | medium (PII) | ✅ | ✅ |
| `searchProducts` | read | low | ✅ | ✅ |
| `updateOrder` | write | high | ❌ | ✅ (confirm) |
| `updateUser` | write | high | ❌ | ✅ (confirm) |

## Implementation Steps

| # | File | Description | Effort |
|---|------|-------------|--------|
| 01 | [01-fix-missing-migrations.md](01-fix-missing-migrations.md) | Missing Alembic migrations | 1h |
| 02 | [02-shared-mock-tools.md](02-shared-mock-tools.md) | Shared mock tools, test data + LLM tool definitions | 1.5h |
| 03 | [03-pure-python-test-agent.md](03-pure-python-test-agent.md) | Pure Python test agent with mock/LLM toggle (port 8003) | 4h |
| 04 | [04-langgraph-test-agent.md](04-langgraph-test-agent.md) | LangGraph test agent with mock/LLM toggle (port 8004) | 4h |
| 05 | [05-docker-and-infra.md](05-docker-and-infra.md) | Docker compose for test agents | 1h |
| 06 | [06-frontend-test-pages.md](06-frontend-test-pages.md) | Two test UI pages with chat, role selection + LLM settings | 4h |
| 07 | [07-e2e-verification.md](07-e2e-verification.md) | E2E test of the full flow (both modes) | 2h |

**Total effort:** ~17.5h (~2.5 focused workdays)

**Execution order:** 01 → 02 → 03+04 (parallel) → 05 → 06 → 07

---

## Module Architecture

Each piece is a **self-contained, independently deployable module**:

```
apps/
  proxy-service/          ← Existing — wizard API + security pipeline (port 8000)
  frontend/               ← Existing — wizard UI + test-agent pages (port 3000)
  test-agents/
    shared/               ← NEW — shared mock data & tool functions (library, no port)
    pure-python-agent/    ← NEW — standalone FastAPI service (port 8003)
    langgraph-agent/      ← NEW — standalone FastAPI service (port 8004)
```

**Key characteristics:**
- Each agent is a **separate FastAPI app** with its own `Dockerfile` and `pyproject.toml`
- Agents have **zero hard dependencies** on each other — you can run only one, or both
- Agents fetch their security config from the wizard API at runtime (`POST /load-config`)
- The `shared/` module is a plain Python package imported by both agents
- Docker Compose `profiles: [test-agents]` keeps them opt-in — they don't start unless you ask

## LLM Mode: Mock vs Real Agent (Toggle in UI)

Each test agent supports **two operating modes**, selectable via a toggle in the UI:

### Mode A: Mock (keyword-based) — no API key needed

```
User message → keyword router → pre_gate → tool → post_gate → raw JSON
```

- Deterministic, always the same result for the same input
- Great for CI, automated testing, security gate validation
- Zero cost, zero latency
- Tool selection by simple keyword matching ("orders" → `getOrders`)

### Mode B: Real LLM Agent — full function-calling pipeline

```
User message → LLM (with tool definitions) → LLM picks tool + args
            → pre_gate → tool → post_gate → LLM formats response
```

- LLM receives tool definitions in **native function-calling format** (OpenAI tools / Anthropic tool_use)
- LLM **decides on its own** which tool to call and what arguments to pass
- After security gates + tool execution, the result goes back to the LLM for natural language formatting
- This is a **real agent** — it reasons, it can refuse, it can chain tools

### Why both modes?

| Aspect | Mock | Real LLM |
|--------|------|----------|
| Purpose | Validate security gates deterministically | Test full agent behavior with reasoning |
| API key | Not needed | Required (or local Ollama) |
| Cost | $0 | Per-token cost |
| Reproducibility | 100% deterministic | Non-deterministic |
| CI-friendly | ✅ | ❌ (needs key + network) |
| Edge cases tested | Known tool selection | LLM hallucinating tools, ambiguous requests, multi-tool reasoning |

### Supported Models (via LiteLLM — already in codebase)

The existing `proxy-service/src/llm/providers.py` already has a model catalog.
The **model dropdown in the UI is filtered dynamically** — only models whose API key
has been configured in Settings are shown. Ollama models are always available if
the Ollama service is reachable.

| Provider | Models | Env var / Settings key | Auto-detected |
|----------|--------|----------------------|---------------|
| **Ollama** (local) | llama3.1:8b, codellama, mistral | None (Ollama URL) | ✅ if Ollama reachable |
| **OpenAI** | gpt-4o, gpt-4o-mini, o3-mini | `OPENAI_API_KEY` | ✅ if key set |
| **Anthropic** | claude-sonnet-4-6, claude-haiku-4-5 | `ANTHROPIC_API_KEY` | ✅ if key set |
| **Google** | gemini-2.5-pro, gemini-2.5-flash | `GOOGLE_API_KEY` | ✅ if key set |
| **Mistral** | mistral-large, mistral-small | `MISTRAL_API_KEY` | ✅ if key set |

**Settings panel** (stored in browser localStorage, never sent to server for storage):
```
┌─ LLM Settings ──────────────────────────────────────────────┐
│                                                              │
│  OpenAI API Key:     [sk-••••••••••••••••]  ✅ configured   │
│  Anthropic API Key:  [                    ]  ⬚ not set      │
│  Google API Key:     [                    ]  ⬚ not set      │
│  Mistral API Key:    [                    ]  ⬚ not set      │
│  Ollama URL:         [http://localhost:11434]  ✅ reachable  │
│                                                              │
│  Available models: gpt-4o, gpt-4o-mini, o3-mini,            │
│                    llama3.1:8b, codellama, mistral            │
└──────────────────────────────────────────────────────────────┘
```

When the user selects "Real LLM" mode, the model dropdown only shows models
from providers with a configured API key. The key is sent **per-request** in
the chat payload — the backend never persists it.

### How it works technically

Both test agents expose a single `/chat` endpoint. The `mode` field controls behavior:

```python
class ChatRequest(BaseModel):
    message: str
    role: str = "user"
    mode: Literal["mock", "llm"] = "mock"   # ← the toggle
    model: str = "gpt-4o-mini"               # ← only used when mode=llm
    api_key: str | None = None               # ← passed per-request from frontend
    confirmed: bool = False
```

In **LLM mode**, the agent sends native tool definitions to the LLM:

```python
# OpenAI function-calling format (LiteLLM handles the conversion for all providers)
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "getOrders",
            "description": "List all customer orders with status and amounts.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "getUsers",
            "description": "List all users. Returns PII (emails, phone numbers).",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "searchProducts",
            "description": "Search products by name or category.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "Search query"}},
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "updateOrder",
            "description": "Update an order's status. Requires admin role.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "status": {"type": "string", "enum": ["pending", "processing", "shipped", "delivered", "cancelled"]}
                },
                "required": ["order_id", "status"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "updateUser",
            "description": "Update a user's profile information. Requires admin role.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "name": {"type": "string"},
                    "email": {"type": "string"}
                },
                "required": ["user_id"]
            }
        }
    },
]
```

The LLM call flow for Real mode:

```python
# 1. LLM decides which tool to call
response = await litellm.acompletion(
    model=request.model,
    messages=[system_prompt, *chat_history, user_message],
    tools=TOOL_DEFINITIONS,          # ← native function calling
    tool_choice="auto",              # ← LLM decides freely
    api_key=request.api_key,
)

# 2. Parse tool_calls from LLM response
tool_call = response.choices[0].message.tool_calls[0]
tool_name = tool_call.function.name
tool_args = json.loads(tool_call.function.arguments)

# 3. Security gates (SAME as mock mode — this is the critical part)
pre_gate_result = pre_tool_gate.check(role, tool_name, tool_args)
if not pre_gate_result["allowed"]:
    return blocked_response(pre_gate_result)

# 4. Execute tool
tool_output = execute_tool(tool_name, tool_args)

# 5. Post-tool scan (PII, injection)
post_result = post_tool_gate.scan(tool_output)

# 6. Send tool result back to LLM for natural language formatting
final = await litellm.acompletion(
    model=request.model,
    messages=[*messages, tool_call_message, tool_result_message],
    api_key=request.api_key,
)
return final.choices[0].message.content
```

### What this tests that mock mode cannot

1. **LLM tries to call a tool that doesn't exist** → pre_gate blocks it (tool not in RBAC)
2. **LLM sends wrong arguments** → tool execution fails gracefully
3. **LLM tries to bypass RBAC** (e.g., calls `updateOrder` when told it shouldn't) → pre_gate blocks
4. **LLM reformulates PII** from tool output → post_gate may or may not catch it (real test!)
5. **LLM chains multiple tools** in one turn → each goes through security gates
6. **Ambiguous user requests** → LLM picks the best tool, security verifies the choice

### Frontend UI for the toggle

```
┌─────────────────────────────────────────────────────────────┐
│  Test Agent: Pure Python                                    │
│                                                             │
│  ┌─────────────┐  ┌──────────────────┐  ┌───────────────┐  │
│  │ Role: user ▼│  │ Mode: ● Mock     │  │ Agent: [v] ▼  │  │
│  │             │  │       ○ Real LLM  │  │               │  │
│  └─────────────┘  └──────────────────┘  └───────────────┘  │
│                                                             │
│  ┌─ When Real LLM selected: ─────────────────────────────┐  │
│  │  Model: [gpt-4o-mini ▼]  API Key: [••••••••••] 🔑     │  │
│  │  ℹ️  Key is kept in browser only, never stored server   │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─ Chat ────────────────────────────────────────────────┐  │
│  │ ...                                                   │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─ Security Gate Log ───────────────────────────────────┐  │
│  │ ...                                                   │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Impact on effort estimate

| Step | Original | New (with LLM mode) | Delta |
|------|----------|---------------------|-------|
| 02 — Shared tools | 1h | 1.5h | +0.5h (add TOOL_DEFINITIONS + system prompt) |
| 03 — Pure Python agent | 3h | 4h | +1h (add LLM call path) |
| 04 — LangGraph agent | 3h | 4h | +1h (add llm_router node) |
| 06 — Frontend | 3h | 4h | +1h (toggle, model dropdown, API key input) |

**New total: ~17.5h (~2.5 focused workdays)** (was ~14h)
