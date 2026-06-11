# A3 — Comparative + Continuous Benchmark (detailed)

> **Track:** A (detection credibility)
> **Priority:** High
> **Effort:** M–L (phased)
> **Status:** Planned — detailed
> **Related:** consumes detection work from A1/A2/B1/B3/B4; produces the
> evidence those specs are validated against.

---

## 1. Goal

Turn self-graded numbers into evidence that survives technical due diligence and
is *citable* in the market:

- **Many external attack datasets** run through our pipeline (not just our own
  curated suite).
- **Continuous** regression gating in CI/CD — detection cannot silently degrade.
- A real **false-positive rate** on a large benign corpus (thousands, not 20).
- A periodic **comparative** report vs named competitors.

## 2. Core principle (read this first)

Two things are routinely conflated; they must be built and operated differently:

| | **External datasets → our pipeline** | **Comparative → competitors** |
|---|---|---|
| Cost | ~free (local) | $ (paid APIs) + keys |
| Determinism | deterministic | non-deterministic (cloud) |
| Legal/fairness | dataset license only | ToS, fairness of config |
| **Use as CI gate?** | **Yes** (blocking) | **No** (informational report) |

Designing one harness that treats both the same is the main failure mode. We
build **three tiers** instead.

## 3. Current state (what exists)

- [`benchmarks/common.py`](../../apps/proxy-service/benchmarks/common.py) already
  builds a **standalone pre-LLM pipeline** (mocks DB/Redis, no Docker) and loads
  internal scenarios from `data/scenarios/{playground,agent}.json`. This is the
  perfect substrate for the T1 gate — reuse it directly.
- `bench_security`, `bench_jailbreakbench`, `bench_latency`, `bench_e2e`,
  `generate_report` exist; results land in `benchmarks/results/`.
- CI ([`.github/workflows/ci.yml`](../../.github/workflows/ci.yml)) has no
  benchmark job. It already uses SHA-pinned actions, `workflow_dispatch`, and a
  Gist-based badge pattern (coverage) we can mirror for a detection badge.

Gaps: numbers are on our own suite (circular); FPR on ~20 prompts; no
comparison; no continuous regression gate.

## 4. Three-tier architecture

### Tier 1 — PR gate (blocking, fast, deterministic, free)

- **Runs:** every PR + push to main.
- **What:** our pre-LLM pipeline (`build_pre_llm_pipeline()` from `common.py`)
  against a **frozen, vendored subset** (~300–500 prompts) drawn from external
  datasets + internal suite, policy = `balanced` (optionally `strict`).
