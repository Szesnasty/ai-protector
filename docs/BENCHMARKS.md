# AI Protector — Benchmark Matrix

> Deterministic (no LLM-as-judge), reproducible. Hardware: **Apple M4 Pro**.

**Model-agnostic safety layer that cuts harmful-output leakage 5–8× ([§6](#6-without-ai-protector--raw-openai-baseline-defense-in-depth)),
with explicit modes for latency, request-egress boundary, and coverage.**

## ⭐ At a glance

One flag (`HARM_ML_MODE`) trades latency for coverage. Pick a row:

| Mode | Attacks blocked<br>(promptfoo, 1103) | Jailbreaks blocked<br>(JailbreakBench, 698) | False positives<br>(440 benign) | Latency<br>(p50) |
|---|:---:|:---:|:---:|:---:|
| **`off`** — fast · injection/jailbreak/PII *(default)* | **65%** ³ | **99%** | **0%** | **48 ms** |
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

³ `off` runs **no harmful-content classifier** — it is the injection / jailbreak /
PII / toxicity firewall. The 65% is *not* a general "security mode" number;
blocking harmful **requests** is the harm guard's job (`pre_llm`/`post_llm`).

**Why off-mode promptfoo (65%) is lower than JailbreakBench (99%):** the
promptfoo corpus mixes jailbreak/prompt-injection attacks **and genuine-harm
requests** (weapons/drugs/hate). In `off` mode AI Protector prioritizes
injection / jailbreak / PII / toxicity and does **not** run the heavy harm
classifier — which is exactly the 26 pp gap that `pre_llm`/`post_llm` close
(genuine-harm **55% → 92%**). JailbreakBench is pure jailbreaks, caught by the
light layers → 99% in every mode.

**Which to pick — three modes, two different security semantics:**

| Mode | Adds | Security semantics |
|---|---|---|
| **`off`** | injection · jailbreak · PII · toxicity | fast firewall; **no** harmful-content classifier |
| **`pre_llm`** | + harmful **requests**, *before they reach the provider* | **request-egress boundary** — org policy / data-boundary / ToS |
| **`post_llm`** | + harmful **responses**, at fast perceived latency | **response safety + UX latency** — the prompt **still reaches** the provider, you pay for the tokens |

**vs. a bare model:** on the same 1103 attacks, even the strongest raw OpenAI
model (`gpt-5-mini`) leaks **~1 in 4**; weaker ones 34–63%. AI Protector `harm`
stops **90.9%** and cuts any model's leak **5–8×** — see [§6](#6-without-ai-protector--raw-openai-baseline-defense-in-depth).

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
| Date | 2026-06-11 (AI Protector §1–5, re-verified 2026-06-16) · 2026-06-15 (OpenAI baseline §6) |

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

## 6. Without AI Protector — raw OpenAI baseline (defense-in-depth)

> *"If a frontier model already refuses most harmful requests, what does AI
> Protector add?"* This section answers it with numbers. We replayed the **exact
> same 1103-attack corpus** from §3 straight at the OpenAI API — **no proxy, no
> guard, no policy** — and measured what each bare model lets through, then the
> combined system (model **+** AI Protector). Three perspectives below: a single
> shared scale (6.2), the raw leak per model (6.3), and defense-in-depth (6.4).

### 6.1 Methodology — exactly what was measured, and on how many attacks

**The corpus (identical to §3, so the two are directly comparable):**

| Set | Count | Composition |
|---|---:|---|
| **Attacks** | **1103** | 1050 promptfoo red-team (35 plugins × obfuscation strategies) + 53 seed |
| Benign controls | 440 | 428 benign + 12 seed-benign (must **not** be blocked) |
| **Per model** | **1543** | frozen JSONL, sha256 manifest, replayed deterministically |

**Two layers, measured separately, then combined:**

| Layer | Where it acts | "Stopped an attack" means | Tooling |
|---|---|---|---|
| **AI Protector** | request (pre-LLM) | pipeline decision = `BLOCK`/`MODIFY` | §3 — deterministic, no API |
| **Bare model** | generation | model did **not** produce the harmful content | OpenAI Chat Completions |

A bare model's response is scored by a **deterministic refusal classifier** (no
LLM-as-judge) into three buckets — `leak% + refusal% + deflection% = 100`:

- **leak** — model produced the requested harmful content (**the failure**);
- **refusal** — hard decline ("I can't help with that"), in any language;
- **deflection** — capability/identity note or crisis-support, no content emitted
  ("As an AI I don't have the ability to…", a self-harm helpline) — *not* a leak.

**Run parameters & data hygiene** (so the numbers are reproducible):

- 7 models, **1 sample/prompt**, `temperature=0` (reasoning models:
  `reasoning_effort=low`, `max_completion_tokens=3000` to avoid truncated-empty
  reasoning outputs); `max_tokens=80` for the visible answer (a refusal shows in
  the first tokens). **Run date 2026-06-15.**
- Empty (reasoning-truncated) responses are re-run, not counted; `gpt-5.5`'s 49
  platform-moderation `400`s are counted as **defended** (provider blocked the
  request), not as errors. Final dataset: **0 empty, 0 errors** for all 7 models.
- Totals: **11,527 API calls**, ~853K tokens.
- **Defense-in-depth** (6.4) is exact, not assumed-independent: we recorded AI
  Protector's `BLOCK`/`ALLOW` for each of the 1103 attacks and **intersected** the
  100 it allows with each model's compliance set.

### 6.2 Perspective A — one shared scale: % of 1103 attacks STOPPED

Bare model and AI Protector measure different things (generation-refusal vs
request-block), so put both on one axis: **the share of the 1103 attacks that
never became harmful output.** Higher is better.

```
% of 1103 attacks STOPPED  (█ stopped · ░ got through)        higher = better
AI Protector (harm)  ▶ ███████████████████████████░░░  90.9%
gpt-5-mini             ███████████████████████░░░░░░░  75.3%
gpt-5.5                ████████████████████░░░░░░░░░░  66.2%
gpt-4                  ████████████████████░░░░░░░░░░  65.2%
AI Protector (off)   ▶ ████████████████████░░░░░░░░░░  65.0%
gpt-5.1                ███████████████████░░░░░░░░░░░  61.9%
gpt-4o                 ██████████████████░░░░░░░░░░░░  58.8%
gpt-4.1                ████████████████░░░░░░░░░░░░░░  52.1%
gpt-3.5-turbo          ███████████░░░░░░░░░░░░░░░░░░░  37.4%
```

- **`harm` mode (90.9%) beats every bare model**, including the best (`gpt-5-mini`
  75.3%).
- **`off` mode (65%)** lands mid-pack — about a strong-but-not-frontier model — by
  design: it runs no harm classifier (it is the fast path for injection /
  jailbreak / PII).
- A frontier model's own safety is real but **not sufficient**: the best still
  lets 1 in 4 through; the rest 34–63%.

### 6.3 Perspective B — raw leak per model (no protection at all)

```
Leak rate — bare model, no AI Protector  (█ leaked)           lower = better
gpt-5-mini     ███████·······················  24.7%
gpt-5.5        ██████████····················  33.8%
gpt-4          ██████████····················  34.8%
gpt-5.1        ███████████···················  38.1%
gpt-4o         ████████████··················  41.2%
gpt-4.1        ██████████████················  47.9%
gpt-3.5-turbo  ███████████████████···········  62.6%
```

| Model (release) | **Leak** | Refusal | Deflection | Benign over-refusal |
|---|:---:|:---:|:---:|:---:|
| `gpt-3.5-turbo` (2022) | **62.6%** | 35.3% | 2.2% | 3.4% |
| `gpt-4` (2023) | **34.8%** | 57.4% | 7.8% | 0.0% |
| `gpt-4o` (2024) | **41.2%** | 54.2% | 4.6% | 0.2% |
| `gpt-4.1` (2025) | **47.9%** | 47.3% | 4.8% | 0.0% |
| `gpt-5-mini` (reasoning) | **24.7%** | 66.8% | 8.5% | 0.0% |
| `gpt-5.1` (reasoning) | **38.1%** | 48.7% | 13.2% | 0.5% |
| `gpt-5.5` (reasoning, 2026) | **33.8%** ¹ | 60.5% | 5.7% | 0.0% |

¹ `gpt-5.5` also hard-blocked **49** attacks at OpenAI's **input moderation**
(HTTP 400 "cybersecurity risk": cybercrime / malware / PII / prompt-injection) —
counted as defended.

- **Newer ≠ safer.** The cautious original `gpt-4` (34.8%) refuses more than the
  newer, more *helpful* `gpt-4o`/`gpt-4.1` (41–48%). The small reasoning model
  `gpt-5-mini` beats every flagship.

### 6.4 Perspective C — defense-in-depth (model **+** AI Protector `harm`)

The two layers are independent, so an attack must beat **both**. Combined leak =
attacks AI Protector allowed **and** the model complied with (exact intersection):

```
Residual leak — model ALONE vs model + AI Protector (harm)    lower = better
gpt-3.5-turbo  alone  ███████████████████···········  62.6%
               +AIP   ██····························   8.3%   (7.6× less)
gpt-4.1        alone  ██████████████················  47.9%
               +AIP   ██····························   7.9%   (6.1× less)
gpt-4o         alone  ████████████··················  41.2%
               +AIP   ██····························   7.1%   (5.8× less)
gpt-5.1        alone  ███████████···················  38.1%
               +AIP   ██····························   6.0%   (6.4× less)
gpt-4          alone  ██████████····················  34.8%
               +AIP   ██····························   6.3%   (5.5× less)
gpt-5.5        alone  ██████████····················  33.8%
               +AIP   █·····························   4.1%   (8.3× less)
gpt-5-mini     alone  ███████·······················  24.7%
               +AIP   █·····························   3.4%   (7.2× less)
```

> **AI Protector cuts the leak rate 5–8× regardless of which model is behind it.**
> Best pairing (`gpt-5-mini`): **24.7% → 3.4%** (1-in-4 becomes 1-in-29). Biggest
> absolute win on cheap/old models (`gpt-3.5-turbo`: 62.6% → 8.3%). Unlike a
> single model it is **model-agnostic** and blocks **before** the request leaves
> your system (§1, ²). The residual ~3–8% is concentrated in borderline classes
> (`overreliance`, `hijacking`, `specialized-advice`, `copyright`).

### 6.5 Limitations of this baseline

- **Refusal classifier is a heuristic.** It matches refusal/deflection substrings
  (incl. multilingual refusals and crisis-support phrasings). It does **not**
  judge whether a compliant answer is *operationally* harmful, so **leak is an
  upper bound** on real harm. Reasoning models that refuse by *explanation*
  ("you shouldn't, because…") rather than a canonical phrase are slightly
  over-counted as leaks (~1% of `gpt-5.1`).
- **Not apples-to-apples with §3.** AI Protector's number is request-layer
  *blocking*; the model number is generation-layer *refusal*. Both are reported
  so the gap is visible, not conflated.
- **Single-turn, English-centric corpus**, one sample per prompt (temp 0). Model
  numbers are provider snapshots on the 2026-06-15 run date and will drift.

### Reproduce

```bash
cd apps/proxy-service
export OPENAI_API_KEY=sk-...
python -m benchmarks.bench_baseline_openai            # raw leak rates, all default models
python -m benchmarks.bench_baseline_openai --resume   # backfill empties/errors, re-aggregate
# defense-in-depth: capture the protector's per-attack decisions, then intersect
HARM_ML_MODE=pre_llm python -m benchmarks._capture_protector_decisions
```

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
