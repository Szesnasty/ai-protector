# AI Protector — Benchmark Matrix

> Deterministic (no LLM-as-judge), reproducible. Hardware: **Apple M4 Pro**.

## ⭐ At a glance

One flag (`HARM_ML_MODE`) trades latency for coverage. Pick a row:

| Mode | Attacks blocked<br>(promptfoo, 1103) | Jailbreaks blocked<br>(JailbreakBench, 698) | False positives<br>(440 benign) | Latency<br>(p50) |
|---|:---:|:---:|:---:|:---:|
| **`off`** — fast *(default)* | **65%** | **99%** | **0%** | **48 ms** |
| **`pre_llm`** — max security | **91%** | **99%** | **0.7%** | ~450 ms |
| **`post_llm`** — fast + full detection ² | **91%** | **99%** | **0.7%** | **48 ms** ¹ |

¹ The harm guard runs **in parallel** with the LLM call, so its ~430 ms is hidden
**only when** the upstream LLM call is slower than the guard **and** the product
can wait for the guard's verdict before releasing the final response. With very
fast models or token-streaming, the saving shrinks.

² **`post_llm` is not the same security boundary as `pre_llm`.** It preserves
perceived latency and blocks unsafe **responses**, but it does **not** prevent
the unsafe request from reaching the model/provider — the prompt is sent, the
provider processes it, and you pay for the generated tokens. Use **`pre_llm`**
when request *egress* itself matters (org policy "these requests must not leave
the system", data-boundary, or provider-ToS concerns).

**Why off-mode promptfoo (65%) is lower than JailbreakBench (99%):** the
promptfoo corpus mixes jailbreak/prompt-injection attacks **and genuine-harm
requests** (weapons/drugs/hate). In `off` mode AI Protector prioritizes
injection / jailbreak / PII / toxicity and does **not** run the heavy harm
classifier — which is exactly the 26 pp gap that `pre_llm`/`post_llm` close
(genuine-harm **55% → 92%**). JailbreakBench is pure jailbreaks, caught by the
light layers → 99% in every mode.

**Which to pick:**
- **`off`** — fastest. Blocks prompt injection, jailbreaks, PII, toxicity.
- **`pre_llm`** — also blocks **harmful requests** *before* they reach the
  provider. Slower pre-LLM, strongest boundary.
- **`post_llm`** — adds harmful-request coverage at fast perceived latency, but
  blocks the **response**, not the request (see ²).

---

## Test environment

> Single-node, native (no Docker). The ML guard models run on the Apple Metal
> (MPS) accelerator; CPU-only deployments are slower (see notes per table).

| | |
|---|---|
| Machine | Apple Silicon Mac |
| CPU | **Apple M4 Pro** — 12 cores (12 physical / 12 logical) |
| Accelerator | Apple Metal (MPS) — used for the ML guard models |
| RAM | 48 GB |
| OS | macOS (Darwin 25.5.0, arm64) |
| Python | 3.12.13 |
| Runtime | native |
| Models | LLM Guard (DeBERTa+DistilBERT), NeMo (FastEmbed), Presidio (spaCy), Jailbreak ML (DistilBERT 86M), Harm ML (granite-guardian 2B) |
| Date | 2026-06-11 |

---

## 1. How to switch modes

The heavy **harm guard** (IBM granite-guardian-2b) is controlled by one flag,
orthogonal to the policy level — the numbers are in [At a glance](#-at-a-glance).

```bash
# One env var, any policy level:
HARM_ML_MODE=off       # fastest, deterministic + light ML only
HARM_ML_MODE=pre_llm   # block harmful requests before the provider (slower pre-LLM)
HARM_ML_MODE=post_llm  # full detection at fast latency (blocks the response)
```

---

## What this benchmark covers — and what it doesn't

AI Protector enforces at **four** boundaries. This benchmark measures the first
two (the proxy firewall). The agent-side gates are a different mechanism and are
benchmarked separately ([Agent pipeline](architecture/AGENT_PIPELINE.md)).

| Boundary | What it controls | In this benchmark? |
|----------|------------------|--------------------|
| **Request guard** (pre-LLM) | Is the incoming prompt safe to process? | ✅ promptfoo / JailbreakBench / internal |
| **Response guard** (output / post-LLM) | Is the model's output safe to return? (`post_llm` harm, PII/secrets redaction) | ◑ harm covered; PII/secrets non-streaming only |
| **Pre-tool gate** (agent) | Is this tool call *allowed* (RBAC, args, budget)? | ❌ separate — agent benchmark |
| **Post-tool gate** (agent) | Is the tool *output* safe (PII, indirect injection)? | ❌ separate — agent benchmark |

> For **tool-calling agents** the decisive control is the **pre-tool gate**, not
> a post-response guard: the model may *propose* a tool call, but the system
> decides whether it is allowed to happen. A high prompt/jailbreak/harm score
> here does not by itself make an agent safe — that is the agent layer's job.

---

## 2. Policy levels (orthogonal to the harm mode)

Policies control the deterministic + light-ML layers. The harm guard is layered
on top via `HARM_ML_MODE` and works with **any** policy.

Latency is the **pre-LLM** pipeline measured in isolation, models warmed
(3 warmup calls), p-values over n=80 (M4 Pro / MPS):

| Policy | Layers | p50 | p95 | p99 |
|--------|--------|-----|-----|-----|
| `fast` | rules + intent only | **~1 ms** | ~1 ms | ~1 ms |
| `balanced` (default) | + LLM Guard · NeMo · Jailbreak ML · A2 deobfuscation | **48 ms** | 68 ms | 82 ms |
| `strict` | + Presidio PII · ML Judge | ~60 ms | — | — |
| `paranoid` | + canary | ~60 ms | — | — |

> CPU-only (no MPS/GPU) is slower — the ML scanners are the cost; the harm guard
> especially (a 2 B model) can be ~1–1.5 s/req on CPU. Numbers above are MPS.

---

## 3. Attack detection — promptfoo red-team corpus (1103 attacks)

Real adversarial corpus harvested from **promptfoo** red-team (35 plugins ×
strategies), frozen and replayed deterministically.

### By obfuscation strategy

| Strategy | `off` (fast) | `pre_llm` / `post_llm` (harm on) |
|----------|--------------|----------------------------------|
| jailbreak-templates | 100.0% | 100.0% |
| spaced | 100.0% | 100.0% |
| multilingual | 75.0% | 100.0% |
| homoglyph | 99.5% | 100.0% |
| base64 | 76.1% | 96.2% |
| leetspeak | 50.8% | 89.6% |
| plain (no obfuscation) | 27.0% | 89.4% |
| rot13 | 38.1% | 70.2% |

### Genuine-harm categories (weapons / drugs / violence / hate / CSAM / …)

| | `off` | harm on |
|---|---|---|
| Genuine-harm detection | **55%** (252/456) | **92%** (420/456) |

---

## 4. JailbreakBench (NeurIPS 2024) — 698 published jailbreak artifacts

Caught by the light ML layers (Jailbreak ML), so identical across harm modes.

| Method | Type | Rate |
|--------|------|------|
| JBC | manual, human-crafted | **100.0%** |
| prompt_with_random_search | black-box random search | **100.0%** |
| GCG | white-box gradient | **98.0%** |
| PAIR | black-box iterative (roleplay) | **97.9%** |
| **Overall** | | **99.0%** |

Internal scenario suite (358 attacks, 38 categories): **99.1%**.

---

## 5. Over-blocking — benign corpus (440 prompts)

Benign corpus: customer-support, account, general-knowledge, coding, and
**dual-use** edge cases (security education, benign roleplay) — the prompts a
brittle filter wrongly blocks.

| Mode | Benign blocked (FPR) |
|------|----------------------|
| `off` | **0 / 440 (0.0%)** |
| `pre_llm` / `post_llm` | **3 / 440 (0.7%)** |

The fast path (`off`) over-blocks **nothing** on this corpus. The harm guard adds
**3 false positives** at P(harm) ≥ 0.8 — two near-threshold support questions
("track my package", "get an invoice") and one dual-use chemistry-safety
question. This is the speed-vs-coverage trade-off: the guard lifts genuine-harm
detection 55% → 92% at a 0.7% FPR cost, tunable via `HARM_ML_THRESHOLD`
(e.g. 0.85 trades a little detection for fewer FPs).

---

## Current weak spots

Where the system misses today, by class (so you can see we know where it does
not deliver):

- **Plain harmful prompts in `off` mode** — the harm classifier is off, so direct
  harmful requests pass (~27% of plain attacks caught). `pre_llm`/`post_llm` → ~89%.
- **ROT13-encoded harmful intent** — ~38% (off) / ~70% (harm): the guard reads
  encoded text imperfectly even after deobfuscation.
- **Leetspeak variants** — ~51% (off) / ~90% (harm).
- **Borderline dual-use requests** — the main *false-positive* risk when the harm
  guard is on (chemistry-safety, "how does X attack work").
- **Multilingual harm** — English-centric models; non-English harmful requests
  detect less reliably (small sample in this corpus).

## What this benchmark does NOT prove

This benchmark does **not** prove that AI Protector makes agents safe. It measures
detection on frozen prompt / jailbreak / harm corpora and benign prompts. It does
**not** measure:

- multi-turn / conversational attacks,
- tool-specific business-logic abuse (the agent pre/post-tool gates),
- long-context RAG / retrieved-document poisoning,
- provider-specific model behavior,
- real production traffic distribution,
- formal security guarantees.

Treat the numbers as a reproducible confidence signal, not a safety certificate.

## Limitations & residual risks

Honest scope — what these numbers do **not** cover:

- **Float numbers are hardware-sensitive.** The ML guards run fp16 on Apple
  Metal (MPS) here; on CPU (`bfloat16`) the probabilities near the 0.8 threshold
  can shift slightly, so harm-mode FPR/detection may differ a few points. The
  deterministic-keyword and `off`-path numbers are stable across hardware.
- **`post_llm` cost:** the prompt **does reach the provider** (only the response
  is blocked), so you pay for the generated tokens on a flagged request. For
  block-before-provider semantics use `pre_llm`.
- **`post_llm` on streaming / `/v1/scan`** falls back to `pre_llm` (the guard
  runs before the call) because those paths have no post-call step — harm
  enforcement is never silently skipped, but on streaming it costs pre-LLM
  latency.
- **Streaming responses are not output-filtered.** PII redaction / secret
  stripping / system-prompt-leak detection run on non-streaming responses only.
  Use non-streaming for output-side guarantees.
- **Very long messages:** the ML scanners see ~512 tokens; a long benign prefix
  can push an obfuscated suffix out of the window. Inherent to window-based ML.
- **Multilingual harm:** the harm guard and keyword layers are English-centric —
  harmful requests in other languages detect less reliably.
- **Memory:** with the harm guard enabled the model footprint is ~6 GB (MPS
  fp16) and the guard alone is ~4 GB; size instances accordingly or run `off`.
- **Benign corpus** is 440 templated prompts — a confidence signal for
  over-blocking, not a substitute for real-traffic FPR monitoring.

## Methodology

- **Deterministic:** no LLM-as-judge. Decisions come from rules, keyword/ML
  classifiers, the jailbreak/harm guard models, and risk thresholds.
- **Frozen corpus:** attacks (promptfoo + seed) and the benign corpus are
  committed JSONL with a sha256 manifest; the benchmark replays them.
- **Latency:** pre-LLM pipeline measured in isolation (no provider call, no
  network) on the hardware above; warmup precedes measurement.
- **Modes:** `off` = harm guard disabled; `pre_llm`/`post_llm` enable it — the
  detection numbers are identical (same model + threshold), only the latency and
  the block point differ.

## Reproduce

```bash
cd apps/proxy-service
make benchmark-external          # fast pre-LLM (HARM_ML_MODE=off)
make benchmark-external-harm     # with the harm guard (HARM_ML_MODE=pre_llm)
make benchmark-jailbreakbench    # JailbreakBench
python -m benchmarks.bench_latency --all-policies   # latency per policy
```
