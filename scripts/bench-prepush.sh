#!/usr/bin/env bash
# Pre-push guard: run the external-attack detection gate locally so a detection
# regression is caught before it reaches CI. Invoked by the `bench-external-gate`
# pre-commit hook (pre-push stage); see .pre-commit-config.yaml.
#
# Runs the SAME check as CI: `make benchmark-external-gate`
# (bench_external --check-baseline --subset full, off-mode, vs baseline.json).
#
# Escape hatches:
#   SKIP_BENCH=1 git push      # skip this gate for one push
#   git push --no-verify       # skip all pre-push hooks
#
# Exits 0 (non-blocking) when the proxy venv is not set up, so a fresh clone or a
# docs-only contributor is never blocked. ~2 min on Apple Silicon; on CPU-only
# machines prefer SKIP_BENCH and rely on the CI gate.
set -euo pipefail

if [ -n "${SKIP_BENCH:-}" ]; then
  echo "[bench] skipped (SKIP_BENCH set)"
  exit 0
fi

if [ ! -x apps/proxy-service/.venv/bin/python ]; then
  echo "[bench] skipped: apps/proxy-service/.venv not found (run: make init)"
  exit 0
fi

echo "[bench] external attack regression gate (full corpus, ~2 min on Apple Silicon)..."
echo "[bench] bypass with: SKIP_BENCH=1 git push   (or git push --no-verify)"
exec make benchmark-external-gate
