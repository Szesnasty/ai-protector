# Agent Runtime Pipeline — pre/post-tool gating in 11 nodes

The agent runtime implements **three lines of defense** around every tool call:

1. **Pre-tool gate** — blocks unsafe or unauthorized tool calls before execution
2. **Post-tool gate** — sanitizes tool outputs before they reach the LLM
3. **Proxy firewall** — scans the final message set before provider invocation

Built on LangGraph. Every agent request traverses 11 nodes.

---

```
Agent request (user message + role)
  │
  ▼
┌───────────────────────────────────────────────────────────────────┐
│  NODE 1 │ input                                                   │
│                                                                   │
│  • Load session history + sanitize user input                     │
│  • Check limits on entry:                                         │
│    - rate limit (requests / minute, per role)                     │
│    - token budget (cumulative session tokens)                     │
│    - cost cap (session spend)                                     │
│                                                                   │
│  limit_exceeded? → short-circuit to memory (no LLM call)         │
└──────────────────────────────┬────────────────────────────────────┘
                               │ OK
                               ▼
┌───────────────────────────────────────────────────────────────────┐
│  NODE 2 │ intent                                                  │
│                                                                   │
│  Policy-driven intent classification (80+ patterns):              │
│  • role_bypass — is the user trying to escalate privileges?       │
│  • tool_abuse — unauthorized tool invocation attempt?             │
│  • agent_exfiltration — bulk data extraction attempt?             │
│  • social_engineering — trust manipulation attempt?               │
│  • general / qa — legitimate request                              │
│                                                                   │
│  Output: intent label + confidence → written to trace             │
└──────────────────────────────┬────────────────────────────────────┘
                               │
                               ▼
┌───────────────────────────────────────────────────────────────────┐
│  NODE 3 │ policy_check                                            │
│                                                                   │
│  Loads active policy config for this agent / session:             │
│  scanner toggles, risk thresholds, redaction mode, alert rules    │
└──────────────────────────────┬────────────────────────────────────┘
                               │
                               ▼
┌───────────────────────────────────────────────────────────────────┐
│  NODE 4 │ tool_router                                             │
│                                                                   │
│  LLM call (via proxy → firewall) decides which tools are needed.  │
│  Produces tool_plan: [{ "tool": "getOrderStatus", "args": {...} }]│
└──────────────────────────────┬────────────────────────────────────┘
                               │
               ┌───────────────┴────────────────┐
        tool_plan empty                  tool_plan has tools
               │                                │
               │                                ▼
               │         ┌──────────────────────────────────────────────────┐
               │         │  NODE 5 │ pre_tool_gate           LINE OF DEFENSE 1 │
               │         │                                                  │
               │         │  For EACH tool in the plan — 5 checks:          │
               │         │                                                  │
               │         │  ① RBAC                                         │
               │         │    Does role "customer" have permission for      │
               │         │    "issueRefund"? Checks rbac_config.yaml        │
               │         │    (with role inheritance). NO → BLOCK           │
               │         │                                                  │
               │         │  ② Argument schema validation                   │
               │         │    Pydantic model per tool — orderId must match  │
               │         │    /^ORD-\d{3,6}$/, query max 500 chars, etc.   │
               │         │    Schema violation → BLOCK                      │
               │         │                                                  │
               │         │  ③ Injection in arguments                       │
               │         │    14 patterns: "ignore previous instructions",  │
               │         │    "you are now", "jailbreak", "<|im_start|>"…  │
               │         │    Match → BLOCK                                 │
               │         │                                                  │
               │         │  ④ Context risk                                 │
               │         │    Does the conversation suggest an exfiltration │
               │         │    pattern? "dump all records", "bulk export",   │
               │         │    "show all users"… Match → BLOCK               │
               │         │                                                  │
               │         │  ⑤ Limits                                       │
               │         │    Rate limit, token budget, cost cap per role   │
               │         │    Exceeded → BLOCK                              │
               │         │                                                  │
               │         │  Write / sensitive tools: REQUIRES_CONFIRMATION  │
               │         │  → pause graph, ask user to confirm              │
               │         └──────────────────┬───────────────────────────────┘
               │                            │
               │          ┌─────────────────┼───────────────────┐
               │    all blocked     needs confirmation      tools OK
               │          │                 │                   │
               │          │                 ▼                   ▼
               │          │       ┌─────────────────┐  ┌──────────────────────────────┐
               │          │       │  NODE 5a        │  │  NODE 6 │ tool_executor      │
               │          │       │  confirmation   │  │                              │
               │          │       │  _response      │  │  Calls real tools:           │
               │          │       │                 │  │  getOrderStatus              │
               │          │       │  ⚠️ Asks user   │  │  searchKnowledgeBase         │
               │          │       │  to confirm     │  │  issueRefund                 │
               │          │       │  before write   │  │  getInternalSecrets          │
               │          │       │  tool executes  │  │                              │
               │          │       └─────────────────┘  │  raw output → post_tool_gate │
               │          │                            └──────────────┬───────────────┘
               │          │                                           │
               │          │                                           ▼
               │          │          ┌────────────────────────────────────────────────────┐
               │          │          │  NODE 7 │ post_tool_gate      LINE OF DEFENSE 2    │
               │          │          │                                                    │
               │          │          │  For EACH tool result — 4 scans:                  │
               │          │          │                                                    │
               │          │          │  ① PII detection (regex)                          │
               │          │          │    email     → [PII:EMAIL]                        │
               │          │          │    phone     → [PII:PHONE]                        │
               │          │          │    SSN       → [PII:SSN]                          │
               │          │          │    credit card → [PII:CREDIT_CARD]                │
               │          │          │    IBAN, IP address → redacted                    │
               │          │          │                                                    │
               │          │          │  ② Secrets detection (regex)                      │
               │          │          │    sk-...    → [SECRET:REDACTED]                  │
               │          │          │    ghp_...   → [SECRET:REDACTED]                  │
               │          │          │    AKIA...   → [SECRET:REDACTED]                  │
               │          │          │    -----BEGIN RSA... → [SECRET:REDACTED]          │
               │          │          │                                                    │
               │          │          │  ③ Indirect prompt injection                      │
               │          │          │    Did the tool return malicious text that could  │
               │          │          │    hijack the LLM? → BLOCK entire output          │
               │          │          │                                                    │
               │          │          │  ④ Size truncation                                │
               │          │          │    > 4 000 chars → truncate + "[TRUNCATED]"       │
               │          │          │                                                    │
               │          │          │  LLM receives sanitized output — never raw        │
               │          │          └──────────────────┬─────────────────────────────────┘
               │          │                             │
               └──────────┴─────────────────────────────┘
                                                        │ (merges with no-tools path)
                                                        ▼
┌───────────────────────────────────────────────────────────────────┐
│  NODE 8 │ llm_call                       LINE OF DEFENSE 3        │
│                                                                   │
│  Phase 1 — proxy firewall scan:                                   │
│    scan_messages → proxy-service (port 8000)                      │
│    Runs full 9-node proxy pipeline (5 detection layers)           │
│    BLOCK? → return error, never call provider                     │
│                                                                   │
│  Phase 2 — provider call:                                         │
│    full messages → LLM provider (OpenAI / Anthropic / Gemini / …)│
│    sanitized tool outputs included in context                     │
│    message_builder: anti-spoofing delimiters, role separation     │
│                                                                   │
│  Token budget updated after call (cost += response tokens)        │
└──────────────────────────────┬────────────────────────────────────┘
                               │
               ┌───────────────┴────────────┐
          firewall BLOCK                   OK
               │                            │
               │                            ▼
               │               ┌────────────────────────┐
               │               │  NODE 9 │ response      │
               │               │  Format final answer   │
               │               │  for the UI            │
               │               └──────────┬─────────────┘
               │                          │
               └───────────────────────────┘
                                          │
                                          ▼
                         ┌────────────────────────────────┐
                         │  NODE 10 │ memory               │
                         │  Persist session history        │
                         │  Update token / cost counters   │
                         └──────────┬─────────────────────┘
                                    │
                                    ▼
                         ┌────────────────────────────────┐
                         │  NODE 11 │ trace / logging      │
                         │  TraceAccumulator → Langfuse    │
                         │  Records: role, tool calls,     │
                         │  gate decisions, risk scores,   │
                         │  pre/post gate results          │
                         └──────────┬─────────────────────┘
                                    │
                                    ▼
                                Response → UI
```

