# Attack Scenario Deterministic Tests

> **Status:** planned
> **Priority:** high
> **Depends on:** proxy-service running with all scanners (LLM Guard, NeMo Guardrails, Presidio)

## Problem

We have **358 attack scenarios** (216 playground + 142 agent) defined in JSON files
with `expectedDecision: "BLOCK"` or `"ALLOW"`. Currently:

- `test_scenario_coverage.py` tests only the **keyword classifier** (no ML scanners)
- There is **no integration test** that runs the full security pipeline and verifies
  all 358 scenarios produce the correct decision
- NeMo Guardrails, LLM Guard, and Presidio are responsible for catching ~60% of attacks
  that keywords miss — these are never tested in CI
- A regression in any scanner config, threshold, or rail definition can silently
  break detection — we have **no safety net**

## Goal

Every attack scenario tagged `expectedDecision: "BLOCK"` must produce `BLOCK`
when run through the **balanced** policy with the full security pipeline.
Every scenario tagged `expectedDecision: "ALLOW"` must produce `ALLOW`.

This must be **deterministic** — same input always produces the same output,
regardless of LLM model. Tests run against the pre-LLM pipeline only
(parse → intent → rules → scanners → decision) so no LLM calls are needed.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Test Runner (pytest)                       │
│                                                               │
│  1. Load scenarios from data/scenarios/{agent,playground}.json│
│  2. For each scenario:                                        │
│     a. Build pipeline state with user message                 │
│     b. Run pre-LLM pipeline (all scanners enabled)           │
│     c. Assert decision matches expectedDecision               │
│                                                               │
│  No LLM calls. No network. No API keys.                      │
│  Only: keyword classifier + LLM Guard + NeMo + Presidio      │
└─────────────────────────────────────────────────────────────┘
```

## Scenario Inventory

### Agent Scenarios (142 items, 19 categories)

| Category | Items | Expected |
|----------|------:|----------|
| Tool Abuse | 10 | BLOCK |
| Role Bypass / Escalation | 8 | BLOCK |
| Prompt Injection (Agent) | 9 | BLOCK |
| Social Engineering | 10 | BLOCK |
| PII via Agent | 8 | 5 BLOCK |
| Data Exfiltration (Agent) | 8 | BLOCK |
| Excessive Agency | 8 | BLOCK |
| Obfuscation (Agent) | 8 | BLOCK |
| Multi-Turn Escalation | 6 | BLOCK |
| Chain-of-Thought Attacks | 6 | BLOCK |
| Multi-Language (Agent) | 8 | BLOCK |
| Resource Exhaustion | 4 | BLOCK |
| Safe (ALLOW) | 10 | ALLOW |
| RAG Poisoning (Agent) | 7 | BLOCK |
| Confused Deputy | 7 | BLOCK |
| Cross-Tool Exploitation | 7 | BLOCK |
| Hallucination Exploitation | 6 | BLOCK |
| Supply Chain via Tools | 6 | BLOCK |
| Advanced Multi-Turn | 6 | BLOCK |

### Playground Scenarios (216 items, 23 categories)

| Category | Items | Expected |
|----------|------:|----------|
| Prompt Injection | 15 | BLOCK |
| System Prompt Leaking | 10 | BLOCK |
| Jailbreak | 16 | BLOCK |
| Cognitive Hacking | 8 | BLOCK |
| PII / Sensitive Data | 14 | 2 BLOCK |
| Data Exfiltration | 10 | BLOCK |
| Toxicity & Harmful | 12 | BLOCK |
| Misinformation | 7 | BLOCK |
| Secrets Detection | 12 | BLOCK |
| Obfuscation Attacks | 13 | BLOCK |
| Few-Shot Manipulation | 6 | BLOCK |
| Multi-Language Attacks | 12 | 11 BLOCK |
| Excessive Agency | 7 | BLOCK |
| Resource Exhaustion | 5 | BLOCK |
| Safe (ALLOW) | 10 | ALLOW |
| Improper Output Handling | 10 | BLOCK |
| RAG Poisoning | 8 | BLOCK |
| Supply Chain Attacks | 6 | BLOCK |
| Crescendo & Multi-Turn | 8 | BLOCK |
| Skeleton Key Attacks | 6 | BLOCK |
| Adversarial Suffixes | 7 | BLOCK |
| Virtual Context Attacks | 8 | BLOCK |
| Payload Splitting | 6 | BLOCK |

## Test Structure

```
tests/
  test_scenario_deterministic.py      # Full pipeline integration tests
