# D — CI, Reporting & `AGENT_BENCHMARKS.md`

> **Status:** Planned — detailed · **Effort:** S–M · cross-cuts [A](A-pre-tool-gate.spec.md)/[B](B-post-tool-gate.spec.md)/[C](C-e2e-agent-traces.spec.md)
> Part of the [Agent Boundary Benchmark plan](README.md).

## 1. Goal

Make the agent benchmark **frozen, gated, badged, and documented** — the same machinery that makes the
proxy benchmark citable, applied to the agent boundary.

## 2. Freeze + integrity (harvest-and-freeze)

- All corpora are committed JSONL with a per-file **sha256 `manifest.json`**.
- A `verify_manifest` step fails CI if a corpus changed without a manifest update (anti-Goodhart, same
  as `benchmarks/external/verify_manifest`).
- `results/*.json` are **gitignored** and uploaded as a CI artifact (auditable last run, not committed).

## 3. Regression gate

- `baseline.json` stores per-metric values + tolerances (detection drop, FPR rise, per-category floor).
- `bench_pre_tool.py` / `bench_post_tool.py` / `bench_agent_e2e.py` each support
  `--check-baseline` (exit 1 on regression) and `--update-baseline`, mirroring `bench_external.py`.
- **Hard invariants (not just tolerances):** Unauthorized-Tool-Block = 100%, Unknown/Spoofed = 100%,
  **Unsafe-Action-Success = 0%** → any breach fails the build outright.

## 4. CI wiring (`.github/workflows/benchmark.yml`)

Add a sibling job to `detection-gate`, scoped to agent paths:

```yaml
  agent-boundary-gate:
    name: Agent boundary gate (pre/post-tool + e2e)
    if: github.event_name == 'pull_request' || github.event_name == 'push'
    # paths: apps/agent-demo/**
    steps:
      - verify agent corpus manifest
      - python -m benchmarks.bench_pre_tool   --check-baseline
      - python -m benchmarks.bench_post_tool  --check-baseline
      - python -m benchmarks.bench_agent_e2e  --check-baseline
      - upload results/*.json artifact (if: always())
```

- **Fast + deterministic** (pure functions, no models to download) → cheap on every PR, unlike the
  ML-heavy proxy gate.
- `publish-badges` (weekly/dispatch) recomputes the agent badges onto the `badges` branch.

## 5. Badges + Makefile + pre-push

- **Badges:** `pre-tool gate`, `post-tool gate`, and the headline `unsafe action: 0%` (or one
  `agent boundary` badge). Same shields-endpoint mechanism as the proxy badges.
- **Makefile:** `benchmark-agent-pretool-gate`, `benchmark-agent-posttool-gate`,
  `benchmark-agent-e2e-gate`, plus a `benchmark-agent` umbrella.
- **Pre-push:** extend the existing hook (or add a sibling) to run the agent gates when
  `apps/agent-demo/**` changes — cheap because the gates are pure (no `SKIP_BENCH` needed by default).

## 6. `docs/AGENT_BENCHMARKS.md` (the canonical doc)

Separate from `docs/BENCHMARKS.md`. Structure mirrors it (At-a-glance → environment → per-gate
breakdown → weak spots → "what this does NOT prove" → methodology → reproduce).

### At a glance (numbers illustrative until measured)

```markdown
# AI Protector — Agent Boundary Benchmark

Deterministic replay. No LLM-as-judge. Measures agent safety boundaries:
pre-tool authorization and post-tool output sanitization.

| Boundary | Corpus | Unsafe blocked | Benign allowed | p50 latency |
|---|---:|---:|---:|---:|
| Pre-tool: RBAC / scope            | 500 | 100%                      | 99.8% | 2 ms |
| Pre-tool: args / injection        | 500 | 99.4%                     | 99.5% | 4 ms |
| Pre-tool: business logic          | 300 | 100%                      | 99.0% | 3 ms |
| Post-tool: PII / secrets          | 600 | 99.2% redaction recall    | 99.1% | 12 ms |
| Post-tool: indirect injection     | 500 | <measured>                | 99.0% | 18 ms |
| E2E agent traces                  | 250 | 0% unsafe action success  | 96.5% completion | — |
```

> Every cell is filled from a real run; `<measured>` indirect-injection is published as observed (with
> misses), never pre-set. Include a **Weak spots** section and a **"what this does NOT prove"** section
> (no live MCP registry fuzzing, no multi-agent, frozen-corpus only).

## 7. Two-pillar framing (README + landing)

Surface both pillars side by side so the story is legible to acquirers:

1. **Prompt / proxy protection:** 99% JailbreakBench, 91% promptfoo (harm-on).
2. **Agent / tool protection:** 0% unsafe action success, 100% RBAC/scope enforcement, post-tool sanitization.

## 8. Acceptance criteria

- [ ] sha256 manifest + `verify_manifest` gate on agent corpora.
- [ ] Three agent gates run on every PR + push; hard invariants (100% / 0%) fail the build.
- [ ] `results/*.json` uploaded as artifact; baselines committed.
- [ ] Agent badge(s) live on the `badges` branch and linked from README + `AGENT_BENCHMARKS.md`.
- [ ] `AGENT_BENCHMARKS.md` published with a weak-spots + "does NOT prove" section.
- [ ] README shows the two pillars together.
