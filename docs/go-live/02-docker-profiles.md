# 02 — Docker Profiles

> **Priority:** Critical | **Effort:** 1–2h | **Dependencies:** 01-mock-provider

---

## Goal

Three `make` targets for three user personas. One `docker-compose.yml` with profiles. No separate compose files.

---

## 1. User personas & targets

```
make demo       GitHub visitor         ~2 min    Mock provider, no Ollama
make up         User evaluating        ~15 min   Full stack with Ollama
make dev        Contributor            —         Infra only, apps run locally
```

---

## 2. Docker Compose profiles

### Profile: `demo` (default for `make demo`)

**Services:** db, redis, proxy-service, agent-demo, frontend
**NOT started:** ollama, langfuse, model-pull

```yaml
services:
  proxy-service:
    profiles: ["demo", "full"]
    environment:
      MODE: demo
    # ...

  agent-demo:
    profiles: ["demo", "full"]
    environment:
      MODE: demo
    # ...

  frontend:
    profiles: ["demo", "full"]
    # ...

  ollama:
    profiles: ["full"]    # NOT in demo
    # ...

  langfuse:
    profiles: ["full"]    # NOT in demo
    # ...
```

### Profile: `full` (default for `make up`)

**Services:** db, redis, ollama, langfuse, proxy-service, agent-demo, frontend, model-pull (init)

### Profile: `dev` (for `make dev`)

NOT a Docker profile — `make dev` starts only infra services by name:
```makefile
dev:
	cd infra && docker compose up db redis ollama langfuse -d
```

This is the existing `make dev-infra` behavior, renamed.

---

## 3. Makefile changes

```makefile
# ── Quick start ─────────────────────────────────────────
# Demo (no Ollama, mock LLM):     make demo
# Full stack (Ollama + real LLM):  make up
# Contributor (infra only):        make dev

demo:
	cd infra && docker compose --profile demo up --build -d
	@echo ""
	@echo "🚀  AI Protector Demo is starting..."
	@echo "    Frontend:       http://localhost:3000"
	@echo "    Proxy API:      http://localhost:8000"
	@echo "    Agent Demo:     http://localhost:8002"
	@echo ""
	@echo "    Mode: DEMO (mock LLM, real security pipeline)"
	@echo "    Paste an API key in Settings to use a real model."

up:
	cd infra && docker compose --profile full up --build -d
	@echo ""
	@echo "🚀  AI Protector is starting (full stack)..."
	@echo "    Frontend:       http://localhost:3000"
	@echo "    Proxy API:      http://localhost:8000"
	@echo "    Agent Demo:     http://localhost:8002"
	@echo "    Langfuse:       http://localhost:3001"
	@echo ""
	@echo "    First time? Run: make pull-model"

init: up pull-model
	@echo ""
	@echo "✅  AI Protector is ready! Open http://localhost:3000"

dev:
	cd infra && docker compose up db redis ollama langfuse -d
	@echo ""
	@echo "🔧  Infrastructure started. Run apps locally:"
	@echo "    cd apps/proxy-service && uvicorn src.main:app --reload --port 8000"
	@echo "    cd apps/agent-demo && uvicorn src.main:app --reload --port 8002"
	@echo "    cd apps/frontend && npm run dev"
```

---

## 4. docker-compose.yml changes

### 4.1 Services without profiles (always start): `db`, `redis`

These are needed by all profiles — keep them profile-free.

### 4.2 Services with profiles:

| Service | Profiles | Notes |
|---------|----------|-------|
| `db` | _(none — always)_ | |
| `redis` | _(none — always)_ | |
| `ollama` | `full` | Not needed in demo |
| `langfuse` | `full` | Nice-to-have, not critical for demo |
| `proxy-service` | `demo`, `full` | `MODE` from env |
| `agent-demo` | `demo`, `full` | `MODE` from env |
| `frontend` | `demo`, `full` | |
| `model-pull` | `init` | Only with `make init` (unchanged) |

### 4.3 MODE env injection

Proxy-service already reads `env_file: .env`. Add `MODE=demo` to `.env`.

For profile-specific override:
```yaml
proxy-service:
  profiles: ["demo", "full"]
  env_file: .env
  environment:
    MODE: ${MODE:-demo}  # Can be overridden, defaults to demo
```

This lets `make demo` work with default (MODE=demo) and `make up` can set `MODE=real`:
```makefile
up:
	cd infra && MODE=real docker compose --profile full up --build -d
```

---

## 5. .env / .env.example update

```env
# ── Mode ───────────────────────────────────────────────
# demo = mock LLM responses, real security pipeline, no Ollama needed
# real = full stack with Ollama or external providers
MODE=demo

# ── API Keys (optional, override mock in any mode) ─────
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...

# ── PostgreSQL ─────────────────────────────────────────
# ... (existing, unchanged)
```

---

## 6. Health check adjustment

In demo profile, `ollama` is not started. The health endpoint currently checks Ollama and would report `degraded`. 

**Fix:** In demo mode, skip Ollama health check or report it as `"skipped"`:
```python
if settings.mode == "demo":
    services["ollama"] = ServiceHealth(status="skipped", latency_ms=0)
else:
    services["ollama"] = await _check_ollama(settings.ollama_base_url)
```

Same for Langfuse if not started.

---

## 7. Files to modify

| File | Change |
|------|--------|
| `infra/docker-compose.yml` | Add `profiles` to services, `MODE` env |
| `Makefile` | New `demo`, `up` targets; rename existing `dev` |
| `infra/.env` | Add `MODE=demo` |
| `infra/.env.example` | Add `MODE=demo` + API key placeholders |
| `apps/proxy-service/src/routers/health.py` | Skip Ollama/Langfuse check in demo mode |

---

## 8. Test plan

| Test | What to verify |
|------|---------------|
| `make demo` | Starts db + redis + proxy + agent + frontend. No Ollama. Healthy. |
| `make up` | Starts full stack including Ollama + Langfuse. |
| `make dev` | Starts only db + redis + ollama + langfuse. |
| Health in demo | `/health` returns `ok` without Ollama. |
| MODE override | `MODE=real make demo` → fails gracefully (Ollama not available). |
