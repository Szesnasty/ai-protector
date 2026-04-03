# 08 — Error States

> **Layer:** Full-stack
> **Phase:** 2 (Custom Endpoints) — MVP
> **Depends on:** All Phase 2 specs

## Scope

Every error state has a defined UI treatment. No silent failures. Covers: target configuration errors, run errors, result edge cases.

## Implementation Steps

### Step 1: Target configuration errors (Test Connection)

| Error | Condition | UI Treatment |
|-------|-----------|-------------|
| **Connection failed** | Target not reachable | Red banner: "Cannot reach `{url}`. Check the URL and make sure your service is running." Disable [Continue]. |
| **Auth invalid** | HTTP 401/403 | Red banner: "Authentication failed (HTTP {status}). Check your Bearer token or API key." |
| **Timeout** | No response in 10s | Red banner: "Connection timed out. Try increasing the timeout in Advanced settings." |
| **Non-JSON response** | Content-type ≠ JSON | Yellow warning: "Endpoint returned `{type}` instead of JSON. Benchmark may have limited accuracy. Continue anyway?" Allow [Continue]. |
| **SSL error** | Certificate issue | Red banner: "SSL certificate error. If this is a self-signed cert, check your environment configuration." |

### Step 2: Run errors (Progress Screen)

| Error | Condition | UI Treatment |
|-------|-----------|-------------|
| **Target unreachable mid-run** | 3 consecutive failures | Progress bar turns red. "Target stopped responding after {N}/{total}. Partial results saved." [View Partial Results] |
| **Scenario timeout** | Exceeds timeout_s | Scenario row: ⏱️ "Timeout — skipped". Run continues. |
| **Run cancelled** | User cancels | "Run cancelled. {N} of {total} completed." [View Partial Results] |
| **Internal error** | Server error | Red banner: "Something went wrong. Partial results saved. Try again." + error ID |

### Step 3: Result edge cases

| Case | UI Treatment |
|------|-------------|
| **All skipped** | No score badge. "No scenarios were applicable. Try disabling Safe mode or a different pack." |
| **Very few executed** (< 5) | Score badge + yellow notice: "Score based on only {N} scenarios. May not be representative." |
| **Partial results** | Score badge + note: "Partial score — {N} of {total} completed." |

### Step 4: Backend error responses

- Structured error format:
  ```json
  { "error": { "code": "connection_failed", "message": "...", "details": {...} } }
  ```
- Error codes: `connection_failed`, `auth_invalid`, `timeout`, `ssl_error`, `run_conflict`, `not_found`, `internal_error`

### Step 5: Frontend error handling

- Global error interceptor for API calls
- Per-component error states (banners, dialogs)
- Retry buttons where applicable
- Never show raw error messages or stack traces to user

## Tests

| Test | What it verifies |
|------|-----------------|
| `test_connection_failed_banner` | Unreachable URL → red banner |
| `test_auth_invalid_banner` | 401 → auth error banner |
| `test_timeout_banner` | Timeout → timeout banner |
| `test_non_json_warning` | Non-JSON → yellow warning (not blocking) |
| `test_ssl_error_banner` | SSL error → ssl banner |
| `test_mid_run_failure_ui` | 3 failures → red progress bar + view partial |
| `test_scenario_timeout_continues` | Single timeout → ⏱️ row, run continues |
| `test_all_skipped_no_score` | No executed scenarios → no score badge |
| `test_few_executed_warning` | < 5 executed → yellow warning |
| `test_partial_results_display` | Cancelled run → partial score shown |
| `test_error_response_format` | Backend errors follow structured format |

## Definition of Done

- [ ] All error states from spec have defined UI treatments
- [ ] Backend returns structured error responses
- [ ] Frontend renders appropriate banners/dialogs for each error
- [ ] No silent failures — every error is visible to the user
- [ ] Partial results always accessible after failures
- [ ] All tests pass
