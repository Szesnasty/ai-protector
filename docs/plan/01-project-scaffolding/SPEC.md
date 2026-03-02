# Step 01 — Project Scaffolding

| | |
|---|---|
| **Phase** | Foundation |
| **Estimated time** | 2–4 hours |
| **Prev** | — |
| **Next** | [Step 02 — Infrastructure](../02-infrastructure/SPEC.md) |
| **Master plan** | [MVP-PLAN.md](../MVP-PLAN.md) |

---

## Goal

Create the monorepo directory structure, configure all linters and formatters, initialize Python and Node.js projects so that every subsequent step has a clean, consistent foundation to build on.

---

## Tasks

### 1. Root-level config

- [ ] Create root `.gitignore` (Python, Node, Docker, IDE, OS files)
- [ ] Create `.editorconfig` (indent style, charset, trailing whitespace)
- [ ] Create root `Makefile` or `justfile` with common commands:
  - `make dev` → docker compose up
  - `make lint` → run all linters
  - `make format` → run all formatters

### 2. Python — Proxy Service (`apps/proxy-service/`)

- [ ] Create `apps/proxy-service/` directory
- [ ] `pyproject.toml` with:
  - Python 3.12+ requirement
  - Dependencies: `fastapi`, `uvicorn[standard]`, `pydantic[v2]`, `sqlalchemy[asyncio]`, `alembic`, `asyncpg`, `redis[hiredis]`, `litellm`, `llm-guard`, `presidio-analyzer`, `presidio-anonymizer`, `nemoguardrails`, `langgraph`, `langfuse`, `structlog`, `httpx`
  - Dev dependencies: `pytest`, `pytest-asyncio`, `pytest-cov`, `ruff`, `mypy`
  - Ruff config: line-length 120, select rules (E, W, F, I, UP, B, SIM)
  - mypy config: strict mode
- [ ] Create `apps/proxy-service/src/` package with `__init__.py`
- [ ] Create `apps/proxy-service/tests/` with `__init__.py`
- [ ] Create `apps/proxy-service/Dockerfile` (multi-stage: builder + runtime)
- [ ] Verify: `cd apps/proxy-service && pip install -e ".[dev]"` works
- [ ] Verify: `ruff check .` runs clean on empty project

### 3. Python — Agent Demo (`apps/agent-demo/`)

- [ ] Create `apps/agent-demo/` directory
- [ ] `pyproject.toml` with:
  - Dependencies: `fastapi`, `uvicorn[standard]`, `pydantic`, `langgraph`, `litellm`, `httpx`, `structlog`
  - Dev dependencies: `pytest`, `pytest-asyncio`, `ruff`
  - Same ruff config as proxy-service
- [ ] Create `apps/agent-demo/src/` package with `__init__.py`
- [ ] Create `apps/agent-demo/tests/` with `__init__.py`
- [ ] Create `apps/agent-demo/Dockerfile`

### 4. Frontend (`apps/frontend/`)

- [ ] Initialize Nuxt 4 project: `npx nuxi@latest init apps/frontend`
- [ ] Install Vuetify 3: `vuetify-nuxt-module`
- [ ] Install additional deps: `pinia`, `@pinia/nuxt`, `zod`, `vue-echarts`, `echarts`
- [ ] Configure `nuxt.config.ts`:
  - Vuetify module with dark/light theme
  - Pinia module
  - TypeScript strict mode
  - Runtime config for API base URLs
- [ ] ESLint + Prettier config (via `@nuxt/eslint`)
- [ ] Create `apps/frontend/Dockerfile` (multi-stage: build + serve)
- [ ] Verify: `cd apps/frontend && npm run dev` starts without errors

### 5. Infrastructure directory

- [ ] Create `infra/` directory
- [ ] Create `infra/.env.example` with all environment variables (documented)
- [ ] Placeholder `infra/docker-compose.yml` (will be filled in Step 02)

### 6. Documentation structure

- [ ] Ensure `docs/plan/` structure is in place
- [ ] Add a one-liner `apps/README.md` explaining the monorepo layout

---

## File Tree After This Step

```
ai-protector/
├── .editorconfig
├── .gitignore
├── Makefile
├── README.md
├── apps/
│   ├── README.md
│   ├── frontend/
│   │   ├── Dockerfile
│   │   ├── nuxt.config.ts
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   └── ...
│   ├── proxy-service/
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   ├── src/
│   │   │   └── __init__.py
│   │   └── tests/
│   │       └── __init__.py
│   └── agent-demo/
│       ├── Dockerfile
│       ├── pyproject.toml
│       ├── src/
│       │   └── __init__.py
│       └── tests/
│           └── __init__.py
├── infra/
│   ├── .env.example
│   └── docker-compose.yml  (placeholder)
└── docs/
    ├── MVP.spec.md
    ├── ROADMAP.spec.md
    └── plan/
        ├── MVP-PLAN.md
        ├── 01-project-scaffolding/
        │   └── SPEC.md  ← you are here
        ├── 02-infrastructure/
        └── 03-proxy-foundation/
```

---

## Definition of Done

- [ ] All directories exist as specified above
- [ ] `ruff check apps/proxy-service/` → 0 errors
- [ ] `ruff check apps/agent-demo/` → 0 errors
- [ ] `cd apps/frontend && npm run dev` → starts on :3000
- [ ] `.gitignore` covers: `__pycache__`, `.venv`, `node_modules`, `.nuxt`, `.output`, `.env`, `*.pyc`, `.mypy_cache`, `.pytest_cache`, `dist/`
- [ ] All configs are committed and pushed
- [ ] No leftover TODO placeholders in config files

---

| **Prev** | **Next** |
|---|---|
| — | [Step 02 — Infrastructure](../02-infrastructure/SPEC.md) |