- **Metrics gated:** detection rate (recall on attacks), **FPR on a benign
  slice**, per-category floor (so an average can't hide a category collapse).
- **Mechanism:** compare against a committed `baseline.json`; fail if detection
  drops > tolerance (e.g. −1.5 pp) **or** FPR rises > ceiling. Post a PR comment
  with the delta table (mirror the coverage-summary `$GITHUB_STEP_SUMMARY`
  pattern already in `ci.yml`).
- **Budget:** target < 5 min. Models cached or pre-baked (see §8).
- **Held-out:** the gate set is **never** the set we tune on (see §7).

### Tier 2 — Scheduled (nightly/weekly, informational, larger)

- **Runs:** `schedule:` cron + `workflow_dispatch`.
- **What:** full external dataset suite + **large benign corpus** (FPR at scale),
  all policies, latency + memory. Our pipeline only — still deterministic & free.
- **Output:** trend artifact (append to a results history), updated badges,
  refreshed published tables. Optionally push results into a small store the
  frontend Analytics page can later visualize.

### Tier 3 — Comparative (manual/release, paid, non-gating)

- **Runs:** `workflow_dispatch` / release tag only — needs `secrets` (API keys).
- **What:** identical input sets sent through competitors; scored with the same
  detectors. Produces the published comparison table.
- **Never blocks a merge.** Cost-capped, cached, sampled.

## 5. External dataset catalog

> Attack sets = recall. Benign sets = FPR. Verify each license before vendoring;
> prefer loaders that fetch at runtime over committing large corpora.

**Attack / jailbreak / injection**
- JailbreakBench (have) — PAIR, GCG, JBC, random search.
- Lakera **PINT** — prompt-injection test methodology/dataset.
- **HackAPrompt** — large competition dataset of human attacks.
- **AdvBench** — harmful-behaviors (GCG lineage).
- **HarmBench** — standardized automated red-team eval behaviors.
- HF injection sets — e.g. `deepset/prompt-injections`,
  `jackhhao/jailbreak-classification` and similar (cross-check quality/license).
- **TensorTrust** — prompt-injection attack/defense corpus.

**Toxicity / safety**
- ToxicChat, BeaverTails, SALAD-Bench (subsets) — for the toxicity rails.

**Benign (FPR — the credibility metric)**
- ShareGPT / OASST / Alpaca / Dolly / LMSYS-Chat-1M subsets — real user-style
  prompts. Target a few thousand. This is what proves we don't block normal work.

**Framework mapping (not a dataset)**
- Map coverage to **OWASP LLM Top 10** and MITRE ATLAS so results speak the
  language buyers/auditors use.

## 6. Competitor catalog (Tier 3)

- **Lakera Guard** (API)
- **AWS Bedrock Guardrails**
- **Azure AI Content Safety — Prompt Shields**
- **Meta Llama Guard / Prompt Guard** (local, deterministic — note: also a
  candidate model for A1/B4, so it doubles as a baseline *and* a build option)
- **Guardrails AI** (OSS, local)
- **OpenAI Moderation** (API)
- Raw **LLM Guard / NeMo Guardrails** alone — to show our *pipeline* adds value
  over the OSS components we build on (important: we use these, so frame as
  "pipeline vs raw component", not "us vs them").

## 7. Benchmark integrity (anti-Goodhart)

This is what makes the numbers defensible:

- **Split every dataset into `dev` (tune) and `holdout` (report-only).** Never
  tune against holdout. The T1 gate uses a frozen slice distinct from dev.
- **Version + hash datasets**; record the hash in every report.
- **FPR is a first-class gate metric** — you cannot "improve" recall by blocking
  everything.
- **Per-category + per-attack-method breakdown** with the average, so regressions
  aren't masked.
- **Report confidence intervals** (Wilson) given sample sizes.
- Keep the **marketing set ≠ the gate set ≠ the tuning set**.

## 8. CI/CD wiring (concrete)

- **New workflow `benchmark.yml`** with two entrypoints:
  - `pull_request` / `push` → **T1 gate job** (fast subset, fail-on-regression).
  - `schedule` (cron) + `workflow_dispatch` → **T2 job** (full suite, trend).
- **A separate `benchmark-comparative.yml`** (`workflow_dispatch` + release) for
  **T3**, reading provider keys from `secrets`. Cost-capped; never required.
- **Model handling:** LLM Guard/NeMo/Presidio are heavy (~1 GB). Options, in order
  of preference:
  1. **Pre-baked benchmark Docker image** with models → CI runs in it (fast,
     reproducible). Reuses the existing proxy Dockerfile layer.
  2. `actions/cache` keyed on model ids (HF cache) — simpler, slower.
  3. Self-hosted runner if GitHub-hosted limits bite.
- **Baseline & results:** commit `benchmarks/baseline.json` (the gate reference)
  and append T2 runs to a history file/branch so trends are diffable. Mirror the
  Gist-badge pattern from `ci.yml` for a "detection 9x.x%" badge.
- **Reuse, don't reinvent:** keep our deterministic in-house harness for the T1
  gate; for breadth in T2/T3 evaluate adopting **garak** (NVIDIA),
  **PyRIT** (Microsoft), **promptfoo**, or **Inspect** (UK AISI) as additional
  evaluators. Using recognized OSS reads as ecosystem fluency in DD.

## 9. Metrics & methodology

- Detection rate / recall on attacks; **FPR** on benign; precision/F1; per-class.
- Latency p50/p95 and memory (extend existing `bench_latency` / machine info in
  `common.py:collect_machine_info`).
- Our scoring stays **deterministic** (no LLM-as-judge) for our pipeline. For
  competitor outputs, define one consistent verdict-extraction rule and document
  it.
- Every report records: git SHA, policy, thresholds, dataset versions/hashes,
  machine info — full reproducibility (`make benchmark` already exists; extend).

## 10. Phased rollout

- **Phase 1 (no competitor dependency):** T1 gate + a first batch of external
  attack datasets + a benign FPR corpus + dev/holdout split. → honest, gated,
  citable numbers. **Start here.**
- **Phase 2:** T2 scheduled full suite + trend + badges + OWASP/ATLAS mapping.
- **Phase 3:** T3 comparative table vs competitors; publish a reproducible
  blog/research post.

## 11. Affected components

- `benchmarks/` — new `bench_external.py` (dataset loaders + runner),
  `bench_comparative.py`, `datasets/` loaders, `fpr_corpus/`, `baseline.json`,
  extended `generate_report.py`
- `.github/workflows/` — new `benchmark.yml` (T1+T2) and `benchmark-comparative.yml` (T3)
- Optional: pre-baked benchmark image; results-history storage

## 12. Acceptance criteria

- [ ] **T1 gate is live** on PRs: regression in detection **or** FPR fails the build.
- [ ] Our pipeline is scored on **≥3 external attack datasets** beyond our own suite.
- [ ] **FPR reported on ≥2,000 benign prompts** (target a few thousand) with CI.
- [ ] **dev/holdout split** enforced; gate set ≠ tuning set, documented.
- [ ] T2 scheduled job produces a **trend** artifact + refreshed badge.
- [ ] T3 produces a **reproducible comparison table** vs ≥3 competitors on ≥2 shared datasets.
- [ ] Coverage mapped to **OWASP LLM Top 10**.

## 13. Open decisions (pick before Phase 1)

1. **Harness:** in-house only for the gate (recommended) vs adopt garak/promptfoo
   for T2/T3 breadth. *Recommendation: in-house gate + garak/promptfoo in T2/T3.*
2. **CI infra for ML models:** pre-baked Docker image (recommended) vs HF cache
   vs self-hosted runner.
3. **Phase 2/3 timing:** is comparative-vs-competitors in scope now (needs budget
   + keys + light legal review of ToS) or deferred? *Recommendation: defer to
   Phase 3; Phase 1 delivers most of the credibility with none of the cost.*

## 14. Risks / open questions

- **Dataset licensing** for redistribution — verify each; prefer runtime fetch.
- **External provider cost/ToS** — keep out of the blocking gate; cap + cache.
- **Goodhart** — mitigated by §7 (holdout, FPR gate, per-category).
- **CI runtime** — mitigated by pre-baked models; keep T1 lean, push heavy work
  to T2.
- **Comparison fairness** — publish exact competitor configs so the table is
  defensible; that defensibility *is* the asset.
