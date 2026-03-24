# 03 — PDF Export

> **Layer:** Full-stack
> **Phase:** 4 (Advanced)
> **Depends on:** JSON + Markdown exports (Phase 3)

## Scope

Branded PDF report suitable for sharing with stakeholders, compliance teams, and management.

## Implementation Steps

### Step 1: PDF template

- Branded header with AI Protector logo
- Executive summary, score badge, category breakdown charts
- Top failures with details
- Appendix: full scenario list

### Step 2: Chart rendering

- Score gauge chart
- Category breakdown bar charts
- Before/After comparison (if applicable)

### Step 3: Export endpoint

- `POST /v1/benchmark/runs/:id/export` with `{ format: "pdf" }`
- Generate PDF server-side (WeasyPrint, ReportLab, or similar)

## Tests

| Test | What it verifies |
|------|-----------------|
| `test_pdf_generates` | Valid PDF file produced |
| `test_pdf_contains_score` | Score visible in PDF |
| `test_pdf_charts_render` | Charts render correctly |

## Definition of Done

- [ ] Branded PDF with all sections
- [ ] Charts render correctly
- [ ] Download works from frontend
- [ ] All tests pass
