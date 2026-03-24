# 06 — Deeper Heuristics

> **Layer:** Backend
> **Phase:** 4 (Advanced)
> **Depends on:** Heuristic Evaluators (Phase 2)

## Scope

Enhanced heuristic analysis for external targets — deeper pattern matching, multi-signal evaluation, and improved confidence scoring.

## Implementation Steps

### Step 1: Multi-turn analysis

- Detect patterns across conversation context (not just single response)
- "Did the model gradually comply over multiple turns?"

### Step 2: Semantic compliance detection

- Beyond keyword matching: detect paraphrased compliance
- "The model didn't say 'Sure' but it still answered the question fully"

### Step 3: Response structure analysis

- Detect structured data dumps (JSON, tables, lists) that indicate data leakage
- Classify response type: refusal, deflection, partial compliance, full compliance

### Step 4: Confidence calibration

- Calibrate heuristic confidence scores against known-good/known-bad responses
- `confidence` field becomes more meaningful

## Tests

| Test | What it verifies |
|------|-----------------|
| `test_paraphrased_compliance_detected` | Indirect compliance caught |
| `test_structured_data_leak` | JSON dump in response → leak detected |
| `test_confidence_calibrated` | Heuristic scores align with ground truth |

## Definition of Done

- [ ] Multi-signal heuristic detection
- [ ] Improved confidence scoring
- [ ] Calibrated against test corpus
- [ ] All tests pass
