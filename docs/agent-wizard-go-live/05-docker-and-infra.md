# Step 05 — Docker & Infrastructure

> **Effort:** 1 hour
> **Depends on:** steps 03, 04 (agent apps must exist)
> **Blocks:** step 06 (frontend needs running agents)

---

## Context

The existing `infra/docker-compose.yml` has: `db` (PostgreSQL), `proxy` (proxy-service :8000),
`frontend` (:3000), `agent-demo` (:8002), plus optional services (Langfuse, Ollama, Redis).

We add 2 new services for the test agents and configure networking so they can reach
the proxy-service to fetch wizard integration kits.

---

## Implementation Plan

### Step 1: Add services to `infra/docker-compose.yml`

Add under `services:`:

```yaml
  # ── Test Agents (wizard go-live) ──────────────────────────────

  test-agent-python:
    build:
      context: ../apps/test-agents
      dockerfile: pure-python-agent/Dockerfile
    container_name: test-agent-python
    ports:
      - "8003:8003"
    environment:
      - PROXY_URL=http://proxy:8000
    depends_on:
      proxy:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8003/health"]
      interval: 10s
      timeout: 5s
      retries: 3
    profiles:
      - test-agents
    networks:
      - ai-protector

  test-agent-langgraph:
    build:
      context: ../apps/test-agents
      dockerfile: langgraph-agent/Dockerfile
    container_name: test-agent-langgraph
    ports:
      - "8004:8004"
    environment:
      - PROXY_URL=http://proxy:8000
    depends_on:
      proxy:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8004/health"]
      interval: 10s
      timeout: 5s
      retries: 3
    profiles:
      - test-agents
    networks:
      - ai-protector
```

### Step 2: Docker profile usage

Using `profiles: [test-agents]` so these services only start when explicitly requested:

```bash
# Start everything including test agents
docker compose --profile test-agents up -d

# Start only test agents (assumes proxy + db already running)
docker compose --profile test-agents up -d test-agent-python test-agent-langgraph

# Start without test agents (normal dev workflow)
docker compose up -d
```

### Step 3: Dockerfile for Pure Python agent

```dockerfile
# apps/test-agents/pure-python-agent/Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY pure-python-agent/pyproject.toml ./pyproject.toml
RUN pip install --no-cache-dir .

# Copy shared tools
COPY shared/ ./shared/

# Copy agent code
COPY pure-python-agent/ ./

EXPOSE 8003
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]
```

### Step 4: Dockerfile for LangGraph agent

```dockerfile
# apps/test-agents/langgraph-agent/Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY langgraph-agent/pyproject.toml ./pyproject.toml
RUN pip install --no-cache-dir .

# Copy shared tools
COPY shared/ ./shared/

# Copy agent code
COPY langgraph-agent/ ./

EXPOSE 8004
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8004"]
```

### Step 5: Update frontend env for new endpoints

In `infra/docker-compose.yml`, update the frontend service env:

```yaml
  frontend:
    environment:
      - NUXT_PUBLIC_API_BASE=http://localhost:8000
      - NUXT_PUBLIC_AGENT_API_BASE=http://localhost:8002
      - NUXT_PUBLIC_TEST_AGENT_PYTHON_URL=http://localhost:8003   # NEW
      - NUXT_PUBLIC_TEST_AGENT_GRAPH_URL=http://localhost:8004    # NEW
```

### Step 6: Add CSP connect-src for test agent ports

In `apps/frontend/server/middleware/security-headers.ts`, the CSP `connect-src` should
include `:8003` and `:8004`:

```
connect-src 'self' http://localhost:8000 http://localhost:8002 http://localhost:8003 http://localhost:8004
```

### Step 7: Local dev (without Docker)

For local development without Docker, run the agents directly:

```bash
# Terminal 1: proxy + DB (already running)
cd infra && docker compose up -d db proxy

# Terminal 2: Pure Python agent
cd apps/test-agents/pure-python-agent
pip install -e ".[dev]"
PROXY_URL=http://localhost:8000 uvicorn main:app --port 8003 --reload

# Terminal 3: LangGraph agent
cd apps/test-agents/langgraph-agent
pip install -e ".[dev]"
PROXY_URL=http://localhost:8000 uvicorn main:app --port 8004 --reload

# Terminal 4: Frontend
cd apps/frontend && npm run dev
```

---

## Network Diagram (Docker)

```
┌─────────────────── ai-protector network ───────────────────────┐
│                                                                 │
│  frontend:3000 ──► proxy:8000 ◄── test-agent-python:8003       │
│                        │         ◄── test-agent-langgraph:8004  │
│                        │                                        │
│                     db:5432                                     │
│                                                                 │
│  (agent-demo:8002 — existing, separate)                        │
└─────────────────────────────────────────────────────────────────┘

Data flow:
  1. Frontend → POST test-agent:800x/load-config {agent_id}
  2. test-agent → GET proxy:8000/v1/agents/:id/integration-kit
  3. proxy reads DB → returns 7-file kit → test-agent loads YAML
  4. Frontend → POST test-agent:800x/chat {message, role}
  5. test-agent runs security gates → returns response + gate_log
```

---

## Definition of Done

- [ ] Both Dockerfiles build successfully: `docker compose --profile test-agents build`
- [ ] `docker compose --profile test-agents up -d` starts both test agents
- [ ] `curl http://localhost:8003/health` returns OK
- [ ] `curl http://localhost:8004/health` returns OK
- [ ] Test agents can reach proxy-service: `POST /load-config` succeeds from inside container
- [ ] Frontend env vars `TEST_AGENT_PYTHON_URL` and `TEST_AGENT_GRAPH_URL` are set
- [ ] CSP headers allow connections to :8003 and :8004
- [ ] Normal `docker compose up` (without profile) does NOT start test agents
