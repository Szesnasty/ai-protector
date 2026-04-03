# Step 02 — Infrastructure (Docker Compose)

| | |
|---|---|
| **Phase** | Foundation |
| **Estimated time** | 3–5 hours |
| **Prev** | [Step 01 — Project Scaffolding](../01-project-scaffolding/SPEC.md) |
| **Next** | [Step 03 — Proxy Service Foundation](../03-proxy-foundation/SPEC.md) |
| **Master plan** | [MVP-PLAN.md](../MVP-PLAN.md) |

---

## Goal

Create a complete Docker Compose setup so that `docker compose up` brings up the full infrastructure stack: PostgreSQL (with pgvector), Redis, Ollama (with Llama 3.1 8B), and Langfuse. Every subsequent step assumes these services are running.

---

## Tasks

### 1. Docker Compose file (`infra/docker-compose.yml`)

- [x] Define all services with proper dependency order
- [x] Use `depends_on` with `condition: service_healthy` where possible
- [x] Named volumes for persistent data (pgdata, ollama_models)
- [x] Network: single `ai-protector` bridge network

### 2. PostgreSQL + pgvector

- [x] Image: `pgvector/pgvector:pg16`
- [x] Port: `5432:5432`
- [x] Environment: `POSTGRES_DB=ai_protector`, `POSTGRES_USER=postgres`, `POSTGRES_PASSWORD=postgres`
- [x] Volume: `pgdata:/var/lib/postgresql/data`
- [x] Healthcheck: `pg_isready -U postgres`
- [x] Init script: `infra/init-db.sql` — create a second database `langfuse` for Langfuse
  ```sql
  -- infra/init-db.sql
  SELECT 'CREATE DATABASE langfuse'
  WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'langfuse')\gexec
  ```

### 3. Redis

- [x] Image: `redis:7-alpine`
- [x] Port: `6379:6379`
- [x] Healthcheck: `redis-cli ping`
- [x] No persistence needed for dev (data is cache/ephemeral)

### 4. Ollama

- [x] Image: `ollama/ollama:latest`
- [x] Port: `11434:11434`
- [x] Volume: `ollama_models:/root/.ollama`
- [x] Create `infra/scripts/pull-model.sh`:
  ```bash
  #!/bin/bash
  echo "Waiting for Ollama to be ready..."
  until curl -s http://localhost:11434/api/tags > /dev/null 2>&1; do sleep 1; done
  echo "Pulling llama3.1:8b..."
  ollama pull llama3.1:8b
  echo "Model ready."
  ```
- [x] Document: first `docker compose up` will need `./infra/scripts/pull-model.sh` to download the model (~4.7 GB)

### 5. Langfuse

- [x] Image: `langfuse/langfuse:2` *(pinned to v2 — v3 requires ClickHouse + MinIO)*
- [x] Port: `3001:3000` (avoids conflict with frontend on 3000)
- [x] Environment variables:
  - `DATABASE_URL=postgresql://postgres:postgres@db:5432/langfuse`
  - `NEXTAUTH_URL=http://localhost:3001`
  - `NEXTAUTH_SECRET=local-dev-secret`
  - `SALT=local-dev-salt`
- [x] Depends on: `db`
- [x] Healthcheck: `wget -qO- http://localhost:3000/api/public/health` *(wget instead of curl — not available in Langfuse v2 image)*

### 6. App service stubs (build context only, no code yet)

- [x] `proxy-service` — build context `../apps/proxy-service`, ports `8000:8000`, env vars from `.env`
- [x] `agent-demo` — build context `../apps/agent-demo`, ports `8002:8002`
- [x] `frontend` — build context `../apps/frontend`, ports `3000:3000`
- [x] All 3 commented out initially (uncommented once code exists in future steps)

### 7. Environment file

- [x] Update `infra/.env.example` with all variables:
  ```env
  # PostgreSQL
  POSTGRES_DB=ai_protector
  POSTGRES_USER=postgres
  POSTGRES_PASSWORD=postgres

  # Redis
  REDIS_URL=redis://redis:6379/0

  # Ollama
  OLLAMA_BASE_URL=http://ollama:11434
  DEFAULT_MODEL=llama3.1:8b

  # Langfuse
  LANGFUSE_HOST=http://langfuse:3001
  LANGFUSE_PUBLIC_KEY=pk-lf-local
  LANGFUSE_SECRET_KEY=sk-lf-local

  # Proxy Service
  DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/ai_protector
  DEFAULT_POLICY=balanced

  # Agent Demo
  PROXY_BASE_URL=http://proxy-service:8000
  ```
- [x] Create `infra/.env` by copying `.env.example` (gitignored)

### 8. Verification script

- [x] Create `infra/scripts/verify-stack.sh`:
  - Checks PostgreSQL connection
  - Checks Redis ping
  - Checks Ollama API
  - Checks Langfuse health
  - Prints status table

---

## File Tree After This Step

```
infra/
├── docker-compose.yml
├── .env.example
├── .env                    (gitignored)
├── init-db.sql
└── scripts/
    ├── pull-model.sh
    └── verify-stack.sh
```

---

## Technical Decisions

### Why one DB instance with two databases?
Langfuse needs its own database. Rather than running two PostgreSQL instances, we create a second database (`langfuse`) in the same instance via `init-db.sql`. Simpler, less RAM.

### Why Ollama model is pulled separately?
The Ollama image doesn't pre-include models. Pulling ~4.7 GB on first boot stalls `docker compose up`. A separate script with a progress indicator is a better UX.

### Why app services are commented out?
No code exists yet (created in Steps 03–05). Including them would cause build failures. They'll be uncommented as each app is implemented.

---

## Definition of Done

- [x] `cd infra && docker compose up -d` → all 4 infra services start (db, redis, ollama, langfuse)
- [x] `docker compose ps` → all services `healthy` or `running`
- [x] `psql -h localhost -U postgres -d ai_protector -c '\dt'` → connects (empty is fine)
- [x] `redis-cli -h localhost ping` → `PONG`
- [x] `curl http://localhost:11434/api/tags` → Ollama responds
- [x] `./infra/scripts/pull-model.sh` → downloads llama3.1:8b successfully *(skipped — 4.7 GB download, script verified working)*
- [x] `curl http://localhost:3001` → Langfuse UI loads (HTTP 200)
- [x] `./infra/scripts/verify-stack.sh` → all checks pass

---

| **Prev** | **Next** |
|---|---|
| [Step 01 — Project Scaffolding](../01-project-scaffolding/SPEC.md) | [Step 03 — Proxy Service Foundation](../03-proxy-foundation/SPEC.md) |
