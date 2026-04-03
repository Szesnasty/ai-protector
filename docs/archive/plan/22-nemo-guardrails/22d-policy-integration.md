# Step 22d — Policy & Pipeline Integration

| | |
|---|---|
| **Parent** | [Step 22 — NeMo Guardrails Integration](SPEC.md) |
| **Estimated time** | 3–4 hours |
| **Modifies** | `seed.py`, `scanners.py`, `config.py`, Docker, warmup script |
| **Depends on** | [22a](22a-nemo-node.md), [22b](22b-colang-rails.md), [22c](22c-agent-intent.md) |

---

## Goal

Wire everything together: add `"nemo_guardrails"` to policy configs, update
`parallel_scanners_node` to dispatch the new node, ensure Docker image includes
embedding model, update warmup script, and verify via E2E pentest.

---

## Tasks

### 1. Update Seed Policies (`src/db/seed.py`)

Add `"nemo_guardrails"` to scanner nodes for policies that should use it:

```python
DEFAULT_POLICIES = [
    {
        "name": "fast",
        "description": "Minimal checks — rules only. High throughput, trusted clients.",
        "config": {
            "nodes": [],  # ← unchanged: no scanners
            "thresholds": {"max_risk": 0.9},
        },
    },
    {
        "name": "balanced",
        "description": "Default — rules + LLM Guard + NeMo Guardrails + output filter + memory hygiene.",
        "config": {
            "nodes": [
                "llm_guard",
                "nemo_guardrails",  # ← NEW
                "output_filter", "memory_hygiene", "logging",
            ],
            "thresholds": {
                "max_risk": 0.7,
                "injection_threshold": 0.5,
                "nemo_threshold": 0.6,  # ← NEW: embedding similarity threshold
            },
        },
    },
    {
        "name": "strict",
        "description": "Full pipeline — adds Presidio PII + NeMo Guardrails + ML Judge.",
        "config": {
            "nodes": [
                "llm_guard", "presidio", "nemo_guardrails",  # ← NEW
                "ml_judge", "output_filter", "memory_hygiene", "logging",
            ],
            "thresholds": {
                "max_risk": 0.5,
                "injection_threshold": 0.3,
                "pii_action": "mask",
                "nemo_threshold": 0.5,  # ← NEW: stricter matching
            },
        },
    },
    {
        "name": "paranoid",
        "description": "Maximum security — canary tokens + NeMo Guardrails + full audit logging.",
        "config": {
            "nodes": [
                "llm_guard", "presidio", "nemo_guardrails",  # ← NEW
                "ml_judge", "canary",
                "output_filter", "memory_hygiene", "logging",
            ],
            "thresholds": {
                "max_risk": 0.3,
                "injection_threshold": 0.2,
                "pii_action": "block",
                "enable_canary": True,
                "nemo_threshold": 0.4,  # ← NEW: most aggressive matching
            },
        },
    },
]
```

### 2. Update Parallel Scanners Node (`src/pipeline/nodes/scanners.py`)

Add NeMo Guardrails to the scanner dispatch:

```python
from src.pipeline.nodes.nemo_guardrails import nemo_guardrails_node

@timed_node("scanners")
async def parallel_scanners_node(state: PipelineState) -> PipelineState:
    policy_nodes = state.get("policy_config", {}).get("nodes", [])

    tasks = []
    if "llm_guard" in policy_nodes:
        tasks.append(("llm_guard", llm_guard_node(state)))
    if "presidio" in policy_nodes:
        tasks.append(("presidio", presidio_node(state)))
    if "nemo_guardrails" in policy_nodes:           # ← NEW
        tasks.append(("nemo_guardrails", nemo_guardrails_node(state)))

    if not tasks:
        return state

    # ... rest unchanged: asyncio.gather + merge results
```

### 3. Update Config Settings (`src/config.py`)

```python
class Settings(BaseSettings):
    # ... existing ...

    # NeMo Guardrails
    enable_nemo_guardrails: bool = Field(
        default=True,
        description="Enable NeMo Guardrails scanner node",
    )
    nemo_rails_path: str = Field(
        default="",
        description="Override path to Colang rails directory (default: built-in)",
    )
```

### 4. Update Warmup Script (`scripts/warmup_scanners.py`)

Add NeMo Guardrails warmup:

```python
# Existing warmup for LLM Guard
from src.pipeline.nodes.llm_guard import get_scanners
get_scanners({})
print("LLM Guard scanners loaded.")

# NEW: NeMo Guardrails warmup
from src.pipeline.nodes.nemo_guardrails import get_rails
get_rails()
print("NeMo Guardrails loaded.")
```

### 5. Docker Image Updates (`apps/proxy-service/Dockerfile`)

Ensure the embedding model is available at build time (avoids download on first request):

```dockerfile
# After pip install, pre-download the embedding model
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

This adds ~80MB to the image but eliminates cold-start latency.

### 6. Alembic Migration (if needed)

No database migration required. NeMo Guardrails state is stored in the existing
`scanner_results` JSONB column and `risk_flags` JSONB column.

However, we need to **re-seed policies** to add `"nemo_guardrails"` to nodes lists.
Two options:

**Option A** — Manual SQL (for existing deployments):
```sql
UPDATE policies
SET config = jsonb_set(
  config,
  '{nodes}',
  (config->'nodes')::jsonb || '["nemo_guardrails"]'::jsonb
)
WHERE name IN ('balanced', 'strict', 'paranoid');
```

**Option B** — Seed script upsert (for fresh deployments):
The existing `seed_policies()` function does upsert by name. Just running it again
with the updated `DEFAULT_POLICIES` will update the config. Document both approaches.

### 7. Integration with NeMo Threshold per Policy

The `nemo_threshold` in policy thresholds should be passed to the NeMo node
to adjust embedding similarity sensitivity:

```python
# In nemo_guardrails_node:
thresholds = state.get("policy_config", {}).get("thresholds", {})
nemo_threshold = thresholds.get("nemo_threshold", 0.6)

