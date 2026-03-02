#!/usr/bin/env bash
set -euo pipefail

MODEL="${1:-llama3.1:8b}"
OLLAMA_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"

echo "⏳ Waiting for Ollama to be ready at ${OLLAMA_URL}..."
until curl -sf "${OLLAMA_URL}/api/tags" > /dev/null 2>&1; do
  sleep 1
done
echo "✅ Ollama is up."

echo "📦 Pulling ${MODEL} (this may take a while ~4.7 GB)..."
curl -sf "${OLLAMA_URL}/api/pull" -d "{\"name\": \"${MODEL}\"}" | while IFS= read -r line; do
  status=$(echo "$line" | grep -o '"status":"[^"]*"' | head -1 | cut -d'"' -f4)
  [ -n "$status" ] && printf "\r  %s" "$status"
done
echo ""
echo "✅ Model ${MODEL} is ready."
