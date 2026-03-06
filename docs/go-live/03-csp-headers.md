# 03 — CSP & Security Headers

> **Priority:** Important | **Effort:** 1–2h | **Dependencies:** none (independent)

---

## Goal

Add Content Security Policy and security headers to the frontend via a Nuxt server middleware. CSP `connect-src` is built dynamically from `runtimeConfig` (env vars) so it adapts to deployment without rebuild.

---

## 1. Architecture

**Server middleware** (runs on every request, SSR + client navigation):

```
apps/frontend/server/middleware/security-headers.ts
```

Nuxt server middleware = zero npm dependencies. No `nuxt-security` module needed.

---

## 2. CSP Policy

### 2.1 Dynamic sources (from runtimeConfig / .env)

| Source | Env var | Default | Used by |
|--------|---------|---------|---------|
| Proxy API | `NUXT_PUBLIC_API_BASE` | `http://localhost:8000` | Playground, policies, analytics |
| Agent API | `NUXT_PUBLIC_AGENT_API_BASE` | `http://localhost:8002` | Agent demo page |

### 2.2 Static provider allowlist

These are the known external LLM provider APIs that the **compare page** calls directly from the browser:

```
https://api.openai.com
https://api.anthropic.com
https://api.mistral.ai
https://generativelanguage.googleapis.com
```

These are hardcoded — provider domains don't change. Adding a new provider = code change anyway (new detection rule in `providers.py`), so update CSP at the same time.

### 2.3 WebSocket sources

Streaming uses `fetch()` with `ReadableStream`, NOT WebSockets. No `ws://` needed in CSP.

Nuxt dev mode HMR uses WebSockets on `/_nuxt/`. This is dev-only — the middleware should detect dev mode and add `ws:` accordingly.

### 2.4 Full policy

```
default-src 'self';
script-src 'self' 'unsafe-inline';
style-src 'self' 'unsafe-inline';
font-src 'self' data:;
img-src 'self' data: blob:;
connect-src 'self' {PROXY_API} {AGENT_API} https://api.openai.com https://api.anthropic.com https://api.mistral.ai https://generativelanguage.googleapis.com;
frame-ancestors 'none';
base-uri 'self';
form-action 'self';
```

**Notes:**
- `'unsafe-inline'` for script-src: Nuxt injects inline scripts for hydration. Alternative is `'nonce-...'` but requires Nuxt module config. `unsafe-inline` is acceptable for a self-hosted tool (not a bank).
- `'unsafe-inline'` for style-src: Vuetify dynamically injects inline styles. Required.
- `data:` for font-src: MDI icons load as data URIs.
- `blob:` for img-src: ECharts may render charts as blob URLs.

---

## 3. Other security headers

| Header | Value | Purpose |
|--------|-------|---------|
| `X-Frame-Options` | `DENY` | Prevent clickjacking |
| `X-Content-Type-Options` | `nosniff` | Prevent MIME-type sniffing |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Limit referrer leakage |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=(), payment=()` | Disable unused APIs |
| `X-XSS-Protection` | `0` | Disabled — CSP replaces it; old browsers' XSS filter can cause issues |

---

## 4. Implementation

### 4.1 `server/middleware/security-headers.ts`

```typescript
export default defineEventHandler((event) => {
  const config = useRuntimeConfig()

  const apiBase: string = config.public.apiBase || 'http://localhost:8000'
  const agentBase: string = config.public.agentApiBase || 'http://localhost:8002'

  // Known external LLM provider APIs (for compare page direct calls)
  const providerApis = [
    'https://api.openai.com',
    'https://api.anthropic.com',
    'https://api.mistral.ai',
    'https://generativelanguage.googleapis.com',
  ].join(' ')

  // Dev mode: allow HMR WebSocket
  const isDev = import.meta.dev
  const devSources = isDev ? ' ws://localhost:3000 ws://localhost:24678' : ''

  const connectSrc = `'self' ${apiBase} ${agentBase} ${providerApis}${devSources}`

  const csp = [
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline'",
    "style-src 'self' 'unsafe-inline'",
    "font-src 'self' data:",
    "img-src 'self' data: blob:",
    `connect-src ${connectSrc}`,
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
  ].join('; ')

  setHeaders(event, {
    'Content-Security-Policy': csp,
    'X-Frame-Options': 'DENY',
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'Permissions-Policy': 'camera=(), microphone=(), geolocation=(), payment=()',
    'X-XSS-Protection': '0',
  })
})
```

### 4.2 No changes needed in nuxt.config.ts

The server middleware is auto-registered by Nuxt (file-based convention in `server/middleware/`).

---

## 5. CORS on backend (related)

Frontend sends requests to proxy-service (port 8000) and agent-demo (port 8002). These are cross-origin from `localhost:3000`.

**Current state:** FastAPI likely has permissive CORS (`allow_origins=["*"]`). This should be tightened:

```python
# proxy-service/src/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",   # Frontend dev
        "http://frontend:3000",    # Frontend in Docker network
    ],
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "x-client-id", "x-policy", "x-api-key", "x-correlation-id"],
    expose_headers=["x-decision", "x-risk-score", "x-intent", "x-request-id"],
)
```

**Note:** This is optional for go-live (CORS on localhost is less critical than CSP), but a good hardening step.

---

## 6. Files to create / modify

### New files:
| File | Purpose |
|------|---------|
| `apps/frontend/server/middleware/security-headers.ts` | CSP + security headers |

### Modified files (optional hardening):
| File | Change |
|------|--------|
| `apps/proxy-service/src/main.py` | Tighten CORS origins |
| `apps/agent-demo/src/main.py` | Tighten CORS origins |

---

## 7. Test plan

| Test | What to verify |
|------|---------------|
| Browser DevTools → Network → Response Headers | CSP header present on all pages |
| Playground chat | `fetch()` to `:8000` succeeds (in connect-src) |
| Agent demo chat | `fetch()` to `:8002` succeeds (in connect-src) |
| Compare page (direct call) | `fetch()` to `api.openai.com` succeeds (if key provided) |
| Inject `<script>` in prompt display | CSP blocks inline execution (though app doesn't render raw HTML) |
| iframe embed attempt | `X-Frame-Options: DENY` prevents embedding |
| DevTools Console | No CSP violation warnings during normal usage |
