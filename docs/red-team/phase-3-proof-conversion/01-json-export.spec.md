# 01 — JSON Export

> **Layer:** Full-stack
> **Phase:** 3 (Proof & Conversion)
> **Depends on:** MVP complete (Phase 0–2)

## Scope

Export benchmark results + metadata as a downloadable JSON file.

## Implementation Steps

### Step 1: Backend export endpoint

- `POST /v1/benchmark/runs/:id/export` → generates JSON report
- Body: `{ format: "json", include_raw_responses?: false }`
- Returns: JSON file or download URL

### Step 2: Export content structure

```json
{
  "export_version": "1.0",
  "generated_at": "...",
  "run": { /* full BenchmarkRun fields */ },
  "scores": { "simple": 61, "weighted": 72, "breakdown": {...} },
  "scenarios": [
    { "id": "CS-001", "passed": true, "actual": "BLOCK", "detector_detail": {...}, "latency_ms": 120 }
  ],
  "summary": { "total": 30, "passed": 27, "failed": 3, "skipped": 0 }
}
```

### Step 3: Optional raw response inclusion

- Default: raw responses excluded (privacy)
- `include_raw_responses: true` → includes `prompt` + `response_body` per scenario
- Frontend: checkbox "Include full responses — may contain sensitive data"

### Step 4: Frontend download

- [Export Report] button on results page
- Click → calls export endpoint → browser download as `red-team-report-{run_id}.json`

## Tests

| Test | What it verifies |
|------|-----------------|
| `test_export_json_structure` | Exported JSON matches schema |
| `test_export_excludes_raw_by_default` | No raw responses without opt-in |
| `test_export_includes_raw_on_opt_in` | Raw responses included when requested |
| `test_export_no_auth_secrets` | Auth secrets never in export |
| `test_frontend_downloads_file` | Click → file downloaded |

## Definition of Done

- [ ] JSON export with full run data (minus auth secrets)
- [ ] Optional raw response inclusion
- [ ] Frontend download button works
- [ ] All tests pass
