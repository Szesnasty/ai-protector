# 07 — Auto "Why It Passed"

> **Layer:** Backend
> **Phase:** 4 (Advanced)
> **Depends on:** Evaluator Engine, Pipeline integration

## Scope

Automatically generate "Why it passed/failed" explanations from scanner results instead of relying on static descriptions in scenario metadata.

## Implementation Steps

### Step 1: Scanner result analysis

- Parse `pipeline_result` (scanner scores, matched patterns, thresholds)
- Identify which scanner came closest to blocking (but didn't)

### Step 2: Explanation templates

- Template-based generation: "The attack passed because {scanner} scored {score}, which is below the threshold of {threshold}."
- Multiple explanation patterns for different failure modes

### Step 3: Actionable explanation

- Not just "why" but "what would fix it":
  - "Lowering {scanner} threshold from 0.5 to 0.3 would have blocked this"
  - "Adding keyword '{word}' to blocklist would catch this pattern"

### Step 4: Fallback to static

- If auto-generation fails → use scenario's static `why_it_passes` field
- Never show empty explanation

## Tests

| Test | What it verifies |
|------|-----------------|
| `test_auto_explanation_generated` | Pipeline result → explanation text |
| `test_explanation_actionable` | Fix suggestion included |
| `test_fallback_to_static` | No pipeline data → static explanation |

## Definition of Done

- [ ] Auto-generated explanations from pipeline results
- [ ] Actionable fix suggestions
- [ ] Graceful fallback to static descriptions
- [ ] All tests pass
