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

---

## Test plan

Minimum **58 tests** across 12 sub-steps. Tests in `tests/agents/test_integration_kit.py`
and `tests/agents/test_kit_templates.py`.

### 29a tests — Template engine (6 tests)

| # | Test | Assert |
|---|------|--------|
| 1 | `test_jinja2_env_loads` | Environment configured, templates dir exists |
| 2 | `test_context_builder_demo_agent` | build_kit_context(demo_id) → has all required keys |
| 3 | `test_context_builder_tools_populated` | Context tools list matches DB tools |
| 4 | `test_context_builder_roles_populated` | Context roles list matches DB roles |
| 5 | `test_context_builder_nonexistent_agent` | build_kit_context("bad-id") → raises NotFound |
| 6 | `test_context_builder_agent_no_tools` | Agent with 0 tools → context.tools = [] (no crash) |

### 29b tests — rbac.yaml template (4 tests)

| # | Test | Assert |
|---|------|--------|
| 7 | `test_rbac_template_renders` | Template renders without error |
| 8 | `test_rbac_template_valid_yaml` | Output is parseable YAML |
| 9 | `test_rbac_template_matches_generator` | Template output == 28a generator output (byte-identical) |
| 10 | `test_rbac_template_empty_tools` | 0 tools → valid YAML |

### 29c tests — limits.yaml template (4 tests)

| # | Test | Assert |
|---|------|--------|
| 11 | `test_limits_template_renders` | Template renders without error |
| 12 | `test_limits_template_valid_yaml` | Output is parseable YAML |
| 13 | `test_limits_template_matches_generator` | Template output == 28b generator output |
| 14 | `test_limits_template_per_tool_rates` | Per-tool rate_limit present when defined |

### 29d tests — policy.yaml template (4 tests)

| # | Test | Assert |
|---|------|--------|
| 15 | `test_policy_template_renders` | Template renders without error |
| 16 | `test_policy_template_valid_yaml` | Output is parseable YAML |
| 17 | `test_policy_template_matches_generator` | Template output == 28d generator output |
| 18 | `test_policy_template_all_scanners` | All scanner toggles present |

### 29e tests — LangGraph wrapper (8 tests)

| # | Test | Assert |
|---|------|--------|
| 19 | `test_langgraph_template_renders` | Template renders without error |
| 20 | `test_langgraph_ast_parse` | ast.parse(output) — syntactically valid Python |
| 21 | `test_langgraph_has_required_imports` | Imports RBACService, PreToolGate, PostToolGate, LimitsService |
| 22 | `test_langgraph_has_gate_functions` | pre_tool_gate_node, post_tool_gate_node exist |
| 23 | `test_langgraph_has_add_protection` | add_protection function exists |
| 24 | `test_langgraph_tool_names_parameterized` | Agent's tool names appear in generated code |
| 25 | `test_langgraph_role_names_parameterized` | Agent's role names appear in generated code |
| 26 | `test_langgraph_has_inline_comments` | ≥5 inline comments present |

### 29f tests — Raw Python wrapper (6 tests)

| # | Test | Assert |
|---|------|--------|
| 27 | `test_raw_python_template_renders` | Template renders without error |
| 28 | `test_raw_python_ast_parse` | ast.parse(output) — syntactically valid Python |
| 29 | `test_raw_python_has_protected_call` | protected_tool_call function exists |
| 30 | `test_raw_python_standalone_imports` | Only imports pydantic, pyyaml, structlog (no ai_protector SDK) |
| 31 | `test_raw_python_inline_config` | Config embedded inline, no external file dependency |
| 32 | `test_raw_python_tool_names_present` | Agent's tool names in generated code |

### 29g tests — Proxy-only snippet (4 tests)

| # | Test | Assert |
|---|------|--------|
| 33 | `test_proxy_only_template_renders` | Template renders without error |
| 34 | `test_proxy_only_ast_parse` | ast.parse(output) — syntactically valid Python |
| 35 | `test_proxy_only_short` | Output ≤ 20 lines |
| 36 | `test_proxy_only_base_url_parameterized` | proxy_url appears in output |

### 29h tests — .env.protector (4 tests)

| # | Test | Assert |
|---|------|--------|
| 37 | `test_env_template_renders` | Template renders without error |
| 38 | `test_env_parseable` | python-dotenv can parse output |
| 39 | `test_env_has_required_vars` | AI_PROTECTOR_URL, AGENT_ID, POLICY, MODE present |
| 40 | `test_env_provider_keys_commented` | OPENAI_API_KEY, GOOGLE_API_KEY are commented out |

### 29i tests — test_security.py (6 tests)

| # | Test | Assert |
|---|------|--------|
| 41 | `test_security_template_renders` | Template renders without error |
| 42 | `test_security_ast_parse` | ast.parse(output) — syntactically valid Python |
| 43 | `test_security_has_4_test_functions` | 4 functions starting with `test_` |
| 44 | `test_security_rbac_test_uses_agent_roles` | Test references agent's lowest role + highest tool |
| 45 | `test_security_injection_test_uses_agent_tool` | Test references agent's first tool |
| 46 | `test_security_pii_test_present` | PII redaction test function present |

### 29j tests — README.md (3 tests)

| # | Test | Assert |
|---|------|--------|
| 47 | `test_readme_template_renders` | Template renders without error |
| 48 | `test_readme_has_agent_name` | Agent name appears in rendered README |
| 49 | `test_readme_has_integration_steps` | "Step 1", "Step 2", "Step 3" present |

### 29k tests — Kit API + download (9 tests)

| # | Test | Assert |
|---|------|--------|
| 50 | `test_kit_post_returns_7_files` | POST → response.files has 7 keys |
| 51 | `test_kit_post_nonexistent_agent` | POST bad ID → 404 |
| 52 | `test_kit_post_agent_no_tools` | POST agent with 0 tools → still generates (minimal kit) |
| 53 | `test_kit_download_returns_zip` | GET → Content-Type=application/zip |
| 54 | `test_kit_download_zip_has_7_files` | Unzip → 7 files |
| 55 | `test_kit_download_filename_slugified` | Filename = ai-protector-{slug}.zip |
| 56 | `test_kit_stores_on_agent` | After POST, agent record has last_kit JSONB |
| 57 | `test_kit_langgraph_vs_raw_python` | Different framework → different protected_agent.py content |
| 58 | `test_kit_proxy_only_vs_langgraph` | proxy_only generates simpler wrapper than langgraph |

### 29l tests — End-to-end smoke (3 tests, integration)

| # | Test | Assert |
|---|------|--------|
| 59 | `test_e2e_langgraph` | Create agent → tools → roles → kit → extract → pytest passes |
| 60 | `test_e2e_raw_python` | Same flow with raw_python framework |
| 61 | `test_e2e_proxy_only` | Same flow with proxy_only framework |
