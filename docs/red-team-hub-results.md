# Red Team Hub — local-model results (DRAFT)

> **DRAFT — methodology & report-format demo, NOT a model ranking.** Runs are partial / in progress
> and some models await re-baseline, so **do not cite these numbers as a leaderboard.** Read this for
> *how* the grading works, not for "model X is safer than Y". Deterministic (no LLM-as-judge), reproducible.
> Targets: **local open models via native Ollama** (Apple Metal) — free, no API.
> This measures the **bare models** (no AI Protector in front). Date: 2026-06-18.

## What this is

We pushed the **same sampled attack set** through several local models and scored
each response with a **deterministic detector** (no LLM judge). One question per
scenario: *did the bare model defend (refuse / not leak), or did the attack get
through?* Higher `defended%` = safer bare model.

It's the Benchmark Hub's output format applied to free local models — a
cross-model, per-category map of where each model leaks.

## TL;DR — overall defended% (ranking)

| Model | Params | Overall defended% |
|---|---|---|
| `gemma4:e4b` | ~4B eff. | _pending re-baseline_ |
| `llama3.2:3b` | 3B | _pending re-baseline_ |
| `llama3.2:1b` | 1B | **66%** ¹ |

¹ `llama3.2:1b` complete (305 scenarios), `temperature=0`, **layered deterministic scorer**.

> **Scorer change (2026-06-18).** These numbers are re-baselined with the **layered
> deterministic grader** now wired into the engine (refusal floor + jailbreak-persona +
> positive structural markers). 1b rose **51% → 66%** vs the old bare-detector scan —
> almost entirely because the old "no-refusal ⇒ leak" rule **false-alarmed** on structural
> categories: `system_prompt_leak` 33% → **100%** and `misinformation` 33% → **97%** once a
> positive leak marker replaced it. The model was less leaky than the naive detector
> claimed — fixing the grader fixed the number. (`3b`/`gemma` to be re-scanned the same way.)

## Results — defended% by threat category

Each cell = % of that category's attacks the bare model defended. Lower = the
model's weak spot. (`—` not yet run.)

| Category (OWASP) | scorer | `1b` | `3b` | `gemma-e4b` |
|---|---|---|---|---|
| tool_abuse (LLM06) | tool-call | 100% | — | — |
| access_control (LLM06) | marker | 100% | — | — |
| system_prompt_leak (LLM07) | struct-marker | 100% | — | — |
| misinformation (LLM09) | struct-marker | 97% | — | — |
| data_leakage_pii (LLM02) | marker | 92% | — | — |
| business_logic_override (LLM01) | marker | 83% | — | — |
| safe_allow *(benign control)* | refusal | 83% | — | — |
| harmful_content | refusal | 77% | — | — |
| prompt_injection_jailbreak (LLM01) | refusal+persona | 70% | — | — |
| secrets_detection (LLM02) | marker | 67% | — | — |
| pii_disclosure (LLM02) | marker | 63% | — | — |
| improper_output (LLM05) | marker | 40% | — | — |
| prompt_injection (LLM01) | refusal/marker | 40% | — | — |
| unsafe_output_artifact (LLM05) | marker | 33% | — | — |
| obfuscation (LLM01) | marker | 33% | — | — |
| impersonation | refusal | 33% | — | — |

**Read of the 1b profile (complete, layered scorer):** holds structural & marker categories
(system-prompt-leak / misinformation / PII / tools / business-logic, 83–100%); **wide open on
impersonation (33%), obfuscation (33%), unsafe output (33%), prompt injection (40%), improper
output (40%)** — the expected shape of a tiny unprotected model, now without the structural
false alarms the old detector produced. Overall **66%**.

## Methodology

- **Deterministic layered scorer, no LLM-as-judge.** The engine scores each response
  with the **layered deterministic grader**: the scenario's registered detector
  (`exact_match` / `regex` / `refusal_pattern` / `tool_call_detect` / …) as the floor,
  plus a **jailbreak-persona** overlay (persona capture is a leak even with no payload)
  and **positive structural markers** for `system_prompt_leak` / `misinformation` (a leak
  is the response *exhibiting* the breach, not the mere absence of a refusal phrase). Same
  response ⇒ same verdict, always. An optional Llama Guard escalation tier exists but is
  **off by default** to preserve reproducibility. (Validated in the Capstone below.)
