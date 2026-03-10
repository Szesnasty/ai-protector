# Step 29 — Integration Kit Generator

**Prereqs:** Step 28 (Config Generation)
**Spec ref:** agents-v1.spec.md → Req 4
**Effort:** 3–4 days (⚠️ highest risk item — the heart of the product)
**Output:** Template-based generation of 7 deployment-ready files

---

## Why this is the hardest step

This is the moment the user decides: "does this actually work?"

The integration kit is not a preview — it's **real files** that go into
a real repo, run real tests, and protect a real agent. If
`pytest test_security.py` fails after extraction, the product has failed.

**Design constraints:**
- Template-based parameter substitution (Jinja2) — NOT LLM code generation
- Same inputs → always same outputs (deterministyczny)
- Max 7 files — no more
- v1 scope: LangGraph wrapper, raw Python wrapper, proxy-only snippet

---

## Sub-steps

### 29a — Template engine setup

Jinja2 templates stored in `apps/proxy-service/src/templates/kit/`.

Template context (filled from DB):

```python
{
    "agent_name": "Customer Support Copilot",
    "agent_id": "abc-123",
    "framework": "langgraph",           # langgraph | raw_python | proxy_only
    "tools": [...],                      # from agent_tools
    "roles": [...],                      # from agent_roles
    "policy_pack": "customer_support",   # selected pack name
    "pack_config": {...},                # pack thresholds
    "proxy_url": "http://localhost:8000",
    "generated_at": "2026-03-10T14:30:00Z",
}
```

**DoD:**
- [ ] Jinja2 environment configured with template directory
- [ ] Context builder: `build_kit_context(agent_id)` → dict from DB
- [ ] Templates can access all context variables
- [ ] Tests: context builder returns expected structure for demo agent

### 29b — Template: rbac.yaml

Template: `templates/kit/rbac.yaml.j2`
Same output as step 28a but from Jinja2 template.

**DoD:**
- [ ] Template produces valid rbac.yaml identical to 28a generator
- [ ] Tests: render template → compare against direct generator output

### 29c — Template: limits.yaml

Template: `templates/kit/limits.yaml.j2`

**DoD:**
- [ ] Template produces valid limits.yaml identical to 28b generator
- [ ] Per-tool rate limits included when defined

### 29d — Template: policy.yaml

Template: `templates/kit/policy.yaml.j2`

**DoD:**
- [ ] Template produces valid policy.yaml identical to 28d generator
- [ ] Pack-specific values correctly substituted

### 29e — Template: protected_agent.py (LangGraph)

Template: `templates/kit/langgraph_protection.py.j2`

Generated code includes:
- Import of `RBACService`, `PreToolGate`, `PostToolGate`, `LimitsService`
- Init from generated config paths
- `pre_tool_gate_node(state)` — parameterized with agent's tools/roles
- `post_tool_gate_node(state)` — parameterized with scanner toggles
- `add_protection(graph)` — adds gate nodes to user's graph

**DoD:**
- [ ] Generated Python file is syntactically valid
- [ ] Parameterized with agent's tool list and role names
- [ ] Includes inline comments explaining each section
- [ ] Tests: render → `ast.parse()` succeeds → function names exist

### 29f — Template: protected_agent.py (raw Python)

Template: `templates/kit/raw_python_protection.py.j2`

Generated code includes:
- `protected_tool_call(role, tool, args)` — single-function wrapper
- RBAC check → arg validation → execute → post-tool scan
- Inline config (no external file dependency for simplest use case)

**DoD:**
- [ ] Generated Python file is syntactically valid
- [ ] Works standalone with `pydantic`, `pyyaml`, `structlog` only
- [ ] Tests: render → `ast.parse()` succeeds

### 29g — Template: protected_agent.py (proxy-only)

Template: `templates/kit/proxy_only.py.j2`

Minimal — just shows the base_url change:

```python
# AI Protector — Proxy-only integration
# Agent: {{ agent_name }}
# No SDK required — just change the base URL.

from openai import OpenAI

client = OpenAI(
    base_url="{{ proxy_url }}/v1",
    api_key="your-api-key",  # passed through to provider
)
```

**DoD:**
- [ ] 10-line snippet, syntactically valid
- [ ] Proxy URL parameterized

### 29h — Template: .env.protector

Template: `templates/kit/env.protector.j2`

```dotenv
# AI Protector config for: {{ agent_name }}
AI_PROTECTOR_URL={{ proxy_url }}
AI_PROTECTOR_POLICY={{ policy_pack }}
AI_PROTECTOR_AGENT_ID={{ agent_id }}
AI_PROTECTOR_MODE=observe
# Add your LLM provider API key:
# OPENAI_API_KEY=sk-...
# GOOGLE_API_KEY=...
```

**DoD:**
- [ ] All required env vars present
- [ ] Provider-specific vars commented out with hints
- [ ] Tests: render → dotenv parseable

### 29i — Template: test_security.py

Template: `templates/kit/test_security.py.j2`

4 smoke tests parameterized with agent's config:

1. **RBAC block:** lowest role tries highest-sensitivity tool → DENY
2. **Injection block:** SQL injection in tool args → BLOCKED
3. **PII redact:** tool output with email/phone → REDACTED
4. **Confirmation trigger:** write+critical tool → requires approval

```python
def test_rbac_block():
    """{{ roles[0].name }} must not access {{ tools[-1].name }}."""
    result = rbac.check_permission("{{ roles[0].name }}", "{{ tools[-1].name }}")
    assert not result.allowed

def test_injection_blocked():
    """Injection in {{ tools[0].name }} args must be blocked."""
    ...
```

**DoD:**
- [ ] 4 tests, all parameterized from agent config
- [ ] Tests are runnable with `pytest` after extraction
- [ ] Tests import from generated `protected_agent.py`
- [ ] Tests: render → `ast.parse()` succeeds → 4 test functions present

### 29j — Template: README.md

Template: `templates/kit/README.md.j2`

Includes:
- Agent name + description
- Protection level + policy pack
- File list with what each file does
- Integration steps (3 steps)
- How to run tests
- How to switch rollout modes

**DoD:**
- [ ] Renders with correct agent info
- [ ] Steps are numbered and actionable

### 29k — Kit generation API + download

```
POST /agents/:id/integration-kit
→ {
    files: {
      "rbac.yaml": "...",
      "limits.yaml": "...",
      "policy.yaml": "...",
      "protected_agent.py": "...",
      ".env.protector": "...",
      "test_security.py": "...",
      "README.md": "..."
    },
    framework: "langgraph",
    generated_at: "2026-03-10T14:30:00Z"
  }

GET /agents/:id/integration-kit/download
→ ai-protector-kit.zip (7 files)
```

**DoD:**
- [ ] POST returns all 7 files as strings (for UI preview)
- [ ] GET returns .zip with all 7 files
- [ ] Zip filename: `ai-protector-{agent_name_slugified}.zip`
- [ ] Stores last generated kit on agent record
- [ ] Tests: generate → download → unzip → 7 files → `pytest test_security.py` passes
- [ ] Tests: different framework → different `protected_agent.py` content

### 29l — End-to-end smoke test

The ultimate acceptance test:

```
1. Create agent via API
2. Register 3 tools, 2 roles
3. Generate integration kit
4. Extract .zip to temp directory
5. Run `pytest test_security.py` from extracted dir
6. All 4 tests pass
```

**DoD:**
- [ ] This test exists and passes in CI
- [ ] Runs for each framework (langgraph, raw_python, proxy_only)
