.PHONY: dev dev-infra down lint format test

# ── Docker ──────────────────────────────────────────────
dev:
	cd infra && docker compose up

dev-infra:
	cd infra && docker compose up db redis ollama langfuse

down:
	cd infra && docker compose down

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
