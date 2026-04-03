# Step 19 — Replay Requests

> **Goal**: Click any request in the log → replay it through the pipeline with a
> **different policy and/or model** → see a side-by-side comparison of the two
> outcomes. This is a powerful tool for policy tuning, incident review, and
> demonstrating to stakeholders how policy changes affect real traffic.

**Prev**: [Step 18 — Explainability](../18-explainability/SPEC.md)

---

## Concept

A **replay** takes the original request's `messages` and `model` (stored in the
`requests` table) and re-runs the **pre-LLM pipeline** (parse → intent → rules →
scanners → decision → mode_gate → explain) against a target policy. No actual LLM
call is made — we only care about the firewall verdict.

The result is a **comparison** object:

```jsonc
{
  "original": {
    "request_id": "chatcmpl-abc123",
    "policy": "balanced",
    "decision": "BLOCK",
    "risk_score": 0.82,
    "explanation": { /* … from Step 18 */ }
  },
  "replay": {
    "policy": "fast",
    "decision": "ALLOW",
    "risk_score": 0.35,
    "explanation": { /* … */ }
  },
  "delta": {
    "decision_changed": true,
    "risk_score_diff": -0.47,
    "new_flags": [],
    "removed_flags": ["denylist_hit"]
  }
}
```

---

## Sub-steps

### 19a — Replay API Endpoint

| Area | Detail |
|------|--------|
| **Endpoint** | `POST /v1/requests/{id}/replay` |
| **Request body** | `{ "policy_name": "fast", "model": "llama3.1:8b" }` — both optional, default to original values. |
| **Logic** | 1. Fetch original `Request` by ID (404 if not found). 2. Reconstruct messages: the `prompt_preview` field stores the user message, but for full fidelity we need the full messages. **Add** `messages_json: Mapped[dict \| None] = mapped_column(JSONB, nullable=True)` to `Request` model so we persist the full conversation. 3. Call `run_pre_llm_pipeline()` with the target policy + model. 4. Build the comparison object. |
| **Response schema** | `ReplayResponse` Pydantic model with `original`, `replay`, `delta` sections. |
| **No LLM call** | Replay only runs the firewall pipeline, never calls the LLM. Fast and safe. |
| **Rate limit** | Optional: max 10 replays/min per client to prevent scanner abuse. |

### 19b — Message Persistence

| Area | Detail |
|------|--------|
| **Request model** | Add `messages_json: Mapped[list \| None] = mapped_column(JSONB, nullable=True)` to persist the full conversation array. |
| **Migration** | Alembic: `ALTER TABLE requests ADD COLUMN messages_json JSONB;` |
| **LoggingNode** | Write `state["messages"]` into `request.messages_json`. Truncate if > 32 KB to prevent bloat. |
| **Privacy note** | `messages_json` contains raw user input — document that this is opt-in and can be disabled via a config flag (`STORE_RAW_MESSAGES=true`). When disabled, replay endpoint returns 409 "Raw messages not available for this request". |

### 19c — Replay Comparison Logic

| Area | Detail |
|------|--------|
| **Comparison builder** | Utility function `build_replay_comparison(original_request, replay_state)` that produces the `delta` section. |
| **Delta fields** | `decision_changed: bool`, `risk_score_diff: float`, `new_flags: list[str]` (flags in replay not in original), `removed_flags: list[str]` (flags in original not in replay), `rules_diff: list[str]`. |
| **Explanation diff** | If Step 18 is done, include the full `explanation` for both sides so the frontend can show them side-by-side. |

### 19d — Frontend: Replay Dialog

| Area | Detail |
|------|--------|
| **Trigger** | New "Replay" button (icon: `mdi-replay`) in each request-log row's action column. |
| **Dialog** | `ReplayDialog.vue` — modal with: (1) policy selector dropdown, (2) model selector dropdown (pre-filled with original values), (3) "Run Replay" button. |
| **Loading state** | Show spinner while replay runs (typically < 2s since no LLM call). |
| **Results view** | Side-by-side comparison card: left = original, right = replay. Each side shows: decision chip, risk score gauge, risk flags as chips, matched rules. Highlight differences in red/green. |
| **Delta summary** | Banner at top: "Decision changed: BLOCK → ALLOW", "Risk score: 0.82 → 0.35 (−0.47)". Colour-coded (green if safer, red if riskier). |
| **Explanation diff** | If explanations are available, show the risk breakdown bars side-by-side (Step 18 component reuse). |

---

## Technical Notes

- Replay uses `run_pre_llm_pipeline()` which already exists — minimal new pipeline code.
- The replay is **stateless** — it does not create a new `Request` row (no pollution of analytics). Optionally log replay events to a separate audit table later.
- Full messages persistence is ~1-3 KB per request on average. For 100K requests that's ~300 MB — acceptable for MVP, add TTL/archival later.
- The comparison endpoint is read-heavy and idempotent — safe to cache with short TTL.

---

## Definition of Done

- [ ] `messages_json` column in `requests` table with migration
- [ ] `LoggingNode` persists full messages (with truncation + opt-out flag)
- [ ] `POST /v1/requests/{id}/replay` endpoint with `ReplayResponse` schema
- [ ] Comparison builder with delta computation
- [ ] Frontend: Replay button in request log
- [ ] Frontend: Replay dialog with policy/model selectors
- [ ] Frontend: Side-by-side comparison view with diff highlighting
- [ ] Tests: replay endpoint, comparison logic, missing-messages 409
