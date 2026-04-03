# 02 — Test Connection

> **Layer:** Full-stack
> **Phase:** 2 (Custom Endpoints) — MVP
> **Depends on:** Target form (Phase 2, step 01), HTTP Client (Phase 0)

## Scope

The [Test Connection] button verifies the target is reachable before starting a run. Backend endpoint that pings the target and returns status.

## Implementation Steps

### Step 1: Backend endpoint

```
POST /v1/benchmark/test-connection
Body: { endpoint_url, auth_header?, timeout_s? }
Response: { status: "ok" | "error", status_code?, latency_ms?, content_type?, error? }
```

### Step 2: Backend implementation

- Use HTTP Client module to send a simple health check (GET or POST with empty prompt)
- Measure latency
- Capture: HTTP status code, content-type header, latency
- On success: `{ status: "ok", status_code: 200, latency_ms: 340, content_type: "application/json" }`
- On failure: `{ status: "error", error: "Connection refused" | "Timeout" | "SSL error" | "HTTP 401" }`

### Step 3: Auth handling (temporary)

- Auth header is sent to the backend for the test only
- Backend does NOT persist the auth at this point
- Auth value is only held in memory for the duration of the request

### Step 4: Frontend integration

- [Test Connection] button calls the endpoint
- Loading state during request
- Success: green banner "✅ 200 OK │ 340ms │ AI Protector can reach your endpoint"
- Failure: red/yellow banner with specific error message (see error states spec)
- Non-JSON warning: yellow banner "Endpoint returned {content-type} instead of JSON. Continue anyway?"

### Step 5: Enable [Continue] on success

- [Continue] button disabled until test passes
- User can retry [Test Connection] after fixing issues
- Non-JSON warning still allows [Continue] (but with warning)

## Tests

| Test | What it verifies |
|------|-----------------|
| `test_connection_ok` | Reachable target → `{ status: "ok", ... }` |
| `test_connection_timeout` | Unreachable target → `{ status: "error", error: "Timeout" }` |
| `test_connection_auth_failure` | 401 → `{ status: "error", error: "HTTP 401" }` |
| `test_connection_ssl_error` | Bad cert → `{ status: "error", error: "SSL error" }` |
| `test_connection_non_json` | HTML response → ok but `content_type: "text/html"` |
| `test_auth_not_persisted` | Auth header not written to DB during test |
| `test_frontend_success_banner` | OK → green banner with latency |
| `test_frontend_error_banner` | Error → red banner with message |
| `test_continue_enabled_after_success` | Success → [Continue] enabled |

## Definition of Done

- [ ] Backend endpoint tests target connectivity
- [ ] Returns structured result with status, latency, content-type
- [ ] Auth handled securely (in-memory only)
- [ ] Frontend displays appropriate success/error banners
- [ ] [Continue] gated on successful test
- [ ] All tests pass
