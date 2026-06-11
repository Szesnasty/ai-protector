# Security Pipeline — 7 detection layers in 9 nodes

The proxy firewall is implemented as a **9-node LangGraph graph**. Every request passes through all nodes sequentially. Detection happens across 7 independent layers — rules, intent classification, and five parallel ML/embedding scanners — then aggregated into a single risk score.

> **Deobfuscation (A2):** the intent node first builds a `scan_text` — the raw
> message **plus** decoded variants of common obfuscations (leetspeak, spaced
> characters, homoglyphs, ROT13, base64). The injection-oriented detectors
> (intent classifier, denylist, LLM Guard, jailbreak ML) read `scan_text`, so an
> obfuscated attack is decoded back into something they recognize. PII (Presidio)
> still reads the raw text, and the **original message is what the LLM receives**.

```
Request
  │
  ▼
┌───────────────────────────────────────────────────────────────────┐
│  NODE 1 │ parse                                                   │
│  Extracts user_message, messages[], model name, client identity   │
└──────────────────────────────┬────────────────────────────────────┘
                               │
                               ▼
┌───────────────────────────────────────────────────────────────────┐
│  NODE 2 │ rules                          LAYER 1: Rule engine     │
│                                                                   │
│  • Denylist — blocked phrases (action: block / flag / score_boost)│
│  • Prompt length — oversized prompts flagged                      │
│  • Encoded content — Base64, hex, unicode escapes in prompt       │
│  • Excessive special characters                                   │
│                                                                   │
│  Hard block on denylist hit — skips remaining nodes               │
└──────────────────────────────┬────────────────────────────────────┘
                               │
                               ▼
┌───────────────────────────────────────────────────────────────────┐
│  NODE 3 │ intent                         LAYER 2: Classification  │
│                                                                   │
│  A2: builds scan_text (raw + deobfuscated variants) first         │
│  ~80 regex / substring patterns → classifies what the user wants: │
│  jailbreak · tool_abuse · role_bypass · agent_exfiltration ·      │
│  social_engineering · harmful_content · system_prompt_extract ·   │
│  rag_poisoning · confused_deputy · template_injection · crescendo  │
│                                                                   │
│  Output: intent label + confidence score (0.0–1.0) + scan_text    │
└──────────────────────────────┬────────────────────────────────────┘
                               │
                               ▼
┌───────────────────────────────────────────────────────────────────┐
│  NODE 4 │ scanners                                                │
│  Dispatcher — fires 5 scanners IN PARALLEL (asyncio.gather)       │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │  LAYER 3 │ LLM Guard  (ProtectAI, open-source, local)       │  │
│  │                                                             │  │
│  │  Fine-tuned ML classifiers running fully on-premise:       │  │
│  │  • PromptInjection — DeBERTa model, detects prompt takeover │  │
│  │  • Toxicity        — DistilBERT, hate speech / violence     │  │
│  │  • Secrets         — regex, API keys / tokens / conn strs  │  │
│  │  • BanSubstrings   — SYSTEM: / <|im_start|>system markers  │  │
│  │  • InvisibleText   — zero-width Unicode steganography       │  │
│  │                                                             │  │
│  │  Zero API calls. Models cached locally (~500 MB).           │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │  LAYER 4 │ Presidio  (Microsoft, open-source, local)        │  │
│  │                                                             │  │
│  │  spaCy NER — detects personally identifiable information:   │  │
│  │  • Names, addresses, emails, phone numbers                  │  │
│  │  • Credit cards, IBANs, national IDs, passports             │  │
│  │  • Medical record numbers, tax IDs                          │  │
│  │                                                             │  │
│  │  Three modes: flag (mark) · mask (replace) · block (deny)  │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │  LAYER 5 │ NeMo Guardrails  (NVIDIA, open-source, local)    │  │
│  │                                                             │  │
│  │  Semantic embeddings — FastEmbed (all-MiniLM-L6-v2, 90 MB):│  │
│  │  • Embeds message → 384-dimensional vector                  │  │
│  │  • Cosine similarity vs example phrases in Colang .co files │  │
│  │  • 13 rails: tool_abuse · role_bypass · exfiltration ·      │  │
│  │    social_engineering · cot_manipulation · rag_poisoning ·  │  │
│  │    confused_deputy · cross_tool · supply_chain · …          │  │
│  │                                                             │  │
│  │  Catches paraphrases and multi-language variants.           │  │
│  │  "Run rm -rf on the filesystem" → also catches:             │  │
│  │    "Wipe the entire disk" / "Delete all files recursively"  │  │
│  │    "執行 rm -rf 命令" (Chinese) / "Usuń wszystkie pliki" (PL) │  │
│  │                                                             │  │
│  │  Zero LLM calls. ~10 ms per scan after warm-up.             │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │  LAYER 6 │ Jailbreak ML  (A1, open-source, local)           │  │
│  │                                                             │  │
│  │  DistilBERT classifier (madhurjindal/Jailbreak-Detector):  │  │
│  │  • Labels prompt jailbreak / benign + confidence            │  │
│  │  • Catches roleplay / PAIR-style jailbreaks that carry no  │  │
│  │    attack keywords (semantic, not pattern-based)            │  │
│  │  • High precision — ~0 false positives on benign/dual-use  │  │
│  │                                                             │  │
│  │  Zero API calls. Model cached locally (~270 MB).            │  │
│  │  JailbreakBench PAIR detection 53.6% → 97.9% with this on.  │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │  LAYER 7 │ Harm ML guard  (IBM granite-guardian, ungated)   │  │
│  │                                                             │  │
│  │  2 B guard model (granite-guardian-3.0-2b) → P(harm):      │  │
│  │  • Catches direct harmful *requests* (weapons/drugs/hate/  │  │
│  │    CSAM/violence) phrased as ordinary questions            │  │
│  │  • Flags at P(harm) ≥ 0.8 (tuned for ~0 FP on benign)      │  │
│  │  • Heavyweight: ~0.5–1.5 s/req — disable via enable_harm_ml │  │
│  │                                                             │  │
│  │  Zero API calls. Apache-2.0, no HF token. ~4 GB.           │  │
│  │  promptfoo red-team 66% → 91%; genuine-harm 57% → 92%.     │  │
│  └─────────────────────────────────────────────────────────────┘  │
└──────────────────────────────┬────────────────────────────────────┘
                               │
                               ▼
┌───────────────────────────────────────────────────────────────────┐
│  NODE 5 │ decision                                                │
│                                                                   │
│  Aggregates signals from ALL 5 layers → weighted risk score:      │
│                                                                   │
│  intent score   × intent weight   (e.g. tool_abuse → +0.40)      │
│  denylist hit                     (→ +0.80, hard block if set)    │
│  LLM Guard flags × scanner weights (injection × 0.8, tox × 0.5) │
│  Jailbreak ML   × jailbreak_ml weight (→ × 0.80)                 │
│  NeMo score     × nemo weight     (→ × 0.70)                     │
│  Presidio PII count × per-entity weight                           │
│  score_boost    from custom rules                                 │
│                                                                   │
│  Risk ≥ threshold (default 0.7) → BLOCK                          │
│  Risk < threshold → ALLOW or MODIFY (PII mask)                   │
└──────────────┬───────────────────────────┬────────────────────────┘
               │ BLOCK                     │ ALLOW / MODIFY
               ▼                           ▼
        return error             ┌─────────────────────┐
        LLM never called         │  NODE 6 │ transform  │
                                 │  Masks PII in prompt │
                                 │  if policy = mask    │
                                 └──────────┬──────────┘
                                            │
                                            ▼
                                 ┌──────────────────────┐
                                 │  NODE 7 │ llm_call    │
                                 │  Phase 1: scan msgs   │
                                 │    → proxy firewall   │
                                 │  Phase 2: full msgs   │
                                 │    → LLM provider     │
                                 └──────────┬───────────┘
                                            │
                                            ▼
                                 ┌──────────────────────────┐
                                 │  NODE 8 │ output_filter  │
                                 │  Scans LLM response:     │
                                 │  • PII redaction         │
                                 │  • Secrets regex         │
                                 │  • System prompt leak    │
                                 └──────────┬───────────────┘
                                            │
                                            ▼
                                 ┌──────────────────────┐
                                 │  NODE 9 │ logging     │
                                 │  Trace, metrics,      │
                                 │  Langfuse export      │
                                 └──────────┬───────────┘
                                            │
                                            ▼
                                       Response
```

