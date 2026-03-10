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
