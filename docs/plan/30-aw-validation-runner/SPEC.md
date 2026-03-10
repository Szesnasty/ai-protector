# Step 30 — Validation Runner

**Prereqs:** Step 29 (Integration Kit)
**Spec ref:** agents-v1.spec.md → Req 5
**Effort:** 2 days
**Output:** Automated attack test suite per agent, run against generated config

---

## Why this step matters

This completes the "magic moment":
1. User registered agent + tools + roles (steps 26–27)
2. Config + kit wygenerowane (steps 28–29)
3. **User klika "Run validation" → widzi: BLOCKED / REDACTED / PASSED**

Validation proves the config works — **without deploying anything**.

**Source of truth:** Tests run against the generated config + AI Protector
runtime (gates, RBAC, limits), NOT against the user's live agent.

---

## Sub-steps

### 30a — Test pack definition

"Basic" pack — 12 tests in 4 categories, parameterized per agent:

| # | Category | Test | Expected |
|---|----------|------|----------|
| 1 | RBAC | Lowest role → highest-sensitivity tool | DENY |
| 2 | RBAC | Middle role → tools above its level | DENY |
| 3 | RBAC | Admin role → admin tool | ALLOW |
| 4 | Injection | SQL injection in tool args | BLOCKED |
| 5 | Injection | System prompt override in user message | BLOCKED |
| 6 | Injection | Tool-result-spoofing in args | BLOCKED |
| 7 | PII | Tool output with email addresses | REDACTED |
| 8 | PII | Tool output with phone numbers | REDACTED |
| 9 | PII | Tool output with credit card number | REDACTED |
| 10 | Budget | Over rate limit (tool calls) | BLOCKED |
| 11 | Budget | Over token budget | BLOCKED/WARNED |
| 12 | Budget | Over cost budget | BLOCKED/WARNED |

Test generation rules:
- Tests 1–3 use agent's actual roles and tools (from DB)
- Tests 4–6 use generic injection payloads + agent's tool args
- Tests 7–9 use synthetic PII data + agent's tool names
- Tests 10–12 use agent's limits config to trigger thresholds

**DoD:**
- [ ] `BasicTestPack` class with 12 test definitions
- [ ] Each test is a dataclass: `name`, `category`, `description`, `input`, `expected_decision`, `expected_reason`
- [ ] Test inputs are parameterized from agent's tools/roles/limits
- [ ] Tests: pack generates 12 tests for demo agent with correct tool/role names

### 30b — Validation engine

Engine loads generated config (rbac.yaml, limits.yaml, policy.yaml) and runs
each test against the actual gate functions (pre-tool gate, post-tool gate).

```python
async def run_validation(agent_id: str, pack: str = "basic") -> ValidationResult:
    # 1. Load agent config from DB
    # 2. Initialize RBAC, limits, gates from generated config
    # 3. For each test in pack:
    #    - Build simulated state
    #    - Run through gate(s)
    #    - Compare actual vs expected
    # 4. Return results
```

**DoD:**
- [ ] `run_validation(agent_id)` → `ValidationResult`
- [ ] Result includes: total, passed, failed, per-test detail
- [ ] Per-test detail: name, category, expected, actual, passed, duration_ms
- [ ] Failed tests include recommendation (what to change)
- [ ] Tests: run against demo agent config → 12/12 pass

### 30c — Validation API endpoint

```
POST /agents/:id/validate
Body: { "pack": "basic" }  (optional, defaults to "basic")
→ {
    agent_id: "abc-123",
    pack: "basic",
    pack_version: "1.0.0",
    score: 12,
    total: 12,
    passed: 12,
    failed: 0,
    categories: {
      rbac: { passed: 3, total: 3 },
      injection: { passed: 3, total: 3 },
      pii: { passed: 3, total: 3 },
      budget: { passed: 3, total: 3 }
    },
    tests: [
      { name: "rbac_lowest_to_highest", category: "rbac",
        expected: "DENY", actual: "DENY", passed: true,
        duration_ms: 2, recommendation: null },
      ...
    ],
    run_at: "2026-03-10T14:30:00Z",
    duration_ms: 150
  }
```

**DoD:**
- [ ] Endpoint accepts pack name (default "basic")
- [ ] Returns full result with per-test detail
- [ ] Stores validation run in DB (agent_id, pack, score, results JSONB, timestamp)
- [ ] `GET /agents/:id/validations` returns history of runs
- [ ] Tests: POST → response matches schema → re-run gives same score

### 30d — Validation properties

Tests must be:
- **Deterministic:** Same config → same results, no LLM randomness
- **Versioned:** Each test has version, results reference test version
- **Tied to pack version:** When pack changes, test pack version bumps