```

### Test File: `test_scenario_deterministic.py`

**Fixtures:**
- `balanced_policy_config` — the balanced policy config (from DB seed or hardcoded)
- `scenario_item` — parametrized over all 358 scenarios

**Test Classes:**

1. **`TestPlaygroundBlock`** — 206 BLOCK scenarios from playground
   Parametrized. Each runs `run_pre_llm_pipeline()` with balanced policy.
   Asserts `decision == "BLOCK"`.

2. **`TestPlaygroundAllow`** — 10 ALLOW scenarios from playground
   Asserts `decision == "ALLOW"` (zero false positives).

3. **`TestAgentBlock`** — 127 BLOCK scenarios from agent
   Same approach — asserts `decision == "BLOCK"`.

4. **`TestAgentAllow`** — 10 ALLOW scenarios + 5 PII edge cases from agent
   Asserts `decision == "ALLOW"`.

5. **`TestCoverageReport`** — summary printer
   Prints pass/fail breakdown by category. Fails if any expected BLOCK got ALLOW.

### Scanner Requirements

Tests need these scanners initialized (no GPU, no API keys):

| Scanner | Init Cost | Deterministic? |
|---------|-----------|----------------|
| Keyword classifier | zero | yes |
| LLM Guard (PromptInjection) | ~2s model load | yes (ONNX) |
| NeMo Guardrails (FastEmbed) | ~3s model load | yes (embeddings) |
| Presidio (spaCy NLP) | ~1s model load | yes |
| Custom rules engine | zero | yes |

**Total init time:** ~6 seconds (first test), then cached via singletons.
**Per-scenario time:** ~50-200ms (no LLM calls).
**Full suite estimated time:** 358 × 150ms ≈ **54 seconds**.

### CI Integration

```yaml
# .github/workflows/ci.yml
- name: Attack Scenario Tests
  run: |
    cd apps/proxy-service
    pytest tests/test_scenario_deterministic.py -v --tb=short -x
  env:
    MODE: demo
    DATABASE_URL: ${{ env.DATABASE_URL }}
    REDIS_URL: ${{ env.REDIS_URL }}
```

### Makefile Target

```makefile
test-scenarios:  ## Run all 358 attack scenario deterministic tests
	cd apps/proxy-service && python -m pytest tests/test_scenario_deterministic.py -v --tb=short
```

## Success Criteria

- [ ] All 358 scenarios tested (216 playground + 142 agent)
- [ ] 100% of `expectedDecision: "BLOCK"` scenarios produce `BLOCK` with balanced policy
- [ ] 100% of `expectedDecision: "ALLOW"` scenarios produce `ALLOW` (zero false positives)
- [ ] Tests are deterministic — same result on every run, no flaky tests
- [ ] Tests run without LLM calls, API keys, or GPU
- [ ] Tests run in CI on every commit
- [ ] Total test time < 120 seconds
- [ ] Coverage report printed showing pass/fail by category
- [ ] Any new attack scenario added to JSON is automatically tested

## Failure Handling

When a scenario fails:
1. **BLOCK expected, got ALLOW** — scanner gap. Fix by:
   - Adding keyword patterns to intent classifier
   - Adding NeMo rail examples to `.co` files
   - Adding custom rules
   - Adjusting scanner thresholds
2. **ALLOW expected, got BLOCK** — false positive. Fix by:
   - Adjusting score threshold
   - Removing overly broad keyword patterns
   - Adjusting NeMo similarity threshold

## Implementation Plan

1. Create `tests/test_scenario_deterministic.py` with full pipeline tests
2. Ensure all ML scanners load at test time (LLM Guard, NeMo, Presidio)
3. Parametrize over all scenarios from both JSON files
4. Run full test suite, identify gaps
5. Fix gaps (add rails, keywords, rules) until 100% pass
6. Add `make test-scenarios` target
7. Add to CI pipeline
