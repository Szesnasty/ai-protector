.PHONY: demo up dev init down pull-model seed lint format test verify pre-commit-install pre-commit

# ── Quick start ─────────────────────────────────────────
# Demo (no Ollama, mock LLM):     make demo
# Full stack (Ollama + real LLM):  make up
# Contributor (infra only):        make dev

demo:
	@test -f infra/.env || (cp infra/.env.example infra/.env && echo "📋  Created infra/.env from .env.example")
	cd infra && MODE=demo docker compose --profile demo up --build -d
	@echo ""
	@echo "🚀  AI Protector Demo is starting..."
	@echo "    Frontend:       http://localhost:3000"
	@echo "    Proxy API:      http://localhost:8000"
	@echo "    Agent Demo:     http://localhost:8002"
	@echo ""
	@echo "    Mode: DEMO (mock LLM, real security pipeline)"
	@echo "    Paste an API key in Settings to use a real model."

up:
	@test -f infra/.env || (cp infra/.env.example infra/.env && echo "📋  Created infra/.env from .env.example")
	cd infra && MODE=real docker compose --profile full up --build -d
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

pull-model:
	cd infra && docker compose --profile full --profile init run --rm model-pull

seed:
	@echo "🌱 Seeding demo data (20 requests)..."
	@python3 scripts/seed_demo.py

# ── Docker ──────────────────────────────────────────────
down:
	cd infra && docker compose --profile demo --profile full down

reset:
	cd infra && docker compose --profile demo --profile full down -v
	@echo "🗑️  All data wiped (volumes removed)"

logs:
	cd infra && docker compose logs -f

ps:
	cd infra && docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

# ── Lint ────────────────────────────────────────────────
lint:
	cd apps/proxy-service && ruff check src/ tests/ && ruff format --check src/ tests/
	cd apps/agent-demo && ruff check src/ tests/ && ruff format --check src/ tests/
	cd apps/frontend && npx eslint .

lint-fix:
	cd apps/proxy-service && ruff check --fix src/ tests/ && ruff format src/ tests/
	cd apps/agent-demo && ruff check --fix src/ tests/ && ruff format src/ tests/
	cd apps/frontend && npx eslint . --fix

format:
	cd apps/proxy-service && ruff format src/ tests/
	cd apps/agent-demo && ruff format src/ tests/
	cd apps/frontend && npx eslint . --fix

# ── Pre-commit ──────────────────────────────────────────
pre-commit-install:
	pip install pre-commit && pre-commit install
	@echo "✅  pre-commit hooks installed"

pre-commit:
	pre-commit run --all-files

# ── Test ────────────────────────────────────────────────
test:
	cd apps/proxy-service && pytest tests/ -v
	cd apps/agent-demo && pytest tests/ -v

test-cov:
	cd apps/proxy-service && pytest tests/ -v --cov=src --cov-report=html

test-scenarios:  ## Run 358 attack scenario deterministic tests (all scanners)
	cd apps/proxy-service && pytest tests/test_scenario_deterministic.py -v --tb=short -x

# ── Verify ──────────────────────────────────────────────
verify:
	cd infra && bash scripts/verify-stack.sh