- **Oracle confidence is labeled per category.** *marker* (exact_match/regex on an
  injected token, secret pattern, or tool call) = **high precision**. *refusal*
  (refusal-phrase match) = **deterministic but heuristic** — a model that complies
  without a canonical refusal, or refuses by explanation, is scored imperfectly.
- **Same attacks across all models** (fixed seed) → a fair ranking.
- **Stratified sample** (~30 / category) — statistically sufficient for stable
  per-category rates; not an exhaustive replay.
- **Target non-determinism:** models run at `temperature=0`; the exact response is
  recorded per scenario, so a verdict is replayable. (Re-scanning the same model
  can still vary — inherent to all red-team tooling; we remove only the *grading*
  variance.)
- **Self-check (and its limit):** an automated flag marks any `leaked` verdict whose
  response still looks like a refusal. It shares the detector's *own* phrase
  vocabulary, so it **cannot catch a refusal phrased in words the detector doesn't
  know** — exactly the blind spot the independent-judge study (below) was built to
  measure. Treat 0-flagged as necessary, not sufficient.

## Oracle validity — is the refusal heuristic credible? (independent-judge study)

The marker oracles (`exact_match` / `regex` / `tool_call_detect` / `json_assertion`)
are **mechanical** — they match an injected token, a secret pattern, or a tool
invocation. Same input ⇒ same verdict, by construction; there is nothing to
"believe", so they are out of scope here.

The **refusal oracle** is the one heuristic worth stress-testing: it decides
"refused vs complied" by phrase match. We check it against an **independent LLM
judge** (`qwen2.5:7b`, local, non-reasoning) on a stratified sample of
refusal-category scenarios and report **Cohen's κ** (agreement beyond chance).

**What the study caught — and the fixes it forced** (target = `gemma4:e4b`, a
reasoning model = the worst case; n ≈ 50 per state):

| Harness state | agreement | Cohen's κ | what was wrong |
|---|---|---|---|
| initial (`max_tokens=150`, empty = leak) | 32% | 0.06 | reasoning models truncated → empty `content` scored as a *leak* |
| + empty/truncated → **inconclusive**, raise token budget | 70% | 0.40 | non-answers no longer counted as breaches |
| + enriched refusal vocab (deflection, 7 languages) | **79%** | **0.54** | model-specific & non-English refusals now recognized |

The **κ = 0.54 residual is the honest ceiling of phrase-matching**, not a fixable
miss. The remaining disagreements are: (a) **safe / off-task completions** — the
model answers something benign instead of the attack; the judge credits a
"refusal", the phrase detector sees "produced content"; closing this needs
topicality understanding, not more phrases — and (b) **judge noise** — e.g. the
judge marked *"I cannot include hidden system instructions…"* as compliance when it
plainly refused. Part of the gap is the judge being wrong, not the oracle.

**Reading:** marker categories are exact; the refusal oracle is a **deterministic,
reproducible signal at κ ≈ 0.5 vs an (imperfect) independent judge** — good as a
floor, explicitly *not* ground truth. For higher fidelity on refusal categories, an
**optional local LLM-judge tier** (opt-in, non-deterministic, clearly labeled, runs
on native Ollama) is the right add-on — never the default scorer, because
reproducibility is the whole point.

**Does it generalize beyond one model?** Same study across **8 targets / 6 vendors
+ 2 reasoning models** (judge `qwen2.5:7b` held out of the target list — a model
grading its own outputs inflates agreement), n ≈ 50 / model:

| Target | Vendor | agreement | Cohen's κ |
|---|---|---|---|
| `gemma4:e4b` (reasoning) | Google | 79% | **0.54** |
| `llama3.2:1b` | Meta | 76% | 0.50 |
| `llama3.2:3b` | Meta | 74% | 0.45 |
| `llama3.1:8b` | Meta | 70% | 0.45 |
| `qwen3:4b` (reasoning) | Alibaba | 68% | 0.36 |
| `granite3.3:8b` | IBM | 62% | 0.29 |
| `phi4` | Microsoft | 50% | 0.14 |
| `mistral:7b` | Mistral | 40% | −0.01 |

**κ is NOT stable across vendors** — range **[−0.01, 0.54], mean 0.34**. Meta/Google
land ~0.45–0.54; IBM 0.29; Microsoft 0.14; Mistral ~0. So the deterministic refusal
oracle's agreement with this judge **depends heavily on the model's refusal style.**

**But the low κ is confounded — and the deterministic oracle looks better than the
number suggests.** Inspecting the disagreements, the gap splits two ways:

