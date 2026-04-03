# Step 18 — Explainability ("Why was it blocked?")

> **Goal**: Every firewall decision includes a structured, human-readable
> **explanation** that traces exactly *which* rule matched, *which* scanner
> triggered, and *how* the risk score compares to the threshold.
> Enterprise customers need this for compliance audits and developer trust.

**Prev**: [Step 17 — Observe / Simulate Mode](../17-observe-simulate/SPEC.md)
**Next**: [Step 19 — Replay Requests](../19-replay-requests/SPEC.md)

---

## Concept

After the decision node, a new **ExplainNode** builds an `explanation` object
that is stored in the pipeline state, persisted in the `requests` table, and
surfaced in the API + frontend.

```jsonc
{
  "verdict": "BLOCK",
  "risk_score": 0.82,
  "threshold": 0.70,
  "reasons": [
    {
      "source": "intent",
      "signal": "jailbreak",
      "contribution": 0.60,
      "detail": "Intent classified as 'jailbreak' (confidence 0.92)"
    },
    {
      "source": "scanner:llm_guard",
      "signal": "promptinjection",
      "contribution": 0.22,
      "detail": "LLM Guard PromptInjection score 0.28 × weight 0.8 = 0.22"
    }
  ],
  "matched_rules": ["denylist:ignore previous", "custom:no_base64"],
  "scanner_summary": {
    "llm_guard": {"promptinjection": 0.28, "toxicity": 0.01},
    "presidio": {"pii_count": 0, "entities": []}
  },
  "mode": "enforce",
  "original_decision": null
}
```

---

## Sub-steps

### 18a — ExplainNode + State

| Area | Detail |
|------|--------|
| **PipelineState** | Add `explanation: dict \| None` field. |
| **ExplainNode** | New node `explain_node` in `src/pipeline/nodes/explain.py`. Runs after `decision_node` (or after `mode_gate` if Step 17 is in place). Reads: `risk_score`, `risk_flags`, `policy_config.thresholds`, `rules_matched`, `scanner_results`, `decision`, `blocked_reason`, `intent`, `intent_confidence`, `original_decision`, `mode`. Produces the structured `explanation` dict. |
| **Score breakdown** | Re-use `calculate_risk_score` logic but in a decomposed form: iterate each risk signal and record its `source`, `signal`, and `contribution` (the delta it adds to the score). Return as `reasons` list sorted by contribution desc. |
| **Graph wiring** | Insert `explain_node` after `mode_gate` (or `decision` if 17 not done): `decision → [mode_gate →] explain → route_after_decision`. |

### 18b — Persistence & API

| Area | Detail |
|------|--------|
| **Request model** | Add `explanation: Mapped[dict \| None] = mapped_column(JSONB, nullable=True)` to `Request`. |
| **Migration** | Alembic: `ALTER TABLE requests ADD COLUMN explanation JSONB;` |
| **LoggingNode** | Write `state["explanation"]` into `request.explanation`. |
| **Request detail API** | `GET /v1/requests/{id}` already returns all columns — include `explanation`. |
| **Request list API** | Optionally include a truncated `explanation.verdict` + `explanation.risk_score` in the list schema (lightweight). |

### 18c — Frontend: Explanation Panel

| Area | Detail |
|------|--------|
| **Request detail expansion** | In the request-log expandable row, add a new **Explanation** tab/section. |
| **Risk breakdown** | Visual bar showing score contributions (stacked horizontal bar). Each segment = one `reason` entry, coloured by source type (intent=blue, scanner=orange, rule=red, pii=purple). Tooltip shows detail text. |
| **Matched rules list** | Chip list of `matched_rules`. |
| **Scanner summary** | Table or key-value list of scanner results (already partially shown; re-use and enrich). |
| **Threshold indicator** | A gauge or marker showing `risk_score` vs `threshold` — visually obvious whether it passed or failed. |
| **Mode badge** | If `original_decision` differs from `verdict`, show observe mode annotation: "Would have been BLOCK (observe mode)". |

---

## Technical Notes

- `ExplainNode` is pure computation — no external calls, deterministic, < 1ms.
- The decomposed score breakdown mirrors `calculate_risk_score` but records each delta. To keep them in sync, refactor `calculate_risk_score` to return both the total and the breakdown list (`_calculate_risk_breakdown(state) → (float, list[dict])`).
- Explanation JSON is append-only (never updated after creation) — ideal for compliance/audit.

---

## Definition of Done

- [ ] `explain_node` produces structured explanation dict
- [ ] `calculate_risk_score` refactored to also return per-signal breakdown
- [ ] `explanation` column in `requests` table with migration
- [ ] `LoggingNode` persists explanation
- [ ] API returns explanation in request detail
- [ ] Frontend: risk breakdown bar, matched rules, scanner summary, threshold gauge
- [ ] Tests: explanation structure, score decomposition accuracy, node timing