---

## Three lines of defense

```
Line 1 — pre_tool_gate (BEFORE tool execution)
  "Is the agent allowed to call this tool with these arguments?"
  Blocks: unauthorized access (RBAC), injected args, exceeded limits

Line 2 — post_tool_gate (AFTER tool execution)
  "Is the tool output safe to expose to the LLM?"
  Blocks: PII leakage, secrets in output, indirect prompt injection

Line 3 — proxy firewall (BEFORE LLM provider call)
  "Is the full message set safe to send to the LLM?"
  Runs the complete 9-node proxy pipeline as a backstop
  Catches anything that made it past the agent-level gates
```

---

## Node summary

| # | Node | Defense | What it does |
|---|------|---------|--------------|
| 1 | input | Limits | Rate limit, token budget, cost cap — on entry |
| 2 | intent | Classification | 80+ patterns → intent label (attack / normal) |
| 3 | policy_check | Policy config | Loads thresholds, scanner toggles for this session |
| 4 | tool_router | — | LLM decides which tools are needed |
| 5 | **pre_tool_gate** | **RBAC + validation** | 5 checks before each tool call |
| 5a | confirmation_response | Confirmation | Pauses for human approval (write / sensitive tools) |
| 6 | tool_executor | — | Calls real tool implementations |
| 7 | **post_tool_gate** | **Output sanitization** | PII, secrets, injection, size — on tool output |
| 8 | **llm_call** | **Proxy firewall** | Phase 1: proxy scan; Phase 2: provider call |
| 9 | response | — | Formats final answer |
| 10 | memory | — | Session history, token / cost counters |
| 11 | trace / logging | — | Full audit trail → Langfuse |

---

## What agent runtime does NOT do (proxy firewall handles it)

The pre/post gates do not include:

- LLM Guard ML classifiers (DeBERTa injection, DistilBERT toxicity)
- NeMo Guardrails semantic embeddings
- Presidio spaCy NER
- Full 9-node intent pipeline

These run in the proxy firewall (node 8, phase 1). The proxy acts as a **backstop** — it catches anything that passed the agent-level gates.

The split is intentional:
- Agent gates enforce **authorization logic** (who can call what, with what args)
- Proxy firewall enforces **content safety** (what text is allowed to reach the LLM)

---

## Related

- [Proxy firewall pipeline (9-node)](PROXY_FIREWALL_PIPELINE.md) — the firewall the agent calls in node 8
- [Pre-tool gate source](../../apps/agent-demo/src/agent/nodes/pre_tool_gate.py)
- [Post-tool gate source](../../apps/agent-demo/src/agent/nodes/post_tool_gate.py)
- [Agent graph wiring](../../apps/agent-demo/src/agent/graph.py)