---

## Node summary

| # | Node | Detection layer | Method |
|---|------|-----------------|--------|
| 1 | parse | — | Extract request fields |
| 2 | rules | **Layer 1** — Rule engine | Denylist, length, encoding, special chars |
| 3 | intent | **Layer 2** — Classification | A2 deobfuscation → `scan_text`; ~80 regex patterns → intent label + confidence |
| 4 | scanners | **Layer 3** — LLM Guard | ML: DeBERTa injection, DistilBERT toxicity, secrets regex |
| 4 | scanners | **Layer 4** — Presidio | spaCy NER: PII detection (10 entity types) |
| 4 | scanners | **Layer 5** — NeMo Guardrails | FastEmbed cosine similarity: 12 semantic rails |
| 4 | scanners | **Layer 6** — Jailbreak ML | DistilBERT classifier: semantic roleplay/PAIR jailbreaks |
| 4 | scanners | **Layer 7** — Harm ML *(strict/paranoid)* | granite-guardian-2b guard model: harmful requests (weapons/drugs/hate/…); heavy, off the fast path |
| 5 | decision | — | Weighted signal aggregation → ALLOW / MODIFY / BLOCK |
| 6 | transform | — | PII masking in prompt (if policy = mask) |
| 7 | llm_call | — | LLM provider call (or scan-only via `/v1/scan`) |
| 8 | output_filter | — | PII redaction, secrets scan, system prompt leak detection |
| 9 | logging | — | Trace accumulator, metrics, Langfuse export |

