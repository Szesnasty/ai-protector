# Step 03 — Proxy Service Foundation

| | |
|---|---|
| **Phase** | Foundation |
| **Estimated time** | 4–6 hours |
| **Prev** | [Step 02 — Infrastructure](../02-infrastructure/SPEC.md) |
| **Next** | Step 04 — Basic LLM Proxy *(spec not yet created)* |
| **Master plan** | [MVP-PLAN.md](../MVP-PLAN.md) |

---

## Goal

Build the FastAPI application skeleton for the proxy service: configuration, database models, migrations, seed data, health endpoint, structured logging, and a working Dockerfile — everything needed before we add the actual firewall pipeline or LLM proxy logic.

---

## Tasks

### 1. Application structure

- [x] Create the package layout:
  ```
  apps/proxy-service/
  ├── src/
  │   ├── __init__.py
  │   ├── main.py              # FastAPI app factory
  │   ├── config.py            # Pydantic Settings
  │   ├── dependencies.py      # Dependency injection (db session, redis)
  │   ├── models/
  │   │   ├── __init__.py
  │   │   ├── base.py          # SQLAlchemy DeclarativeBase
  │   │   ├── policy.py        # Policy model
  │   │   ├── request.py       # Request log model
  │   │   └── denylist.py      # DenylistPhrase model
  │   ├── schemas/
  │   │   ├── __init__.py
  │   │   ├── policy.py        # Pydantic schemas for Policy CRUD
  │   │   ├── request.py       # Pydantic schemas for Request log
  │   │   └── health.py        # Health response schema
  │   ├── routers/
  │   │   ├── __init__.py
  │   │   └── health.py        # GET /health
  │   ├── db/
  │   │   ├── __init__.py
  │   │   ├── session.py       # AsyncSession factory
  │   │   └── seed.py          # Seed default policies
  │   └── logging.py           # Structlog configuration
  ├── alembic/
  │   ├── alembic.ini
  │   ├── env.py
  │   └── versions/            # Migration files
  ├── tests/
  │   ├── __init__.py
  │   └── test_health.py
  ├── pyproject.toml
  └── Dockerfile
  ```

### 2. Configuration (`src/config.py`)

- [x] Pydantic `BaseSettings` with:
  ```python
  class Settings(BaseSettings):
      # Database
      database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_protector"

      # Redis
      redis_url: str = "redis://localhost:6379/0"

      # Ollama / LLM
      ollama_base_url: str = "http://localhost:11434"
      default_model: str = "llama3.1:8b"

      # Langfuse
      langfuse_host: str = "http://localhost:3001"
      langfuse_public_key: str = "pk-lf-local"
      langfuse_secret_key: str = "sk-lf-local"

      # App
      default_policy: str = "balanced"
      log_level: str = "INFO"

      model_config = SettingsConfigDict(env_file=".env")
  ```
- [x] Singleton pattern via `@lru_cache`

### 3. Database models (`src/models/`)

- [x] `base.py`: `DeclarativeBase` with UUID primary key mixin
- [x] `policy.py`: `Policy` model matching the SQL schema from MVP.spec.md
  - id (UUID), name, description, config (JSONB), is_active, version, created_at, updated_at
- [x] `request.py`: `Request` model
  - id, client_id, policy_id (FK), intent, prompt_hash, prompt_preview, decision, risk_flags (JSONB), risk_score, latency_ms, model_used, tokens_in, tokens_out, blocked_reason, response_masked, created_at
- [x] `denylist.py`: `DenylistPhrase` model
  - id, policy_id (FK, cascade), phrase, category, is_regex, created_at

### 4. Database session (`src/db/session.py`)

- [x] `create_async_engine()` with pool settings
- [x] `async_sessionmaker` for creating sessions
- [x] `get_db()` async generator for FastAPI dependency injection
- [x] Redis client factory (`get_redis()`)

### 5. Alembic setup

- [x] Initialize Alembic: `alembic init alembic`
- [x] Configure `alembic/env.py` for async SQLAlchemy
- [x] Set `sqlalchemy.url` from `Settings.database_url`
- [x] Generate initial migration: `alembic revision --autogenerate -m "initial schema"`
- [x] Verify: `alembic upgrade head` creates all 3 tables + indexes

### 6. Seed data (`src/db/seed.py`)

