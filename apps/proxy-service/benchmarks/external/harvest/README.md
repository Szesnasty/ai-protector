# Offline harvest — promptfoo → frozen corpus

> **Runs offline only. Never in CI.** CI replays the *frozen* corpus
> deterministically. Harvest (re)generates that corpus; its output is committed
> via a reviewed PR.

## Why offline

`promptfoo redteam generate` uses an LLM to generate/augment attacks → it is
**non-deterministic** and costs money/keys. So we **generate once → freeze →
replay**: the corpus is a committed artifact that only changes through an
explicit, reviewed PR. CI never calls promptfoo or an LLM.

## Prerequisites

```bash
npm install -g promptfoo            # or: npx promptfoo@latest
export OPENAI_API_KEY=...           # provider used by promptfoo to generate attacks
promptfoo --version                 # pin this as --source-version below
```

## Steps

```bash
cd apps/proxy-service/benchmarks/external/harvest

# 1. Generate attacks (writes raw/redteam.yaml). Does NOT call our pipeline.
promptfoo redteam generate -c promptfooconfig.yaml -o raw/redteam.yaml

# 2. Normalize → canonical corpus/promptfoo.jsonl + rebuild manifest.json
cd ../../..   # → apps/proxy-service
python -m benchmarks.external.loaders.promptfoo_loader \
    --input benchmarks/external/harvest/raw/redteam.yaml \
    --source-version "$(promptfoo --version)"

# 3. Re-baseline the gate against the new corpus (needs the ML pipeline locally)
python -m benchmarks.bench_external --update-baseline

# 4. Review the diff, then commit corpus/ + manifest.json + baseline.json via PR.
```

## Notes

- `raw/` is git-ignored — only the normalized `corpus/*.jsonl` is committed.
- Iteration 1 = **proxy surface only**. The agent-surface plugins
  (rbac/bola/bfla/ssrf/sql-injection/shell-injection/debug-access/excessive-agency)
  are intentionally excluded from `promptfooconfig.yaml`.
- The seed corpus (`corpus/seed.jsonl`, from `harvest/generate_seed.py`) is
  deterministic and needs no promptfoo — it keeps the benchmark runnable without
  any external tool. promptfoo augments it; it does not replace it.
