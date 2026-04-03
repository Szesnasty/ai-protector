# Phase 2 — Custom Endpoints (Real Adoption) [MVP]

> **Goal:** Users test their own endpoints. This is where real-world value begins.

## Specs

| # | Spec | Layer | Status |
|---|------|-------|--------|
| 01 | [Target Configuration Form](01-target-configuration-form.spec.md) | Frontend | ✅ done |
| 02 | [Test Connection](02-test-connection.spec.md) | Full-stack | not started |
| 03 | [Auth Secret Handling](03-auth-secret-handling.spec.md) | Backend | not started |
| 04 | [Safe Mode Filtering](04-safe-mode-filtering.spec.md) | Backend | not started |
| 05 | [Heuristic Evaluators](05-heuristic-evaluators.spec.md) | Backend | not started |
| 06 | [Frontend Target Cards](06-frontend-target-cards.spec.md) | Frontend | not started |
| 07 | [CTA Protection Paths](07-cta-protection-paths.spec.md) | Frontend | not started |
| 08 | [Error States](08-error-states.spec.md) | Full-stack | not started |

## Phase-level Definition of Done

User provides `http://localhost:8080/chat` → Core Security → score → sees CTA to protect → proxy → re-run → improvement. Hosted endpoint with auth also works.