- [x] Create 4 default policies:
  ```python
  DEFAULT_POLICIES = [
      {
          "name": "fast",
          "description": "Minimal checks — rules only. High throughput, trusted clients.",
          "config": {
              "nodes": ["parse", "intent", "rules", "decision", "llm", "basic_output", "logging"],
              "thresholds": {"max_risk": 0.9}
          }
      },
      {
          "name": "balanced",
          "description": "Default — rules + LLM Guard + output filter + memory hygiene.",
          "config": {
              "nodes": ["parse", "intent", "rules", "llm_guard", "decision", "transform", "llm", "output_filter", "memory_hygiene", "logging"],
              "thresholds": {"max_risk": 0.7, "injection_threshold": 0.5}
          }
      },
      {
          "name": "strict",
          "description": "Full pipeline — adds Presidio PII + ML Judge.",
          "config": {
              "nodes": ["parse", "intent", "rules", "llm_guard", "presidio", "ml_judge", "decision", "transform", "llm", "output_filter", "memory_hygiene", "logging"],
              "thresholds": {"max_risk": 0.5, "injection_threshold": 0.3, "pii_action": "mask"}
          }
      },
      {
          "name": "paranoid",
          "description": "Maximum security — canary tokens + full audit logging.",
          "config": {
              "nodes": ["parse", "intent", "rules", "llm_guard", "presidio", "ml_judge", "decision", "canary", "transform", "llm", "output_filter", "memory_hygiene", "logging"],
              "thresholds": {"max_risk": 0.3, "injection_threshold": 0.2, "pii_action": "block", "enable_canary": true}
          }
      }
  ]
  ```
- [x] Idempotent: skip if policies already exist (upsert by name)
- [x] Run on app startup (lifespan event)

### 7. Health endpoint (`src/routers/health.py`)

- [x] `GET /health` returns:
  ```json
  {
      "status": "ok",
      "services": {
          "db": "ok",
          "redis": "ok",
          "ollama": "ok",
          "langfuse": "ok"
      },
      "version": "0.1.0"
  }
  ```
- [x] Each service check:
  - **db**: `SELECT 1` via async session
  - **redis**: `PING` via aioredis
  - **ollama**: `GET {ollama_base_url}/api/tags` via httpx
  - **langfuse**: `GET {langfuse_host}/api/public/health` via httpx
- [x] If a service is down → `"status": "degraded"`, service shows `"error": "..."`
- [x] Response model: `HealthResponse` Pydantic schema

### 8. Structured logging (`src/logging.py`)

- [x] Configure Structlog with:
  - JSON renderer (production) / ConsoleRenderer (dev)
  - Processors: timestamp, log level, caller info, request correlation ID
  - Integration with uvicorn access logs
- [x] Add middleware to inject `correlation_id` (UUID) into every request

### 9. FastAPI app (`src/main.py`)

- [x] App factory with lifespan:
  ```python
  @asynccontextmanager
  async def lifespan(app: FastAPI):
      # Startup
      await run_migrations()  # or just verify DB connection
      await seed_policies()
      yield
      # Shutdown
      await close_db()
      await close_redis()
  ```
- [x] Include routers: `/health`
- [x] CORS middleware (allow frontend origin)
- [x] Request correlation ID middleware
- [x] OpenAPI metadata (title, description, version)

### 10. Dockerfile

- [x] Multi-stage build:
  ```dockerfile
  # Stage 1: Builder
  FROM python:3.12-slim AS builder
  WORKDIR /app
  COPY pyproject.toml .
  RUN pip install --no-cache-dir .

  # Stage 2: Runtime
  FROM python:3.12-slim
  WORKDIR /app
  COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
  COPY --from=builder /usr/local/bin /usr/local/bin
  COPY src/ src/
  COPY alembic/ alembic/
  COPY alembic.ini .
  EXPOSE 8000
  CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
  ```

### 11. First test

- [x] `tests/test_health.py`:
  ```python
  async def test_health_endpoint(client):
      response = await client.get("/health")
      assert response.status_code == 200
      data = response.json()
      assert data["status"] in ("ok", "degraded")
  ```
- [x] Configure `pytest` with `httpx.AsyncClient` + `TestClient`

---

## Technical Decisions

### Why Pydantic Settings (not dotenv)?
Pydantic Settings validates types, has defaults, supports `.env` files, and integrates natively with FastAPI's dependency injection. One source of truth for config.

### Why seed on startup?
The 4 default policies must exist for the proxy to work. Seeding on startup (idempotent upsert) means `docker compose up` gives you a working system immediately — no manual SQL scripts.

### Why correlation ID middleware?
Every request gets a UUID that flows through all logs, Langfuse traces, and DB records. Essential for debugging request flows across the pipeline nodes.

---

## Definition of Done

- [x] `cd apps/proxy-service && uvicorn src.main:app` → starts on :8000
- [x] `GET /health` → returns JSON with status + all 4 service checks
- [x] `alembic upgrade head` → creates `policies`, `requests`, `denylist_phrases` tables
- [x] `SELECT * FROM policies` → 4 default policies (fast, balanced, strict, paranoid)
- [x] Structlog outputs JSON logs with correlation_id
- [x] `ruff check src/` → 0 errors
- [x] `pytest tests/` → test_health passes
- [x] Dockerfile builds: `docker build -t ai-protector-proxy .`
- [x] Uncomment `proxy-service` in docker-compose.yml → service starts and connects to DB

---

| **Prev** | **Next** |
|---|---|
| [Step 02 — Infrastructure](../02-infrastructure/SPEC.md) | Step 04 — Basic LLM Proxy *(coming next)* |
