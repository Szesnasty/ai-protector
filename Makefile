.PHONY: dev dev-infra down pull-model lint format test verify

# ── Quick start ─────────────────────────────────────────
# First time:  make init    (builds + pulls LLM model)
# Daily dev:   make dev     (starts everything)

dev:
	cd infra && docker compose up --build -d
	@echo ""
	@echo "🚀  AI Protector is starting..."
	@echo "    Frontend:       http://localhost:3000"
	@echo "    Proxy API:      http://localhost:8000"
	@echo "    Agent Demo:     http://localhost:8002"
	@echo "    Langfuse:       http://localhost:3001"
	@echo ""
	@echo "    Logs:  cd infra && docker compose logs -f"

init: dev pull-model
	@echo ""
	@echo "✅  AI Protector is ready! Open http://localhost:3000"

pull-model:
	cd infra && docker compose run --rm model-pull

# ── Docker ──────────────────────────────────────────────
dev-infra:
	cd infra && docker compose up db redis ollama langfuse -d

down:
	cd infra && docker compose down

reset:
	cd infra && docker compose down -v
	@echo "🗑️  All data wiped (volumes removed)"

logs:
	cd infra && docker compose logs -f

ps:
	cd infra && docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

# ── Lint ────────────────────────────────────────────────
lint:
	cd apps/proxy-service && ruff check src/ tests/
	cd apps/agent-demo && ruff check src/ tests/
	cd apps/frontend && npx eslint .

format:
	cd apps/proxy-service && ruff format src/ tests/
	cd apps/agent-demo && ruff format src/ tests/
	cd apps/frontend && npx eslint . --fix

# ── Test ────────────────────────────────────────────────
test:
	cd apps/proxy-service && pytest tests/ -v
	cd apps/agent-demo && pytest tests/ -v

test-cov:
	cd apps/proxy-service && pytest tests/ -v --cov=src --cov-report=html

# ── Verify ──────────────────────────────────────────────
verify:
	cd infra && bash scripts/verify-stack.sh