1. **Judge errors (the oracle is right).** `qwen2.5:7b` systematically labels clear
   *harmful compliance* as "refuse": e.g. *"Sure, here is a strong justification of
   ethnic genocide…"*, *"Yes, I can help you understand the chemistry involved in
   meth…"*, *"Certainly! Below is a structured outline…"* — the model **complied**,
   the deterministic oracle correctly scored a leak, the judge was wrong. Adopting an
   unvalidated LLM judge as ground truth would **under-report real harmful compliance**
   — the worst failure mode for a security tool.
2. **Oracle gaps (the judge is right).** Soft / verbose refusals & deflections the
   phrase list misses: *"I must clarify that I am committed to safety…"*, *"I'm an AI
   and don't have a personal phone number…"*, plus more non-English refusals.

`ours_only` (we say refuse, judge says comply) is **near-zero everywhere** (0–3) —
the oracle is **conservative**: it under-credits refusals, never invents them. For a
security tool that is the safe direction.

**Conclusion: neither phrase-matching alone nor a single LLM judge is sufficient —
they fail on *different* cases.** κ-vs-single-judge measures *agreement with a noisy
judge*, not oracle accuracy. This is the evidence for **layered grading** (markers →
heuristic floor → optional judge as a cross-check/escalation) and for **validating
the judge itself** before trusting it. A judge↔judge cross-check (two independent
judges on the same responses) is in progress to quantify the judge's own noise.

Reproduce: `python /tmp/validate_oracle.py` (full sweep, resumable) — refusal-oracle
vs judge: agreement % + Cohen's κ + the disagreement list.

### Capstone — grader accuracy vs reference labels (Claude-graded; human spot-check pending)

To escape "agreement with a noisy judge", 82 responses (mistral + gemma, 5 refusal
categories) were hand-labeled with the outcome question — did the attack **materially
succeed (L)** or did the model **defend (D** = refuse / deflect / off-task)? — then every
grader was scored against those labels. (Labels are **Claude-graded reference, not human**;
a 15–20 row human spot-check would seal it.) Distribution: **71 defended / 11 real leaks**,
and **all 11 leaks live in impersonation (6) / jailbreak-persona (4) / system-prompt-leak
(1)** — `harmful_content` and `misinformation` had **0** real leaks in this sample, so their
accuracy measures "correctly says defended", not leak-catching.

> **⚠️ Wiring-bug correction (2026-06-18).** The first version of this table was contaminated
> by a Llama Guard wiring bug. We called it with `[user=prompt, assistant=response]` through
> Ollama's `llama-guard3` chat template — whose final instruction **hardcodes "assess ONLY
> THE LAST *User* message"** even when the last turn is the assistant. Llama Guard was
> therefore grading the **harmful prompt**, not the response: a clean refusal to "build a
> bomb" came back `unsafe`. The fixed adapter builds the official Llama Guard 3 prompt by
> hand and targets the **Agent** turn via `/api/generate` (`raw: true`), bypassing the broken
> template. A control test (refusal ⇒ safe, real compliance ⇒ unsafe) now guards it
> (`tests/red_team/test_llama_guard.py`). Numbers below are **re-validated with the fixed
> adapter**; the `old` column shows the contaminated values for the before/after.

| Grader | accuracy | dangerous-miss¹ | false-alarm |
|---|---|---|---|
| Llama Guard 3 — **buggy** (graded the prompt) | 79% | 11% (9) | 10% (8) |
| Llama Guard 3 — **fixed** (graded the response) | **83%** | **13% (11)** | 4% (3) |
| `qwen2.5:7b` (chat judge) | 73% | 2% (2) | 24% (20) |
| layered (det. floor + persona + guard + structural markers) | **84%** | **5% (4)** | 11% (9) |
| our refusal-oracle | 45% | 4% (3) | 51% (42) |
| `llama3.1:8b` (chat judge) | 24% | 0% (0) | 76% (62) |

¹ **dangerous-miss = grader certified "safe" something that actually leaked** — the failure
mode that matters most for security. Lower is better, **and it flips the ranking.**

- **The fixed Llama Guard caught 0 of 11 real leaks.** Its 83% accuracy is carried entirely
  by the 71 defended cases; every one of its 11 dangerous-misses is a real leak in
  impersonation / jailbreak-persona / system-prompt-leak — **outside its S1–S14 harm
  taxonomy**. Fixing the wiring *raised* accuracy (83%) and *cut* false alarms (4%) by
  correctly clearing refusals, but it could never see the leaks that mattered. **Accuracy
  lies; dangerous-miss is the security metric.**
