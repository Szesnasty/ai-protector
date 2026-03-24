.PHONY: demo up dev init down pull-model seed lint format test verify pre-commit-install pre-commit benchmark benchmark-quick benchmark-e2e benchmark-jailbreakbench

# ── Quick start ─────────────────────────────────────────
# Demo (no Ollama, mock LLM):     make demo
# Full stack (Ollama + real LLM):  make up
# Contributor (infra only):        make dev

# Generate BENCHMARK_SECRET_KEY if empty in infra/.env
define ensure-benchmark-key
	@if grep -q '^BENCHMARK_SECRET_KEY=$$' infra/.env 2>/dev/null; then \
		KEY=$$(openssl rand -hex 32) && \
		sed -i '' "s/^BENCHMARK_SECRET_KEY=$$/BENCHMARK_SECRET_KEY=$$KEY/" infra/.env && \
		echo "🔑  Generated BENCHMARK_SECRET_KEY"; \
	fi
endef

demo:
	@test -f infra/.env || (cp infra/.env.example infra/.env && echo "📋  Created infra/.env from .env.example")
	$(ensure-benchmark-key)
	cd infra && MODE=demo docker compose --profile demo --profile test-agents up --build -d
	@echo ""
	@echo "🚀  AI Protector Demo is starting..."
	@echo "    Frontend:       http://localhost:3000"
	@echo "    Proxy API:      http://localhost:8000"
	@echo "    Agent Demo:     http://localhost:8002"
	@echo "    Python Agent:   http://localhost:8003"
	@echo "    LangGraph Agent:http://localhost:8004"
	@echo ""
	@echo "    Mode: DEMO (mock LLM, real security pipeline)"
	@echo "    Paste an API key in Settings to use a real model."

up:
	@test -f infra/.env || (cp infra/.env.example infra/.env && echo "📋  Created infra/.env from .env.example")
	$(ensure-benchmark-key)
	cd infra && MODE=real docker compose --profile full --profile test-agents up --build -d
	@echo ""
	@echo "🚀  AI Protector is starting (full stack)..."
	@echo "    Frontend:       http://localhost:3000"
	@echo "    Proxy API:      http://localhost:8000"
	@echo "    Agent Demo:     http://localhost:8002"
	@echo "    Python Agent:   http://localhost:8003"
	@echo "    LangGraph Agent:http://localhost:8004"
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
	cd infra && docker compose --profile demo --profile full --profile test-agents down

reset:
	cd infra && docker compose --profile demo --profile full --profile test-agents down -v
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
	cd apps/test-agents && pytest tests/ -v

test-cov:
	cd apps/proxy-service && pytest tests/ -v --cov=src --cov-report=html

test-scenarios:  ## Run 358 attack scenario deterministic tests (all scanners)
	cd apps/proxy-service && pytest tests/test_scenario_deterministic.py -v --tb=short -x

# ── Benchmark ───────────────────────────────────────────
benchmark:  ## Run full benchmark suite (latency + security + memory)
	cd apps/proxy-service && .venv/bin/python -m benchmarks.bench_security --all-policies
	cd apps/proxy-service && .venv/bin/python -m benchmarks.bench_latency --all-policies --iterations 50
	cd apps/proxy-service && .venv/bin/python -m benchmarks.bench_memory
	cd apps/proxy-service && .venv/bin/python -m benchmarks.generate_report
	@echo ""
	@echo "📊  Benchmark complete — see BENCHMARK.md"

benchmark-quick:  ## Quick benchmark (balanced policy, 20 iterations)
	cd apps/proxy-service && .venv/bin/python -m benchmarks.bench_security
	cd apps/proxy-service && .venv/bin/python -m benchmarks.bench_latency --iterations 20
	cd apps/proxy-service && .venv/bin/python -m benchmarks.generate_report

benchmark-e2e:  ## End-to-end benchmark with real LLM (requires GEMINI_API_KEY + running proxy)
	cd apps/proxy-service && .venv/bin/python -m benchmarks.bench_e2e --iterations 10
	cd apps/proxy-service && .venv/bin/python -m benchmarks.generate_report

benchmark-jailbreakbench:  ## JailbreakBench (NeurIPS 2024) detection benchmark
	cd apps/proxy-service && .venv/bin/python -m benchmarks.bench_jailbreakbench
	@echo ""
	@echo "📊  JailbreakBench results — see BENCHMARK_JAILBREAKBENCH.md"

# ── Verify ──────────────────────────────────────────────
verify:
	cd infra && bash scripts/verify-stack.sh
