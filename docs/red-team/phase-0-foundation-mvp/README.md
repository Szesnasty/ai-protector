# Phase 0 — Foundation (Backend Engine) [MVP]

> **Goal:** Build the engine that everything else rests on. No UI. Fully testable in isolation.

## Modules

| # | Spec | Module | Status |
|---|------|--------|--------|
| 01 | [Scenario Schema](01-scenario-schema.spec.md) | `red-team/schemas/` | not started |
| 02 | [Pack Loader](02-pack-loader.spec.md) | `red-team/packs/` | not started |
| 03 | [Evaluator Engine](03-evaluator-engine.spec.md) | `red-team/evaluators/` | not started |
| 04 | [Score Calculator](04-score-calculator.spec.md) | `red-team/scoring/` | not started |
| 05 | [Run Engine](05-run-engine.spec.md) | `red-team/engine/` | not started |
| 06 | [Persistence](06-persistence.spec.md) | `red-team/persistence/` | not started |
| 07 | [Progress Emitter](07-progress-emitter.spec.md) | `red-team/progress/` | not started |
| 08 | [HTTP Client](08-http-client.spec.md) | `red-team/engine/http_client` | not started |

## Dependency order

```
Scenario Schema → Pack Loader → Evaluator Engine → Score Calculator
                                                  ↘
HTTP Client ─────────────────────────────────────→ Run Engine → Persistence
                                                              → Progress Emitter
```

## Phase-level Definition of Done

- `pytest` passes with >90% coverage on all engine modules
- A run can be executed **programmatically** (no UI, no API) against a mock target
- Every evaluator is unit-tested with deterministic inputs/outputs
- Pack loading + filtering is tested for all filtering rules
- Score calculation matches the weighted formula from the spec
- Run lifecycle state machine is verified (created → running → completed/failed/cancelled)