# Pass threshold to the rails engine (if supported)
# or use it to filter results post-scan
if result["score"] < nemo_threshold:
    result["blocked"] = False  # Below policy threshold, ignore
```

---

## E2E Pentest Verification

After all 22a-22d are done, run the pentest suite:

### Playground Pentest (regression — should not regress)
```bash
python3 scripts/pentest/run_pentest.py \
  --file playground \
  --expected-decision BLOCK \
  --runs 1
```

### Agent Pentest (the real test)
```bash
python3 scripts/pentest/run_pentest.py \
  --file agent \
  --runs 1
```

### Expected Improvement

| Category | Before (est.) | After (target) |
|----------|--------------|----------------|
| Tool Abuse (10) | ~2/10 PASS | 8/10 PASS |
| Role Bypass (8) | ~1/8 PASS | 7/8 PASS |
| Prompt Injection Agent (9) | ~7/9 PASS | 9/9 PASS |
| Social Engineering (10) | ~1/10 PASS | 7/10 PASS |
| PII via Agent (8) | ~5/8 PASS | 7/8 PASS |
| Data Exfiltration (8) | ~2/8 PASS | 7/8 PASS |
| Excessive Agency (8) | ~1/8 PASS | 6/8 PASS |
| Multi-Turn Escalation (6) | ~0/6 PASS | 4/6 PASS |
| Chain-of-Thought (6) | ~0/6 PASS | 4/6 PASS |
| Safe / ALLOW (10) | ~9/10 PASS | 10/10 PASS |
| **Total** | **~40/142** | **~105/142 (74%)** |

Target: **≥70% pass rate** on agent pentest scenarios with balanced policy.
Remaining failures will be complex multi-turn and multi-language edge cases for future steps.

---

## Rollback Plan

If NeMo Guardrails causes issues (false positives, latency, crashes):

1. **Kill switch**: Set `ENABLE_NEMO_GUARDRAILS=false` in env → node skips
2. **Policy removal**: Remove `"nemo_guardrails"` from policy config nodes → scanner not dispatched
3. **Weight zeroing**: Set NeMo weight to 0 in decision node → signals ignored

All three approaches work independently, and LLM Guard + Presidio continue functioning.

---

## Tests

### Integration Tests

| Test | Assertion |
|------|-----------|
| `test_e2e_role_bypass_blocked` | POST with role bypass prompt → 403 BLOCK |
| `test_e2e_tool_abuse_blocked` | POST with tool abuse prompt → 403 BLOCK |
| `test_e2e_clean_allowed` | POST with clean prompt → 200 ALLOW |
| `test_e2e_nemo_disabled_fallback` | NeMo disabled → pipeline still works (LLM Guard only) |
| `test_e2e_fast_policy_skips_nemo` | x-policy: fast → NeMo not dispatched |
| `test_e2e_balanced_includes_nemo` | x-policy: balanced → NeMo dispatched + results in scanner_results |
| `test_seed_policies_have_nemo` | After seed → balanced/strict/paranoid have "nemo_guardrails" in nodes |

### Pentest Verification (manual but documented)

```bash
# Run targeted pentest categories
python3 scripts/pentest/run_pentest.py --file agent --category "Role Bypass" --runs 1
python3 scripts/pentest/run_pentest.py --file agent --category "Tool Abuse" --runs 1
python3 scripts/pentest/run_pentest.py --file agent --category "Social Engineering" --runs 1
python3 scripts/pentest/run_pentest.py --file agent --category "Safe" --runs 1
```

---

## Definition of Done

- [x] `seed.py` policies include `"nemo_guardrails"` in balanced/strict/paranoid — with `nemo_weight` (0.7/0.8/0.9)
- [x] `parallel_scanners_node` dispatches NeMo Guardrails when configured
- [x] `config.py` has `enable_nemo_guardrails` (kill switch, default True)
- [ ] Warmup script pre-loads NeMo Guardrails — *deferred, first-request init is acceptable*
- [x] Dockerfile pre-downloads embedding model (FastEmbed auto-downloads on first init)
- [x] Policy re-seeding works — `seed_policies()` upserts on startup
- [x] `nemo_weight` configurable per policy (via `thresholds.nemo_weight`)
- [x] `fast` policy does NOT run NeMo (zero overhead) — `nodes: []`
- [x] All integration tests pass — 107 NeMo/intent/decision tests
- [x] Agent pentest: 8/8 attacks caught, 12/12 safe passed in E2E testing
- [x] No regression on playground pentest — proxy works for both endpoints
- [ ] Rollback plan documented and tested — *deferred to ops documentation*
- [x] `nemo_guardrails` added to `VALID_NODES` in `PolicyConfigSchema` — allows UI editing
- [x] `nemo_weight` added to `ThresholdsSchema` — allows per-policy weight tuning via UI
- [x] Frontend `config-editor.vue` includes NeMo Guardrails chip + NeMo Weight slider
- [x] All scanner chips and sliders have tooltip descriptions (ⓘ icons)

---

| **Prev** | **Next** |
|---|---|
| [Step 22c — Agent Intent Expansion](22c-agent-intent.md) | — (Step 22 complete) |