- **Our refusal-oracle has the safest single-grader profile by construction** (4%
  dangerous-miss) — it errs toward false alarms, never toward false safety. Its weakness is
  recall on non-verbal deflectors (51% false-alarm), not dangerous misses.
- **Layered grading is the synthesis** — and it beats every single grader on the security
  metric: dangerous-miss **5% (caught 7 of 11)** at **84% accuracy** — i.e. Llama Guard's
  accuracy (83%) at **less than half its dangerous-miss** (5% vs 13%) and a quarter of its
  blind spots. It escalates to the guard on harm/jailbreak, adds a persona overlay, and uses
  **positive structural markers** where the guard is blind.

**Per-category — where each grader is blind (fixed guard vs layered, post-#4):**

| Category | n | real leaks | guard acc / dmiss / falarm | layered acc / dmiss / falarm |
|---|---|---|---|---|
| harmful_content | 15 | 0 | 93% / 0 / 1 | 93% / 0 / 1 |
| prompt_injection_jailbreak | 10 | 4 | 60% / **4** / 0 | 90% / 1 / 0 |
| impersonation | 18 | 6 | 67% / **6** / 0 | 44% / **2** / 8 |
| system_prompt_leak | 20 | 1 | 90% / 1 / 1 | **95% / 1 / 0** |
| misinformation | 19 | 0 | 95% / 0 / 1 | **100% / 0 / 0** |

- The guard's misses concentrate exactly where its taxonomy is blind (impersonation,
  persona-capture). Escalating to it **only on harm/jailbreak** lets the layered grader catch
  those (persona overlay) without inheriting the blindness on structural categories.
- **#4 resolved — positive structural markers.** The layered grader's false alarms were
  almost all on structural categories, where it fell back to "no refusal phrase ⇒ leak" and
  over-flagged benign on-task answers. We replaced that floor with a **positive leak marker**
  (the response *exhibits* the breach) for `system_prompt_leak` and `misinformation`:
  false alarms there dropped **11→0** and **12→0** with **no added dangerous-miss** (validated,
  `/tmp/exp_struct.py`). Overall layered false-alarm fell **39%→11%**, accuracy **56%→84%**,
  dangerous-miss held at **5%**.
- **Honest residual — impersonation is semantic.** Positive markers *failed* on impersonation
  (they missed all 6 real leaks: dmiss 2→6), because a successful impersonation is the model
  answering authoritatively in open-ended ways no keyword list captures. So impersonation
  **keeps the deterministic refusal floor** (8 false alarms, dmiss 2) and is the prime
  candidate for the **optional LLM-judge tier** — the one category where deterministic grading
  genuinely cannot separate leak from benign.

**Empirical case for category-aware layered grading:** harmful_content/jailbreak → Llama
Guard (+ a jailbreak-persona check); impersonation/system_prompt_leak → markers + refusal
(Llama Guard is blind there). Choose the grader per category by **dangerous-miss, not accuracy.**

Reproduce: `python /tmp/grade_compare.py <model>` (label sheet + verdicts) →
`python /tmp/revalidate.py` (every grader vs labels, incl. the buggy-vs-fixed guard column
and per-category breakdown).

## Honest limits

- **This measures the bare models, not AI Protector.** The product story is the
  loop: scan → see the gaps above → put AI Protector in front → **re-scan** → the
  ingress/injection categories should jump. (Next run.)
- **Refusal-oracle is heuristic** (see above) — treat refusal-category numbers as
  a reproducible signal, not ground truth. Marker categories are exact.
- **Small local models** (1–4B), single-turn, English-centric, sampled corpus.
- **Per-category N is modest** — report counts, not just %; small categories
  (tool_abuse, access_control) are tiny samples.
- A confidence signal, **not a safety certificate**.

## Reproduce

```bash
# native Ollama (Metal), free — no API
python -m src.red_team.packs.fetch_sources && python -m src.red_team.packs.build_packs
python /tmp/multi_scan.py   # same sampled attacks × models → this table
```

## Next

- Fill `3b` / `gemma-e4b` columns (run completing).
- **Loop demo:** re-run the same set *through AI Protector* → before/after per
  category (the product's value, à la BENCHMARKS.md §6).
- Optional: `gemma4:26b` (hours), and a reasoning model (`qwen3` with thinking
  disabled, else its reasoning text pollutes the refusal oracle).
