# Security Pipeline — 5 detection layers in 9 nodes

The proxy firewall is implemented as a **9-node LangGraph graph**. Every request passes through all nodes sequentially. Detection happens across 5 independent layers — rules, intent classification, three parallel ML/embedding scanners, then aggregated into a single risk score.

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
│  ~80 regex / substring patterns → classifies what the user wants: │
│  jailbreak · tool_abuse · role_bypass · agent_exfiltration ·      │
│  social_engineering · harmful_content · system_prompt_extract ·   │
│  rag_poisoning · confused_deputy · template_injection · crescendo  │
│                                                                   │
│  Output: intent label + confidence score (0.0–1.0)                │
└──────────────────────────────┬────────────────────────────────────┘
                               │
                               ▼
┌───────────────────────────────────────────────────────────────────┐
│  NODE 4 │ scanners                                                │
│  Dispatcher — fires 3 scanners IN PARALLEL (asyncio.gather)       │
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
| 3 | intent | **Layer 2** — Classification | ~80 regex patterns → intent label + confidence |
| 4 | scanners | **Layer 3** — LLM Guard | ML: DeBERTa injection, DistilBERT toxicity, secrets regex |
| 4 | scanners | **Layer 4** — Presidio | spaCy NER: PII detection (10 entity types) |
| 4 | scanners | **Layer 5** — NeMo Guardrails | FastEmbed cosine similarity: 12 semantic rails |
| 5 | decision | — | Weighted signal aggregation → ALLOW / MODIFY / BLOCK |
| 6 | transform | — | PII masking in prompt (if policy = mask) |
| 7 | llm_call | — | LLM provider call (or scan-only via `/v1/scan`) |
| 8 | output_filter | — | PII redaction, secrets scan, system prompt leak detection |
| 9 | logging | — | Trace accumulator, metrics, Langfuse export |

> Node 4 (`scanners`) is a single dispatcher node that fires layers 3–5 in parallel.
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
| Intent (regex) | Pattern families (~80 types) | Novel attacks not in patterns |
| LLM Guard (ML) | Semantic injection, toxicity | Domain-specific attacks |
| Presidio (NER) | PII entities with context | Custom entity formats |
| NeMo (embeddings) | Paraphrases, multilingual | Multi-turn slow-burn attacks |

No single layer is complete. Together they cover the space.

---

## All scanners run locally — no external API calls

| Scanner | Model | Size | Source |
|---------|-------|------|--------|
| LLM Guard PromptInjection | `ProtectAI/deberta-v3-base-prompt-injection-v2` | ~250 MB | HuggingFace, Apache 2.0 |
| LLM Guard Toxicity | `martin-ha/toxic-comment-model` (DistilBERT) | ~250 MB | HuggingFace, Apache 2.0 |
| Presidio NER | spaCy `en_core_web_lg` + custom recognizers | ~750 MB | MIT |
| NeMo Guardrails | FastEmbed `all-MiniLM-L6-v2` (ONNX) | ~90 MB | Apache 2.0 |

Total: ~1.3 GB on first `docker compose up`. Cached locally, zero API cost per request.

---

## Related

- [Agent pipeline (11-node)](AGENT_PIPELINE.md) — pre/post-tool gates inside the agent graph
- [Attack scenario example](../../demo-files/nodes.md) — step-by-step trace for `rm -rf` prompt
- [NeMo rails source](../../apps/proxy-service/src/pipeline/rails/) — Colang `.co` files
- [Decision node source](../../apps/proxy-service/src/pipeline/nodes/decision.py)
