# Phase 1 — Vertical Slice: Demo Agent [MVP]

> **Goal:** Prove the full loop end-to-end on one controlled target. First time UI and backend connect.

## Specs

| # | Spec | Layer | Status |
|---|------|-------|--------|
| 01 | [API Routes](01-api-routes.spec.md) | Backend | ✅ done |
| 02 | [Frontend Landing](02-frontend-landing.spec.md) | Frontend | ✅ done |
| 03 | [Frontend Configure](03-frontend-configure.spec.md) | Frontend | ✅ done |
| 04 | [Frontend Progress](04-frontend-progress.spec.md) | Frontend | ✅ done |
| 05 | [Frontend Results](05-frontend-results.spec.md) | Frontend | ✅ done |
| 06 | [Frontend Scenario Detail](06-frontend-scenario-detail.spec.md) | Frontend | ✅ done |
| 07 | [CTA + Re-run + Before/After](07-cta-rerun-before-after.spec.md) | Full-stack | ✅ done |

## What is NOT in Phase 1

- No custom endpoints (Local Agent / Hosted Endpoint)
- No auth handling
- No error states (demo agent is controlled — it always works)
- No safe mode (demo agent = safe by definition)

## Phase-level Definition of Done

New user → Demo Agent → 3 clicks → score → drill into failure → apply fix → re-run → Before/After shows improvement. **This is the heart of the product working.**
