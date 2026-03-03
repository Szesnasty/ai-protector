# AI Protector

Self-hosted **LLM Firewall with an Agentic Security Pipeline** — an OpenAI-compatible proxy that scans, classifies, and enforces policies on every LLM request and response. Includes a demo agent app (Customer Support Copilot) to showcase both **building** and **securing** AI agents.

## Highlights

- **Policy Agent** — LangGraph-based firewall pipeline (not a dumb filter chain)
- **Two-Level Security** — agent-level + proxy-level protection
- **Agent Demo** — working tool-calling agent running behind the firewall
- **Full Observability** — Langfuse tracing, structured logging, risk scoring
- **Local-first** — runs on Ollama (Llama 3.1 8B), no cloud keys needed

## Current Status

The full **firewall pipeline** is implemented and tested (325 tests):

| Phase | Steps | Status |
|-------|-------|--------|
| Foundation (01–04) | Scaffolding, Docker, FastAPI, LLM Proxy | ✅ Done |
| Firewall Pipeline (06–09) | LangGraph, Scanners, Policies, Output Pipeline | ✅ Done |
| Frontend & Agent (05, 10–18) | Playground, Agent Demo, Dashboard | 🔜 Next |

### Pipeline Architecture

```
User Request → POST /v1/chat/completions
                 │
    ┌────────────▼────────────┐
    │   ParseNode → IntentNode → RulesNode → ScannersNode → DecisionNode   │
    │                                                           │          │
    │                    ┌──────────────────┬────────────────────┤          │
    │                    ▼                  ▼                    ▼          │
    │                  BLOCK             MODIFY               ALLOW        │
    │                    │            TransformNode              │          │
    │                    │                  │                    │          │
    │                    │              LLM Call             LLM Call       │
    │                    │                  │                    │          │
    │                    │           OutputFilterNode    OutputFilterNode   │
    │                    │                  │                    │          │
    │                    └──────► LoggingNode (Postgres + Langfuse) ◄──────┘
    └─────────────────────────────────────────────────────────────────────┘
```

See [mvp-diagram.md](mvp-diagram.md) for the full 18-step implementation plan diagram.

## Tech Stack

**Frontend:** Nuxt 4 · Vuetify 3 · Pinia · vue-echarts
**Backend:** FastAPI · LangGraph · LiteLLM · LLM Guard · Presidio · NeMo Guardrails
**Infra:** Docker Compose · PostgreSQL 16 · Redis 7 · Ollama · Langfuse

## Docs

- [MVP Spec](docs/MVP.spec.md) — architecture, agentic pipeline, agent demo, implementation plan
- [Roadmap](docs/ROADMAP.spec.md) — Red Team engine, adaptive policies, enterprise features

---

## Getting Started

### Prerequisites

| Tool | Version |
|------|---------|
| Docker & Docker Compose | latest |
| Python | 3.12+ |
| Node.js | 20+ (for frontend, optional) |

### 1. Clone & start infrastructure

```bash
git clone https://github.com/Szesnasty/ai-protector.git
cd ai-protector
docker compose up -d          # PostgreSQL, Redis, Ollama, Langfuse
```

Wait for Ollama to pull the default model (first run only):

```bash
docker compose exec ollama ollama pull llama3.1:8b
```

### 2. Run the proxy service

```bash
cd apps/proxy-service

# Create & activate virtual environment
python3 -m venv .venv
source .venv/bin/activate      # on Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy env file and adjust if needed
cp .env.example .env

# Run database migrations
alembic upgrade head

# Seed default policies & denylist
python -m src.db.seed

# Start the server
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

The API is now available at **http://localhost:8000**.

### 3. Verify it works

```bash
# Health check
curl http://localhost:8000/health

# Chat completion (non-streaming)
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Hello!"}]}'

# Chat completion (streaming)
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Hello!"}], "stream": true}'
```

### 4. Run tests

```bash
cd apps/proxy-service
source .venv/bin/activate
pytest tests/ -v               # all tests
ruff check src/ tests/         # linter
```

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/ai_protector` | Async PostgreSQL connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API base URL |
| `DEFAULT_MODEL` | `ollama/llama3.1:8b` | Default LLM model |
| `DEFAULT_POLICY` | `balanced` | Default firewall policy |
| `DEFAULT_TEMPERATURE` | `0.7` | Default LLM temperature |
| `ENABLE_LANGFUSE` | `true` | Enable Langfuse tracing |