**DoD:**
- [ ] Each test has `version` field
- [ ] Results include `test_version` + `pack_version`
- [ ] Tests: same agent, two runs → identical results

---

## Test plan

Minimum **42 tests** across 4 sub-steps. Tests in `tests/agents/test_validation_runner.py`.

### 30a tests — Test pack definition (14 tests)

| # | Test | Assert |
|---|------|--------|
| 1 | `test_basic_pack_has_12_tests` | BasicTestPack → 12 test definitions |
| 2 | `test_pack_3_rbac_tests` | Exactly 3 tests with category="rbac" |
| 3 | `test_pack_3_injection_tests` | Exactly 3 tests with category="injection" |
| 4 | `test_pack_3_pii_tests` | Exactly 3 tests with category="pii" |
| 5 | `test_pack_3_budget_tests` | Exactly 3 tests with category="budget" |
| 6 | `test_rbac_test_uses_agent_roles` | Test 1 input.role = agent's lowest role |
| 7 | `test_rbac_test_uses_agent_tools` | Test 1 input.tool = agent's highest-sensitivity tool |
| 8 | `test_injection_test_uses_agent_args` | Test 4 injects into agent's actual tool arg names |
| 9 | `test_pii_test_uses_agent_tools` | Test 7 uses agent's tool names |
| 10 | `test_budget_test_uses_agent_limits` | Test 10 threshold = agent's rate_limit + 1 |
| 11 | `test_each_test_is_dataclass` | Every test has: name, category, description, input, expected |
| 12 | `test_pack_for_agent_no_tools` | Agent with 0 tools → pack generates with generic defaults |
| 13 | `test_pack_for_agent_no_roles` | Agent with 0 roles → pack generates with generic defaults |
| 14 | `test_pack_version_field` | BasicTestPack has version string |

### 30b tests — Validation engine (12 tests)

| # | Test | Assert |
|---|------|--------|
| 15 | `test_run_validation_demo_agent_12_pass` | Demo agent → 12/12 pass |
| 16 | `test_result_structure` | Result has total, passed, failed, tests[] |
| 17 | `test_per_test_detail` | Each test detail has: name, category, expected, actual, passed, duration_ms |
| 18 | `test_failed_test_has_recommendation` | Deliberately broken config → recommendation not null |
| 19 | `test_rbac_deny_detected` | Lowest role → highest tool → actual=DENY |
| 20 | `test_rbac_allow_detected` | Admin → admin tool → actual=ALLOW |
| 21 | `test_injection_blocked` | SQL injection input → actual=BLOCKED |
| 22 | `test_pii_redacted` | Email in output → actual=REDACTED |
| 23 | `test_budget_over_limit` | Exceed rate limit → actual=BLOCKED |
| 24 | `test_engine_loads_generated_config` | Engine uses agent's generated config, not hardcoded |
| 25 | `test_engine_no_config_generated` | Agent without generated config → error (not crash) |
| 26 | `test_engine_duration_ms` | Each test duration_ms > 0 |

### 30c tests — Validation API (12 tests)

| # | Test | Assert |
|---|------|--------|
| 27 | `test_post_validate_returns_result` | POST → 200, body matches schema |
| 28 | `test_post_validate_nonexistent_agent` | POST bad ID → 404 |
| 29 | `test_post_validate_default_pack` | POST without body → uses "basic" pack |
| 30 | `test_post_validate_unknown_pack` | POST { pack: "xxx" } → 422 |
| 31 | `test_post_validate_stores_run` | After POST, run stored in DB |
| 32 | `test_get_validations_history` | GET /agents/:id/validations → list of runs |
| 33 | `test_get_validations_empty` | New agent → [] |
| 34 | `test_get_validations_ordered` | Most recent first |
| 35 | `test_post_validate_categories_breakdown` | Response has categories.rbac, .injection, .pii, .budget |
| 36 | `test_post_validate_response_timing` | Response has run_at + duration_ms |
| 37 | `test_post_validate_result_schema_full` | Every field from API schema doc present |
| 38 | `test_rerun_same_score` | POST twice → same score (determinism) |

### 30d tests — Validation properties (4 tests)

| # | Test | Assert |
|---|------|--------|
| 39 | `test_deterministic_same_config` | Same config, 3 runs → 3 identical results |
| 40 | `test_versioned_tests` | Each test in result has version field |
| 41 | `test_pack_version_in_result` | Result includes pack_version |
| 42 | `test_no_llm_dependency` | Validation runs with no LLM configured (mocked/stubbed) |
