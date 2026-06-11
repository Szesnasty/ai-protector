# B4 — Optional LLM-Judge Tier (High-Risk Only)

> **Track:** B (defense-in-depth)
> **Priority:** Medium
> **Effort:** M
> **Status:** Planned
> **Depends on:** A1 (defines the uncertainty band), A3 (proves it helps)

---

## 1. Goal

Add a semantic LLM-judge as an **optional final tier that fires only on
ambiguous / high-risk requests**. This closes the semantic tail (PAIR-style
attacks) that pattern + shallow-ML detection misses — *without* sacrificing the
deterministic, no-LLM-in-the-loop guarantee for the ~95% of clear-cut traffic.

## 2. Current state

The pipeline is proudly LLM-free and deterministic (a real selling point). The
cost is the semantic tail: roleplay-framed attacks that score low on every
deterministic signal. There is no escalation path for "looks borderline."

## 3. Approach (big blocks)

1. **Band-based routing.** In
   [`decision.py`](../../apps/proxy-service/src/pipeline/nodes/decision.py),
   route to the judge **only** when `risk_score` falls in an *uncertain band*
   near the threshold (or for specific intents) — never on every request. Keeps
   cost and latency bounded to a small slice of traffic.
2. **Judge node.** A new conditional node that calls a small/cheap model
   (configurable — local Llama Guard or a provider) with a strict rubric at
   temperature 0, returning a structured verdict + reason. Cache by `prompt_hash`.
3. **Policy-gated, off by default.** Clearly labeled as the one non-deterministic
   tier. Determinism stays the default story; this is opt-in for teams that want
   the extra recall.
4. **Fail-closed fusion.** The judge may only **confirm or escalate** (→ BLOCK).
   It can never silently allow something the deterministic layer blocked.

## 4. Affected components

- `pipeline/graph.py` (conditional edge for the judge), new `pipeline/nodes/judge.py`
- `decision.py` (band logic + fusion), policy config (`enable_judge`, band bounds)
- `llm/client.py` (judge call), result caching

## 5. Acceptance criteria

- [ ] Judge fires on only a small, configurable fraction of traffic (the band).
- [ ] Detection on PAIR / semantic attacks improves when enabled (measured via A3).
- [ ] FPR does not rise (judge can only escalate, fusion is fail-closed).
- [ ] Latency cost is incurred **only** on routed requests, not the whole stream.
- [ ] Off by default; determinism preserved when disabled.

## 6. Out of scope

- Replacing the deterministic pipeline. This is a tail-coverage add-on, not the
  primary path.

## 7. Risks / open questions

- Cost/latency if the band is mis-sized — make the band and a per-window judge
  budget configurable; monitor the routed fraction.
- Non-determinism is a feature regression for some buyers — keep it clearly
  optional and documented as such.
