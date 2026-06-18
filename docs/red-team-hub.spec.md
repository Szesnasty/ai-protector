# Red Team Hub — Benchmark aggregator for AI security

> **Track:** A (detection credibility) — product surface
> **Priority:** High
> **Effort:** L (iterative)
> **Status:** 🟡 In progress — JailbreakBench pack landed (698, auto-listed); branch `feat/red-team-hub`
> **Branch:** `feat/red-team-hub` (off `main`)

---

## 1. Goal & positioning

Evolve the existing **Security Scan / Red Team** view into a **Benchmark Hub**: a
multi-select of AI-security attack packs that run against *any* OpenAI-compatible
endpoint and produce a **deterministic, reproducible, auditable** score — plus a
one-click path to remediation (AI Protector's protection layer).

Think **Nuclei / OWASP ZAP / Burp** for AI: aggregate the field's best attack
suites under one unified schema and UX. **Stays a module of AI Protector** (not a
separate product) until it lives its own life; the natural upsell is the loop.

**The loop (the whole story):**
```
1. Connect endpoint  2. Run Red Team Scan  3. Find gaps
4. Enable protection 5. Re-scan           6. Prove the improvement
```

**The moat is NOT the benchmarks** (they are open-source, commodity — a full
JailbreakBench pack was ~80 lines → 698 scenarios). The moat is the **layer**:
unified schema · deterministic oracle (no LLM-as-judge) · **remediation** ·
auditable/reproducible results · (long-term) aggregated cross-run data.

**Brand lens (primary goal — courses/workshops):** the Hub is a content &
credibility engine — model rankings, bypass-trend posts, "how to validate your
AI's security" workshop backbone. It feeds the brand as much as the product.

### Guiding principle — curated, not volume

**The value is the loop (find → fix → prove) + remediation, NOT the attack
count.** "We run thousands of attacks" is vanity: 5000 near-duplicates tell you
no more than 50 well-chosen ones, and in real life teams scan in *bursts*
(pre-launch, audit), not obsessively. Optimize for **time-to-answer + a clear
verdict + the fix** — ship the *experience*, not the corpus. A result is
`score → critical findings → top fixes → re-scan`, never a wall of 5000 rows.

### v1 scope (MVP) — 3 packs, shippable now

- **Core Security (your ~50)** — the HIGH-confidence **anchor**: `exact_match`
  marker oracle + `fix_hints` (remediation) + real-world business-logic attacks.
  This is the *differentiated* pack — lead with it, not with the big ones.
- **JailbreakBench (698)** ✅ — breadth + a recognized name (refusal oracle,
  labeled heuristic).
- **promptfoo (injection/obfuscation)** — second recognized name + marker oracle
  on part of it.

Mix = HIGH anchor (yours) + breadth with borrowed credibility (JBB/promptfoo),
with honest per-pack oracle labels. **Named gap deferred to v2: indirect/agent
(BIPIA)** — i.e. the "what it *does*" thesis; ship v1 knowing it's missing.

### Selection model — category-first (taxonomy TBD)

The select's primary axis is the **threat category**, not the pack. Users think
in threats ("test my injection / PII / tool-abuse risk"), not in "run promptfoo".

- **Primary:** pick category(ies) → the engine runs matching scenarios **across
  all selected packs**. **Secondary:** narrow by pack/source (also the credibility
  attribution — "these 40 injection attacks came from promptfoo + JBB + Core").
- **Output is per-category** ("Prompt Injection 92% · PII 81% · Tool Abuse 74%") —
  the most useful verdict *and* the best brand content (rankings by category).
- This is the **Nuclei (tags) / ZAP (policies)** model — what turns a big library
  from overwhelming into *targeted* (the answer to "nobody checks thousands").

**Enabler = unified category taxonomy.** Each pack ships native categories
(core_security: `prompt_injection`/`secrets_detection`/…; promptfoo: plugin names;
JBB: `prompt_injection_jailbreak`). Cross-pack category-select needs a map from each
pack's native categories → a **shared set**. This is the "unified schema" moat.

> **Deferred on purpose:** the concrete shared category set is **not** defined
> top-down now. Derive it **empirically once the v1 packs are in** — from the
> categories that actually appear in Core Security + JailbreakBench + promptfoo —
> then map. Bottom-up from real packs beats a speculative taxonomy.

**UX caution:** category-first, pack/source as a collapsible secondary filter —
not a 3-D checkbox maze (pack × category × severity).

---

## 2. Why it matters

- **Easier sale than a firewall:** *"let's check if you have a problem"* beats
  *"buy protection for a problem we haven't proven"*. Benchmark = free entry,
  protection = premium → PLG funnel.
- **Remediation is the unfair advantage:** promptfoo / garak / PyRIT **report**;
  AI Protector reports **and offers the fix** (`[Enable Prompt Protection]`,
  `[Enable Tool RBAC]`). Pure-report tools have lower business value.
- **Aggregated data (long-term):** which attacks pass, which models fail, which
  defenses work, bypass trends — data single-benchmark authors don't have. Feeds
  back into improving AI Protector. (Chicken-and-egg: needs scale; privacy/consent
  required — collecting what passes against customer endpoints.)

---

## 3. Current state (what already exists)

Most of the hard infrastructure is **already built and working** — this is an
extension, not a from-scratch build.

| Piece | Status | File |
|---|---|---|
| Pack auto-discovery (`data/*.yaml\|json` → registered) | ✅ verified | [packs/loader.py](../apps/proxy-service/src/red_team/packs/loader.py) |
| Deterministic detector registry (7 types) | ✅ | [evaluators/detectors.py](../apps/proxy-service/src/red_team/evaluators/detectors.py), [registry.py](../apps/proxy-service/src/red_team/evaluators/registry.py) |
| Severity-weighted scoring | ✅ | [scoring/calculator.py](../apps/proxy-service/src/red_team/scoring/calculator.py) |
| Engine / worker / target adapters | ✅ | [engine/run_engine.py](../apps/proxy-service/src/red_team/engine/run_engine.py), [engine/adapters.py](../apps/proxy-service/src/red_team/engine/adapters.py) |
| Target form (URL, headers, `{{PROMPT}}` body) | ✅ | RedTeamTargetForm.vue |
| PDF export + business impact | ✅ | [export/renderer.py](../apps/proxy-service/src/red_team/export/renderer.py), [export/business_impact.py](../apps/proxy-service/src/red_team/export/business_impact.py) |
| Run API | ✅ **but single-pack** (`create_run(pack: str)`) | [api/service.py](../apps/proxy-service/src/red_team/api/service.py), [api/routes.py](../apps/proxy-service/src/red_team/api/routes.py) |
| Built-in packs | core_security (51), core_verified (23), extended_advisory (25), unsafe_output (5), agent_threats (3) | packs/data/ |
| **JailbreakBench pack** | ✅ **landed** (698, auto-listed) | packs/data/jailbreakbench.yaml |

Deterministic detector types available: `regex`, `keyword`, `heuristic`,
`refusal_pattern`, `exact_match`, `tool_call_detect`, `json_assertion`. **No
LLM-as-judge** anywhere — that is the property to preserve.

---

## 4. Two integration modes

How a source is integrated determines effort — be explicit per source.

- **Import** — extract the payloads → normalize to our scenario schema → attach
  one of *our* deterministic detectors. Works for sources whose attacks are
  essentially **static prompts**. Easy (≈ a day each). Proven with JBB.
- **Orchestrate / wrap** — run the tool as a subprocess/lib → parse its report →
  normalize into our schema. Needed for **dynamic** tools (adaptive generation,
  multi-turn, simulated environments). Heavier, and **inherits their scoring
  (often LLM-judge)** → a brand cost. Deferred.

---

## 5. Final pack roster (the select) — deterministic only

Grouped by **oracle confidence**, because that decides how a "92%" is read. The
UI must show the oracle type per pack.

### 🟢 HIGH — marker / regex oracle (unambiguous, high precision)
Attack injects a marker/action → `exact_match`/`regex`. Verdict is bulletproof.

| Pack | Class | Detector | License | Mode |
|---|---|---|---|---|
| Core Security / Verified / Extended / Unsafe Output (built-in) | injection, secrets, output | exact_match/regex | — | ✅ have |
| Agent Threats (built-in) | tool abuse | tool_call_detect | — | ✅ (needs tool target) |
| **BIPIA** (Microsoft) | indirect injection (email/QA/web) | exact_match/regex | MIT | import — **fills the indirect gap** |
| **promptfoo: Injection & Obfuscation** (ascii-smuggling, special-token, system-prompt-override, sql/shell) | injection/format | exact_match/regex | MIT | import (have harvest) |

### 🟡 MED — refusal oracle (deterministic but heuristic)
Model *should refuse*; check refusal phrases (`refusal_pattern`). Reproducible,
no LLM-judge — but lower precision (model can comply without canonical refusal).
**Label this on the pack card.**

| Pack | Class | License | Mode |
|---|---|---|---|
| **JailbreakBench** | jailbreak (GCG/PAIR/JBC/RS) | MIT | ✅ landed (698) |
| **HarmBench** | harmful (7 categories) | MIT | import |
| **AdvBench** (Zou/GCG `harmful_behaviors`) | harmful + adversarial suffix | MIT | import (one CSV) |
| **Do-Not-Answer** (LibrAI) | categorized refuse-expected | Apache | import |
| **In-the-Wild Jailbreaks** (TrustAIRLab) | real DAN-style | check | import (have) |
| **garak: static probes** (dan/encoding/malwaregen/xss) | mixed | Apache | import static probes only |

### 🔀 Obfuscation multiplier (toggle, not a pack)
Apply base64 / rot13 / leet / homoglyph / multilingual to *any* selected pack via
the existing [strategies.py](../apps/proxy-service/benchmarks/external/strategies.py);
check the decoded marker. Deterministic (HIGH), free ×N coverage.

### ⛔ Deferred / out (cannot bite deterministically as a flat pack)
- **PyRIT** (crescendo/TAP) — multi-turn + LLM-judge. Only seed prompts are
  importable; full engine is a different product surface.
- **AgentDojo (full)** — oracle *is* deterministic ("did the agent perform the
  injected action") but needs the agent embedded in their environment → agent
  track, later.
- **deepset/prompt-injections** — great for **A4 classifier training**, weak as a
  scan pack (no per-prompt marker → ambiguous oracle). Keep in training, not here.
- **"Is this content dangerous" as a judgment** — that would be an LLM-judge. We
  approximate via refusal; we do **not** ship a content judge.

---

## 6. Determinism & reproducibility

**Honest decomposition — three layers:**
1. **Corpus** — frozen + sha256 + versioned → fully reproducible. ✅ (existing
   pattern in [benchmarks/external](../apps/proxy-service/benchmarks/external/)).
2. **Oracle / detector** — deterministic → same input ⇒ same verdict, always.
   No LLM-judge ⇒ no grading variance. ✅ **This is the differentiator.**
3. **Target response** — the tested model is **not** deterministic (temperature,
   version drift, provider changes). The *same* endpoint can score differently
   run-to-run. This is **irreducible and shared by all red-team tools** —
   AI Protector's edge is removing the *grading* variance, leaving only this.

**Oracle precision ≠ reproducibility:** marker/`exact_match` = reproducible *and*
true; `refusal_pattern` = reproducible but *heuristic* (a proxy). Both honest **if
labeled**.

**The claim competitors cannot make:** *"re-run → same verdict from the same
response — and we show you the response."* Auditable + replayable.

**Bulletproof checklist (mostly already have):**
1. Pack frozen + sha256 + version.
2. Deterministic detector per scenario, **oracle-type labeled**.
3. Record per scenario: exact request, **response**, model version, timestamp →
   auditable replay.
4. `temperature=0` + **N samples** for non-deterministic targets → report rate +
   variance, not a point estimate.
5. Per-pack **oracle-confidence badge** in UI and PDF.

---

## 7. Architecture & work breakdown

1. **Pack adapters (import mode)** — per source: harvest → normalize to scenario
   schema with a deterministic detector + metadata. Generator scripts, frozen
   output. (JBB done as the reference pattern.)
2. **Pack metadata** — extend the `Pack`/`PackInfo` schema with `source`,
   `license`, `version`, `oracle_confidence` (high|heuristic). NB: dataclasses are
   `frozen, slots` — add fields explicitly; keep yaml back-compatible.
3. **Multi-pack run** — the run model is **single-pack** today (`create_run(pack:
   str)`). Change to `packs: list[str]`: merge selected packs' scenarios into one
   run, **tag each scenario with its origin pack** (enrichment/fix-hints/PDF resolve
   per-origin). Touch `api/service.py`, `api/routes.py`, the run DB model, and
   `compare_runs` (today asserts `run_a.pack == run_b.pack`).
4. **Frontend multi-select** — pack picker cards (name, source, count, license,
   severity mix, **oracle-confidence badge**). The "Test Your Endpoint" view +
   PDF already exist.
5. **Auditable run record** — persist request/response/model/timestamp per
   scenario (extend if not already complete).
6. **Obfuscation toggle** — apply `strategies.py` transforms to selected packs at
   run time; decoded-marker detector.
7. **Rankings view (brand)** — same packs across models → comparison table
   (reuses §6 baseline data shape).

---

## 8. Pack metadata schema (target)

```yaml
name: jailbreakbench
display_name: JailbreakBench
version: 1.0.0
source: "JailbreakBench/artifacts"      # attribution
license: MIT                            # for redistribution honesty
oracle_confidence: heuristic            # high | heuristic
description: "NeurIPS 2024 published jailbreak artifacts (GCG/PAIR/JBC/RS)."
scenario_count: 698
applicable_to: [chatbot_api, tool_calling]
scenarios: [ { id, title, category, severity, prompt, expected, detector, fix_hints, ... } ]
```

---

## 9. Affected components

- `red_team/packs/loader.py` — metadata fields (`source`/`license`/`oracle_confidence`).
- `red_team/api/{service,routes}.py` + run DB model — `pack` → `packs`, scenario origin tag.
- `red_team/engine/run_engine.py` — merge multi-pack scenario set.
- `red_team/scoring/calculator.py` — per-pack + per-category breakdown (already category-aware).
- `red_team/export/renderer.py` — selected packs + per-pack/per-category in PDF.
- Frontend — multi-select picker + oracle-confidence badge.
- New `red_team/packs/data/*.yaml` — the imported packs.
- New generator scripts (per source) — harvest → normalize (JBB generator is the template).

---

## 10. Acceptance criteria

- [ ] Multi-select: pick ≥2 packs → one run → merged results, each result tagged
      with its origin pack.
- [ ] Category-first: picking a category runs matching scenarios across **all**
      selected packs; results are reported **per-category** (e.g. "Prompt
      Injection 92%"). Category taxonomy derived bottom-up from the shipped packs.
- [ ] Each external pack carries `source` + `license` + `oracle_confidence`,
      shown on the card and in the PDF.
- [ ] Scores are **reproducible given recorded responses**; each scenario stores
      request/response/model/timestamp for replay.
- [ ] Marker-oracle packs report HIGH confidence; refusal-oracle packs are visibly
      labeled heuristic — no silent blending.
- [ ] Dropping a normalized pack file registers it with **zero loader code change**
      (already true).
- [ ] The loop demo works end-to-end: scan a target → see gaps → enable protection
      → re-scan → score improves.

---

## 11. Out of scope (now)

- PyRIT orchestration, garak *dynamic* probes, AgentDojo *full* environment (wrap
  mode — different product surface, inherits LLM-judge).
- LLM-as-judge scoring of any kind.
- Spinning the Hub out as a separate product (revisit only if it lives its own life).
- Letting this derail the near-term brand/income work (profile, recommendations,
  outreach, first workshop) — Hub is a direction, sequence it.

---

## 12. Risks & honest limits

- **Confidence signal, not safety proof** — curated/frozen corpus, not protection
  against novel attacks (frame as such, like the existing benchmarks).
- **Refusal-oracle precision ceiling** — heuristic; label it.
- **Target non-determinism** — mitigated (temp 0, N samples, recorded response),
  not eliminated.
- **Coverage = imported packs** — broad but finite.
- **Licensing** — permissive (MIT/Apache: JBB, HarmBench, AdvBench, BIPIA, garak,
  promptfoo) safe to bundle **with attribution**; NC/gated (alpaca, wildjailbreak,
  qualifire) → local use or skip for redistribution.
- **Wrap mode inherits LLM-judge** → brand cost; that's why it's deferred.

---

## 13. Roadmap / sequencing

**Iteration 1 — MVP (ship now): 3 packs + the loop.**
- Packs: **Core Security (your ~50, HIGH anchor)** + **JailbreakBench** ✅ +
  **promptfoo (injection/obfuscation)**.
- Mechanics: **multi-pack run** (`pack` → `packs` + scenario origin tag) — the one
  real backend change — + **UI multi-select** + **oracle-confidence labels** +
  result framed as `score → critical → fixes → re-scan` (not a row dump).
- Minimal path: can ship JBB + Core Security first (2 packs), add the promptfoo
  adapter (~a day) right after.
- **Then derive the unified category taxonomy** from the 3 packs' *actual*
  categories (bottom-up, not invented up front) → map each pack's natives onto it
  → enable **category-first selection + per-category scores**.
- Then: get it in front of people + demo/post it (brand). Expand packs **by what
  users actually ask for**, not speculatively.

**Iteration 2:**
- **BIPIA (indirect injection — the deferred v1 gap)**, HarmBench, AdvBench,
  Do-Not-Answer, garak-static; obfuscation toggle; auditable replay record;
  **model rankings view** (brand content).

**Iteration 3 (later):**
- Wrap-mode for garak (full), agent track (AgentDojo / tool gates), aggregated
  trends across runs, spin-out consideration.

**Next concrete step:** second import pack — **BIPIA** (HIGH oracle, fills the
indirect-injection gap, Microsoft brand) or **AdvBench** (fast classic) — then
the multi-pack run + a real LLM target (reference-chat-target, not the proxy, so
the refusal oracle is meaningful).
