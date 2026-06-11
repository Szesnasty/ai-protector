# B2 — Canary Tokens + ML Judge (De-vaporize)

> **Track:** B (defense-in-depth)
> **Tracks issue:** ISS-003 (ML Judge), ISS-004 (Canary)
> **Priority:** Medium
> **Effort:** S–M
> **Status:** Planned

---

## 1. Goal

Make two UI-advertised-but-non-functional features real (or remove them). Both
currently appear as policy-editor chips and set flags that nothing reads — a
classic red flag in technical due diligence ("advertised capability does not
exist").

## 2. Current state

- **Canary (ISS-004):** the chip sets `enable_canary: true` in policy
  thresholds, but no pipeline node injects or detects a canary.
- **ML Judge (ISS-003):** the chip suggests a dedicated ML safety model; in
  reality there is no `ml_judge` node — it only nudges risk weights in
  [`decision.py`](../../apps/proxy-service/src/pipeline/nodes/decision.py).

Note: the red-team engine **already implements** a per-run `${CANARY}`
mechanism — see
[`run_engine.py`](../../apps/proxy-service/src/red_team/engine/run_engine.py)
(`canary_token`, `_substitute_canary_in_scenario`). Reuse it.

## 3. Approach (big blocks)

### 3a. Canary tokens (build)

1. **Inject** a per-request canary string into the system prompt when
   `enable_canary` — in [`transform.py`](../../apps/proxy-service/src/pipeline/nodes/transform.py)
   or at the `llm_call` boundary.
2. **Detect** the canary in
   [`output_filter.py`](../../apps/proxy-service/src/pipeline/nodes/output_filter.py):
   if the canary appears in the model's response, the system prompt / context
   leaked → BLOCK + flag.
3. **Unify** with the red-team engine's existing `${CANARY}` machinery so there
   is one implementation.

### 3b. ML Judge (truth-up)

- **Preferred:** wire the chip to the **A1 ML classifier** so "ML Judge"
  surfaces a real model score in the decision, with the score visible in the
  trace. The label becomes honest.
- **Alternative:** if A1 isn't ready, rename/hide the chip until it is. Do not
  ship a chip that implies a model that doesn't exist.

## 4. Affected components

- `transform.py` / `llm_call.py` (canary injection), `output_filter.py` (detect)
- `decision.py`, policy config schema
- Frontend chips: `app/components/policies/config-editor.vue`
- Reuse: `red_team/engine/run_engine.py` canary helpers

## 5. Acceptance criteria

- [ ] Enabling **Canary** on a system-prompt-leak demo measurably flips the
      outcome to BLOCK when the canary leaks.
- [ ] The **ML Judge** chip maps to a real model score (A1) or is removed.
- [ ] No policy flag remains that is advertised in the UI but read by nothing.
- [ ] Canary implementation is shared with the red-team engine.

## 6. Out of scope

- Building the A1 model (consumed here for the ML Judge mapping).

## 7. Risks / open questions

- Canary must be unguessable per request and stripped from anything logged in
  plaintext.
- ML Judge naming: align UI copy with what the model actually does to avoid
  swapping one overclaim for another.
