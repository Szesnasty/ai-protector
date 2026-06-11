# Next-Steps Plan — Detection Credibility & Defense-in-Depth

> Coarse-grained specs ("big blocks") for the next wave of work.
> Each file is one deliverable. Detail is intentionally high-level for now —
> these are scoping documents, not implementation guides.

Two tracks, derived from the project review:

- **Track A — Detection credibility + benchmarks.** Make detection harder to
  evade and make the numbers *citable* (comparative, continuous, real FPR).
  This is the content acquirers and the market actually read.
- **Track B — Additional security layers.** Close the defense-in-depth gaps
  that show up in due diligence (phantom features, indirect injection, output
  side, DoS).

## Index

| # | Spec | Tracks issue | Priority | Rough effort | What it buys |
|---|------|--------------|----------|--------------|--------------|
| A1 | [ML intent classifier](A1-ml-intent-classifier.spec.md) ✅ | ISS-005 | High | M–L | **Implemented** — JailbreakBench 81.2%→99.1%, PAIR 53.6%→97.9%, 0 model FP |
| A2 | [Deobfuscation / normalization](A2-deobfuscation-normalization.spec.md) ✅ | ISS-012 | High | S–M | **Implemented** — leetspeak 25%→100%, external 86.8%→100%, FPR still 0% |
| A3 | [Comparative + continuous benchmark](A3-comparative-continuous-benchmark.spec.md) | — | High | M–L | Umbrella: 3-tier benchmark architecture, turns self-graded numbers into cited evidence |
| **A3a** | [**External deterministic attacks + CI gate**](A3a-external-deterministic-attacks.spec.md) | — | **High — start here** | M | **Current focus.** promptfoo/garak attacks → our pipeline → PR gate |
| B1 | [Indirect / second-order injection](B1-indirect-injection-detection.spec.md) | — | High | M | 2026 frontier; fits "what the model *does*" |
| B2 | [Canary tokens + ML Judge (de-vaporize)](B2-canary-and-ml-judge.spec.md) | ISS-003, ISS-004 | Med | S–M | Removes advertised-but-dead features before DD |
| B3 | [Output-side hardening](B3-output-side-hardening.spec.md) | ISS-007, ISS-010 | Med | S–M | Robust leak/secret detection on responses |
| B4 | [Optional LLM-judge tier](B4-optional-llm-judge-tier.spec.md) | — | Med | M | Semantic tail coverage, determinism preserved |
| B5 | [Proxy rate limiting / DoS](B5-proxy-rate-limiting.spec.md) | ISS-008 | Med | S | Volume/cost controls proxy currently lacks |

## Dependency notes

- **A1** is foundational: its model is reused by **B1** (indirect injection),
  **B2** (ML Judge chip), and informs **B4** (judge routing band).
- **A2** feeds **B1** — tool/RAG content must be normalized before scanning too.
- **B2** canary reuses the `${CANARY}` machinery already present in the
  red-team engine ([run_engine.py](../../apps/proxy-service/src/red_team/engine/run_engine.py)).
- Several specs converge on **shared detector modules** (injection, secrets) so
  proxy and agent stop maintaining divergent regex lists.

## Suggested order

1. A2 (fast, unblocks honest benchmark numbers) →
2. A1 (the real detection upgrade) →
3. A3 (measure it, comparatively, continuously) →
4. B1 + B3 (defense-in-depth on the content/output sides) →
5. B2 + B5 (DD hygiene + ops) →
6. B4 (optional semantic tier, last).

## Current focus

**A3a — external deterministic attacks + CI gate.** The actionable Tier 1 / Phase 1
slice of A3: harvest attacks from **promptfoo / garak / static datasets**, freeze
them into a versioned corpus, and **replay deterministically through our pipeline
as a PR regression gate**. No competitor benchmarking yet (that's A3 Tier 3,
deferred). Key principle: *generate once (offline, LLM-based) → freeze → replay
(in CI, deterministic)*. The obfuscation strategies it harvests
(`base64/leetspeak/rot13/multilingual`) double as the regression test for A2.

**Iteration 1 locked:** promptfoo · harvest-and-freeze · proxy surface only. The
concrete build plan (files, `manifest.json` format, `benchmark.yml` skeleton,
gate logic, DoD) is in [A3a §13](A3a-external-deterministic-attacks.spec.md#13-iteration-1--implementation-plan).

**✅ Iteration 1 is implemented** (see [A3a §15](A3a-external-deterministic-attacks.spec.md#15-status--implemented-iteration-1)).
The benchmark exposed the A2 gap (leetspeak 25%), **A2 was then implemented**
([`deobfuscate.py`](../../apps/proxy-service/src/pipeline/utils/deobfuscate.py)),
and the gate now reads **detection 100% / FPR 0%** on the seed corpus (was 86.8%).
Same change lifted the internal suite 97.6%→98.8% with no new false positives.
Run locally with `make benchmark-external-gate`.