> Node 4 (`scanners`) is a single dispatcher node that fires layers 3–7 in parallel.
> Layers 1–2 (rules + intent) are separate nodes that also contribute risk signals to the decision.

---

## Risk score calculation (decision node)

```python
score = 0.0

# Intent weight (per intent type)
if intent == "tool_abuse":        score += 0.40
elif intent == "jailbreak":       score += 0.60
elif intent == "role_bypass":     score += 0.50
# ... 15 more intent types

# Rule-based signals
if denylist_hit:                  score += 0.80   # → immediate BLOCK
if encoded_content:               score += 0.30
if length_exceeded:               score += 0.10

# LLM Guard signals
score += llm_guard_injection  * 0.80  # injection score × weight
score += llm_guard_toxicity   * 0.50
score += secrets_weight              # 0.60 flat if secrets found

# Jailbreak ML classifier (A1)
score += jailbreak_ml_score * 0.80   # confidence × weight (semantic jailbreaks)

# Harm ML guard model (A1-harm)
score += harm_ml_score * 0.90        # P(harm) × weight (harmful requests, when ≥ 0.8)

# NeMo Guardrails
score += nemo_score * 0.70           # highest matched rail × weight

# Presidio PII
score += min(pii_count * 0.10, 0.50)

# Custom rule boost
score += score_boost                 # accumulated from denylist rules

score = min(score, 1.0)             # cap at 1.0
```

---

## Defense in depth — why multiple layers

Each layer catches a different class of attack:

| Layer | Catches | Misses |
|-------|---------|--------|
| Rules (denylist) | Exact known phrases, fast | Unknown phrasing, paraphrases |
| Intent (regex + A2 deobfuscation) | Pattern families (~80 types), obfuscated variants | Novel attacks not in patterns |
| LLM Guard (ML) | Semantic injection, toxicity | Domain-specific attacks |
| Presidio (NER) | PII entities with context | Custom entity formats |
| NeMo (embeddings) | Paraphrases, multilingual | Multi-turn slow-burn attacks |
| Jailbreak ML (DistilBERT) | Roleplay / PAIR jailbreaks (semantic) | Adversarial-suffix-only (GCG tail) |
| Harm ML (granite-guardian) | Direct harmful requests (weapons/drugs/hate/…) | Heavy (~1 s); thresholded to protect FPR |

No single layer is complete. Together they cover the space.

---

## All scanners run locally — no external API calls

| Scanner | Model | Size | Source |
|---------|-------|------|--------|
| LLM Guard PromptInjection | `ProtectAI/deberta-v3-base-prompt-injection-v2` | ~250 MB | HuggingFace, Apache 2.0 |
| LLM Guard Toxicity | `martin-ha/toxic-comment-model` (DistilBERT) | ~250 MB | HuggingFace, Apache 2.0 |
| Presidio NER | spaCy `en_core_web_lg` + custom recognizers | ~750 MB | MIT |
| NeMo Guardrails | FastEmbed `all-MiniLM-L6-v2` (ONNX) | ~90 MB | Apache 2.0 |
| Jailbreak ML | `madhurjindal/Jailbreak-Detector` (DistilBERT) | ~270 MB | HuggingFace |
| Harm ML | `ibm-granite/granite-guardian-3.0-2b` (guard model) | ~4 GB | HuggingFace, Apache 2.0 |

Total: ~5.6 GB on first `docker compose up` (models pre-baked into the image). Cached locally, zero API cost per request.

---

## Related

- [Agent pipeline (11-node)](AGENT_PIPELINE.md) — pre/post-tool gates inside the agent graph
- [NeMo rails source](../../apps/proxy-service/src/pipeline/rails/) — Colang `.co` files
- [Decision node source](../../apps/proxy-service/src/pipeline/nodes/decision.py)
