#!/usr/bin/env bash
set -euo pipefail

PASS="✅"
FAIL="❌"
results=()

check() {
  local name="$1"
  local cmd="$2"
  if eval "$cmd" > /dev/null 2>&1; then
    results+=("$PASS $name")
  else
    results+=("$FAIL $name")
  fi
}

echo "🔍 Verifying AI Protector infrastructure..."
echo ""

# PostgreSQL
check "PostgreSQL (5432)" \
  "pg_isready -h localhost -U postgres -q 2>/dev/null || docker compose exec -T db pg_isready -U postgres -q"

# Langfuse DB
check "Langfuse DB exists" \
  "docker compose exec -T db psql -U postgres -lqt | grep -qw langfuse"

# Redis
check "Redis (6379)" \
  "redis-cli -h localhost ping 2>/dev/null | grep -q PONG || docker compose exec -T redis redis-cli ping | grep -q PONG"

# Ollama
check "Ollama (11434)" \
  "curl -sf http://localhost:11434/api/tags"

# Langfuse
check "Langfuse (3001)" \
  "curl -sf http://localhost:3001/api/public/health"

echo "┌──────────────────────────────────┐"
echo "│  AI Protector — Stack Status     │"
echo "├──────────────────────────────────┤"
for r in "${results[@]}"; do
  printf "│  %-32s│\n" "$r"
done
echo "└──────────────────────────────────┘"

# Exit with failure if any check failed
for r in "${results[@]}"; do
  if [[ "$r" == *"$FAIL"* ]]; then
    echo ""
    echo "⚠️  Some services are not healthy. Run: cd infra && docker compose ps"
    exit 1
  fi
done

echo ""
echo "🎉 All services are up and healthy!"
