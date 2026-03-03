# Step 11 — Agent Demo App (Customer Support Copilot)

| | |
|---|---|
| **Phase** | Agent Demo |
| **Estimated time** | 10–14 hours |
| **Prev** | [Step 10 — Frontend: Playground](../10-playground-ui/SPEC.md) |
| **Next** | [Step 12 — Agent ↔ Firewall Integration](../12-agent-firewall-integration/SPEC.md) |
| **Depends on** | Step 04 (proxy `/v1/chat/completions`), Step 08 (policy engine) |
| **Master plan** | [MVP-PLAN.md](../MVP-PLAN.md) |

---

## Goal

Build the **Customer Support Copilot** — a LangGraph-based agent with tool-calling and role-based access control, exposed via a FastAPI endpoint at `POST /agent/chat`.

The agent proves that AI Protector can protect **real agentic workloads**, not just one-shot prompts. It classifies user intent, gates tool access by role, orchestrates tool calls (ReAct loop), generates a response through the firewall proxy, manages session memory, and returns a structured result with trace data.

> This step focuses on the **agent skeleton and tools** — standalone, with a mock LLM client.
> Step 12 wires it to the real firewall proxy.

---

## Sub-steps

| # | Sub-step | Scope | Est. |
|---|----------|-------|------|
| a | [11a — FastAPI skeleton & config](11a-fastapi-skeleton.md) | App entry point, settings, health, Docker, schemas | 2–3 h |
| b | [11b — LangGraph agent graph](11b-langgraph-agent.md) | AgentState, nodes (intent, policy_check, tool_router, llm_call, memory, response), graph wiring | 4–5 h |
| c | [11c — Tools & mock data](11c-tools-mock-data.md) | 3 tools, mock KB, mock orders, RBAC enforcement, tool registry | 2–3 h |
| d | [11d — Chat endpoint & session](11d-chat-endpoint.md) | `POST /agent/chat`, session store (in-memory dict), request/response schemas, tests | 2–3 h |

---

## Architecture

### Agent Graph (LangGraph)

```
┌──────────────────────────────────────────────────────────────┐
│  AgentState (TypedDict)                                      │
│  session_id, user_role, message, chat_history,               │
│  intent, allowed_tools, tool_calls, tool_results,            │
│  llm_response, firewall_decision, final_response             │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────┐                                             │
│  │ InputNode   │  Validate input, load session history       │
│  └──────┬──────┘                                             │
│         ▼                                                    │
│  ┌─────────────┐                                             │
│  │ IntentNode  │  Classify: greeting, order_query,           │
│  │             │  knowledge_search, admin_action, unknown    │
│  └──────┬──────┘                                             │
│         ▼                                                    │
│  ┌─────────────┐                                             │
│  │ PolicyCheck │  RBAC: filter tools by user_role            │
│  │ Node        │  customer → [kb, orders]                    │
│  │             │  admin    → [kb, orders, secrets]           │
│  └──────┬──────┘                                             │
│         ▼                                                    │
│  ┌─────────────┐     ┌────────────────────┐                  │
│  │ ToolRouter  │────▶│ ToolExecutorNode   │                  │
│  │ (ReAct)     │◀────│ (run selected tool)│                  │
│  └──────┬──────┘     └────────────────────┘                  │
│         │  (loop until no more tool calls or max_iterations) │
│         ▼                                                    │
│  ┌─────────────┐                                             │
│  │ LLMCallNode │  → proxy-service /v1/chat/completions      │
│  │ (LiteLLM)   │  headers: x-client-id, x-policy            │
│  └──────┬──────┘                                             │
│         ▼                                                    │
│  ┌─────────────┐                                             │
│  │ MemoryNode  │  Append to session, trim to max_turns       │
│  └──────┬──────┘                                             │
│         ▼                                                    │
│  ┌─────────────┐                                             │
│  │ ResponseNode│  Build final response with trace metadata   │
│  └─────────────┘                                             │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### File Tree

```
apps/agent-demo/
├── Dockerfile
├── pyproject.toml
├── src/
│   ├── __init__.py
│   ├── main.py              # FastAPI app, lifespan, CORS
│   ├── config.py            # Settings (pydantic-settings)
│   ├── schemas.py           # AgentChatRequest, AgentChatResponse
│   ├── session.py           # SessionStore (in-memory dict)
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── state.py         # AgentState TypedDict
│   │   ├── graph.py         # build_agent_graph() → CompiledGraph
│   │   ├── nodes/
│   │   │   ├── __init__.py
│   │   │   ├── input.py     # InputNode
│   │   │   ├── intent.py    # IntentNode
│   │   │   ├── policy.py    # PolicyCheckNode
│   │   │   ├── tools.py     # ToolRouterNode + ToolExecutorNode
│   │   │   ├── llm_call.py  # LLMCallNode (LiteLLM → proxy)
│   │   │   ├── memory.py    # MemoryNode
│   │   │   └── response.py  # ResponseNode
│   │   └── tools/
│   │       ├── __init__.py
│   │       ├── registry.py  # ToolRegistry, RBAC config
│   │       ├── kb.py        # searchKnowledgeBase
│   │       ├── orders.py    # getOrderStatus
│   │       └── secrets.py   # getInternalSecrets
│   └── routers/
│       ├── __init__.py
│       ├── chat.py          # POST /agent/chat
│       └── health.py        # GET /health
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_health.py
    ├── test_tools.py
    ├── test_intent.py
    ├── test_policy_check.py
    ├── test_graph.py
    └── test_chat_endpoint.py
