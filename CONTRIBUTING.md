# Contributing & running AI Protector

**AI Protector is a solo-authored, source-available project.** I build and maintain it
alone — it is both a working tool and a portfolio of how I approach agent security.

**Code contributions are not accepted.** Pull requests will be closed unmerged. No hard
feelings — it is a deliberate choice to keep the codebase fully owned and vouched-for.

**What *is* very welcome:**

- 🐛 **Bug reports** and 💡 **ideas** → [open an issue](https://github.com/Szesnasty/ai-protector/issues)
- 🧪 **"I ran it against my model and here's what happened"** → issues or [Discussions](https://github.com/Szesnasty/ai-protector/discussions)
- ⭐ a star, if it is useful to you

The [Apache-2.0](LICENSE) license lets you **fork, run, and adapt it freely** for your own use.

---

## Running it locally

```bash
git clone https://github.com/Szesnasty/ai-protector.git
cd ai-protector
make init          # builds everything + pulls LLM model (~4.7 GB)
```

Open http://localhost:3000 when done.

### Option A — Full Docker (simplest)

```bash
make dev           # start all services
make logs          # stream logs
make down          # stop
```

### Option B — Native apps with hot-reload

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

### Checks

```bash
make lint          # ruff (Python) + eslint (TypeScript/Vue)
make test          # full test suite
make format        # auto-fix formatting
```

## Project structure

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

## Questions?

Open an [issue](https://github.com/Szesnasty/ai-protector/issues) or start a
[Discussion](https://github.com/Szesnasty/ai-protector/discussions). Feedback is genuinely welcome.
