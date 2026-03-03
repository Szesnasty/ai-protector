# Step 17 — Observe / Simulate Mode

> **Goal**: Let operators deploy the firewall in "shadow mode" — the full pipeline runs
> and logs its decisions, but BLOCK verdicts are downgraded to ALLOW so real traffic
> is never interrupted. This is critical for enterprise adoption: teams can validate
> policies on production traffic before flipping to enforcement.

**Prev**: [Step 16 — Analytics](../16-analytics/SPEC.md)
**Next**: [Step 18 — Explainability](../18-explainability/SPEC.md)

---

## Concept

Each **policy** gains a new field `mode` with two allowed values:
| Mode | Behaviour |
|-----------|-----------|
| `enforce` | Pipeline runs normally — BLOCK/MODIFY/ALLOW are all honoured (current behaviour). |
| `observe` | Pipeline runs identically, but after the decision node a **mode gate** converts BLOCK → ALLOW and MODIFY → ALLOW. The *original* decision is stored in a new field `original_decision` so logs and analytics show "would have blocked". |

The observe mode **does not skip** any scanner or rule — everything executes exactly as
in enforce mode so the logs are faithful.

---

## Sub-steps

### 17a — Policy Model & Migration

| Area | Detail |
|------|--------|
| **Model change** | Add `mode: Mapped[str] = mapped_column(String(16), nullable=False, default="enforce")` to `Policy` model. Allowed values: `enforce`, `observe`. |
| **Migration** | Alembic migration: `ALTER TABLE policies ADD COLUMN mode VARCHAR(16) NOT NULL DEFAULT 'enforce';` |
| **Policy schema** | Add `mode` to `PolicyCreate`/`PolicyUpdate`/`PolicyOut` Pydantic schemas. Validate enum. |
| **Seed data** | Existing seed policies keep `mode = "enforce"`. |

### 17b — Pipeline Mode Gate

| Area | Detail |
|------|--------|
| **PipelineState** | Add two new fields: `mode: Literal["enforce", "observe"]` and `original_decision: Literal["ALLOW", "MODIFY", "BLOCK"] \| None`. |
| **Runner** | `run_pipeline()` and `run_pre_llm_pipeline()` read `policy_config["mode"]` (default `"enforce"`) and inject it into `initial_state["mode"]`. |
| **Mode gate node** | New node `mode_gate_node` inserted **after** `decision_node` in the graph. Logic: if `mode == "observe"` and `decision != "ALLOW"`, set `original_decision = decision`, override `decision = "ALLOW"`, clear `blocked_reason`. |
| **Graph wiring** | `decision → mode_gate → [route_after_decision]`. Order: parse → intent → rules → scanners → decision → **mode_gate** → routing. |
| **Pre-LLM pipeline** | Same gate added after `decision` in `_build_pre_llm_pipeline()`. |
| **Logging node** | `LoggingNode` stores `original_decision` in the Request model (new nullable column + migration). |

### 17c — Request Model & API

| Area | Detail |
|------|--------|
| **Request model** | Add `original_decision: Mapped[str | None]` and `mode: Mapped[str | None]` columns. |
| **Migration** | Alembic: add columns `original_decision VARCHAR(16)`, `mode VARCHAR(16)` to `requests`. |
| **Request log API** | Include `original_decision` and `mode` in response schemas. Allow filtering by `mode`. |
| **Analytics** | Adjust `/v1/analytics/summary` to report both *actual* and *would-have-been* block counts when `mode=observe` data exists. Add a new `observe_would_block` metric. |

### 17d — Frontend: Mode Toggle

| Area | Detail |
|------|--------|
| **Policies UI** | Add a toggle switch (Vuetify `v-switch`) to each policy card: Enforce / Observe. PATCH on toggle. Green badge = enforce, amber badge = observe. |
| **Policy config editor** | Show `mode` field in the editor dialog. |
| **Request log** | New column/chip: mode (`enforce`/`observe`). When `original_decision` is set, show it as a ghost chip ("would block") next to the actual decision chip. |
| **Analytics** | On KPI cards, if observe data exists, show a secondary line: "Would have blocked: N". Timeline chart gains a dashed line for observe-mode would-block decisions. |

---

## Technical Notes

- The mode gate is a **pure function** — no external calls, O(1).
- Tests must verify: (a) in observe mode, decision is always ALLOW; (b) `original_decision` preserves the real verdict; (c) enforce mode is unchanged.
- `x-decision` response header should reflect the **effective** decision (ALLOW in observe mode), but add `x-original-decision` header when it differs.

---

## Definition of Done

- [ ] `policies.mode` column with migration
- [ ] `mode_gate_node` in pipeline graph (both full and pre-LLM)
- [ ] `original_decision` + `mode` persisted in `requests` table
- [ ] Policy API accepts/returns `mode`
- [ ] Frontend toggle for observe/enforce per policy
- [ ] Request log shows "would block" when `original_decision != decision`
- [ ] Analytics show observe-mode metrics
- [ ] Tests: pipeline mode gate, API round-trip, observe analytics