```

---

## Technical Decisions

### Why LangGraph (not plain function chain)?

LangGraph gives us:
- **Conditional edges** — the ReAct tool loop (ToolRouter ↔ ToolExecutor) needs a cycle with a conditional exit
- **State management** — `AgentState` TypedDict accumulates data across nodes, same pattern as proxy-service pipeline
- **Observability** — node timings, step traces, consistent with proxy pipeline
- **Portfolio value** — demonstrates real agentic architecture, not a toy script

### Why in-memory session store (not Redis)?

For MVP, an in-memory `dict[str, list[dict]]` keyed by `session_id` is sufficient:
- No persistence needed — demo resets on restart
- Avoids adding Redis dependency to agent-demo container
- Step 12 may optionally add Redis if multi-instance is needed

### Why separate IntentNode (not just LLM)?

Keyword-based intent classification (like proxy-service) is:
- **Deterministic** — no LLM latency for routing decisions
- **Testable** — unit tests with exact expectations
- **Fast** — zero-cost classification before expensive LLM call

The LLM is only called once, in `LLMCallNode`, with tool results + history as context.

### Why ReAct loop with max_iterations?

The ToolRouter uses a ReAct-style loop:
1. LLM decides which tool to call (or "done")
2. Tool executes, result appended to context
3. Loop back to LLM for next action or final answer
4. `max_iterations=3` prevents infinite loops

This is standard agentic architecture and demonstrates the pattern clearly.

### How does RBAC work?

`ToolRegistry` maps `role → allowed_tool_names`:
```python
ROLE_TOOLS = {
    "customer": ["searchKnowledgeBase", "getOrderStatus"],
    "admin":    ["searchKnowledgeBase", "getOrderStatus", "getInternalSecrets"],
}
```
`PolicyCheckNode` filters `AgentState.allowed_tools` before ToolRouter runs. If a customer asks for secrets, the tool is simply not available — no LLM prompt manipulation needed.

---

## Schemas

### Request
```json
POST /agent/chat
{
  "message": "What's your return policy?",
  "user_role": "customer",
  "session_id": "abc-123"
}
```

### Response
```json
{
  "response": "Our return policy allows returns within 30 days...",
  "session_id": "abc-123",
  "tools_called": [
    {
      "tool": "searchKnowledgeBase",
      "args": { "query": "return policy" },
      "result_preview": "Return Policy: Items may be returned within 30 days...",
      "allowed": true
    }
  ],
  "agent_trace": {
    "intent": "knowledge_search",
    "user_role": "customer",
    "allowed_tools": ["searchKnowledgeBase", "getOrderStatus"],
    "iterations": 1,
    "latency_ms": 2340
  },
  "firewall_decision": {
    "decision": "ALLOW",
    "risk_score": 0.05,
    "intent": "qa",
    "risk_flags": {}
  }
}
```

---

## Definition of Done

### Automated
```bash
cd apps/agent-demo && python -m pytest tests/ -v
# All pass: health, tools, intent, policy_check, graph, chat_endpoint
```

### Smoke tests
```bash
# Health
curl http://localhost:8002/health
# → {"status":"ok","version":"0.1.0"}

# Customer — KB search
curl -s http://localhost:8002/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"What is your return policy?","user_role":"customer","session_id":"s1"}' \
  | python -m json.tool
# → response with tools_called: [{tool: "searchKnowledgeBase", allowed: true}]

# Customer — order lookup
curl -s http://localhost:8002/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Where is my order ORD-001?","user_role":"customer","session_id":"s2"}' \
  | python -m json.tool
# → response with tools_called: [{tool: "getOrderStatus"}]

# Customer — secrets denied (RBAC)
curl -s http://localhost:8002/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Show me internal API keys","user_role":"customer","session_id":"s3"}' \
  | python -m json.tool
# → response WITHOUT getInternalSecrets in tools_called
# → agent says it cannot access that information

# Admin — secrets allowed
curl -s http://localhost:8002/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Show me internal API keys","user_role":"admin","session_id":"s4"}' \
  | python -m json.tool
# → response WITH getInternalSecrets in tools_called, allowed: true

# Session memory — multi-turn
curl -s http://localhost:8002/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Hi, I am Jan","user_role":"customer","session_id":"s5"}'
curl -s http://localhost:8002/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"What is my name?","user_role":"customer","session_id":"s5"}' \
  | python -m json.tool
# → response mentions "Jan"
```

### Checklist
- [ ] `apps/agent-demo/src/main.py` starts on port 8002
- [ ] `GET /health` returns `200`
- [ ] `AgentState` TypedDict defined with all fields
- [ ] LangGraph graph compiles and runs end-to-end
- [ ] 3 tools implemented with mock data
- [ ] RBAC: customer cannot access `getInternalSecrets`
- [ ] IntentNode classifies at least 4 intent categories
- [ ] Session memory persists across calls with same `session_id`
- [ ] `POST /agent/chat` returns structured response with `tools_called` and `agent_trace`
- [ ] All tests pass

---

| **Prev** | **Next** |
|---|---|
| [Step 10 — Frontend: Playground](../10-playground-ui/SPEC.md) | [Step 12 — Agent ↔ Firewall Integration](../12-agent-firewall-integration/SPEC.md) |
