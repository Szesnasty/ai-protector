# Contributing to AI Protector

Thanks for your interest in contributing! This guide will help you get started.

## Quick Setup

```bash
git clone https://github.com/Szesnasty/ai-protector.git
cd ai-protector
make init          # builds everything + pulls LLM model (~4.7 GB)
```

Open http://localhost:3000 when done.

## Development Workflow

### Option A: Full Docker (simplest)

```bash
make dev           # start all services
make logs          # stream logs
make down          # stop
```

### Option B: Native apps with hot-reload (recommended for development)

```bash
make dev-infra     # start only PostgreSQL, Redis, Ollama, Langfuse

# Terminal 1 — Proxy Service
cd apps/proxy-service
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn src.main:app --reload --port 8000

# Terminal 2 — Agent Demo
cd apps/agent-demo
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn src.main:app --reload --port 8002

# Terminal 3 — Frontend
cd apps/frontend
npm install
npm run dev
```

## Before Submitting a PR

```bash
make lint          # ruff (Python) + eslint (TypeScript/Vue)
make test          # all tests must pass
```

## Commit Convention

We use [Conventional Commits](https://www.conventionalcommits.org/):

| Prefix | Use for |
|--------|---------|
| `feat:` | New feature |
| `fix:` | Bug fix |
| `docs:` | Documentation only |
| `test:` | Adding/fixing tests |
| `refactor:` | Code change that doesn't add feature or fix bug |
| `dx:` | Developer experience improvements |
| `ci:` | CI/CD changes |

Examples:
```
feat: add rate limiting to chat endpoint
fix: streaming BLOCK requests not logged to analytics
docs: update README quick start section
```

## Code Style

| Language | Tool | Config |
|----------|------|--------|
| Python | [Ruff](https://docs.astral.sh/ruff/) | `pyproject.toml` (line-length: 120, Python 3.12) |
| TypeScript / Vue | [ESLint](https://eslint.org/) | `eslint.config.mjs` |

Don't format manually — the tools handle it:
```bash
make format        # auto-fix all formatting
```

## Project Structure

```
apps/
├── proxy-service/     # Python FastAPI — LLM Firewall
├── agent-demo/        # Python FastAPI — Customer Support Copilot
└── frontend/          # Nuxt 4 + Vuetify 4 — Dashboard
infra/
└── docker-compose.yml # PostgreSQL, Redis, Ollama, Langfuse
docs/
├── architecture/      # System design, pipelines, threat model
└── assets/            # Screenshots and diagrams
```

## PR Checklist

Before requesting review, ensure:

- [ ] Tests pass (`make test`)
- [ ] Linting passes (`make lint`)
- [ ] Commit messages follow Conventional Commits
- [ ] New features have tests
- [ ] Documentation updated if needed

## Questions?

Open a [GitHub Discussion](https://github.com/Szesnasty/ai-protector/discussions) for questions or ideas.
