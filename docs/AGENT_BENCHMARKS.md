# AI Protector — Agent Boundary Benchmark

> Deterministic replay of proposed tool calls + tool outputs through the agent
> **pre-tool** and **post-tool** gates. **No LLM, no LLM-as-judge, no DB, no Redis** —
> the gates are pure functions. This is the second pillar next to the
> [Proxy Firewall Benchmark](BENCHMARKS.md).

The question this answers is not "can we detect a bad prompt?" but **"even if the
model is manipulated, does the system still block the unauthorized *action* and
treat tool output as untrusted?"**

## ⭐ At a glance

Apple M4 Pro · frozen JSONL corpora (102 cases) · pure-function replay.

| Boundary | Corpus | Headline metric | Result | Benign allowed | p50 |
|---|---:|---|---:|---:|---:|
| **Pre-tool gate** | 60 | unsafe calls contained | **93.8%** | **100%** | **0.009 ms** |
| **Post-tool gate** | 28 | secret/PII redaction recall | **100%** | **100%** | **0.02 ms** |
| **Post-tool gate** | (12) | indirect-injection blocked | **50%** ¹ | — | — |
| **E2E agent traces** | 8 | **unsafe action success** | **0.0%** ² | 100% completion | — |

¹ Honest gap — see [Weak spots](#weak-spots). ² **The headline: `0% unsafe
action success` across the attack traces** — no `must_not_execute` tool ever ran.

> **`0% unsafe tool execution`** is a stronger claim than a detection percentage:
> it measures *outcome* control. It is true **on this frozen corpus** — the number
> is only as strong as the corpus, which is versioned and growing.

---

## 1. Pre-tool gate

Replays `(role, proposed_tool, arguments)` through the real gate
(`_evaluate_tool`): RBAC → scope → argument validation → context-risk → limits →
confirmation. Decisions normalized to `allow / block / require_confirmation`.

| Category | Cases | Contained | Rate |
|---|---:|---:|---:|
| RBAC deny (role lacks tool) | 5 | 5 | **100%** |
| Unknown / non-existent tool | 9 | 9 | **100%** |
| Tool-name spoofing (space/unicode/case) | 10 | 10 | **100%** |
| Business-logic / magnitude | 6 | 6 | **100%** ³ |
| Context-risk escalation | 1 | 1 | **100%** |
| Confirmation required (containment) | 2 | 2 | **100%** |
| Argument injection | 6 | 5 | 83.3% |
| Argument schema validation | 9 | 7 | 77.8% |
| **Unsafe contained (overall)** | **48** | **45** | **93.8%** |
| Benign tool calls allowed | 12 | 12 | **100%** |
| Confirmation **accuracy** (exact) | 2 | 1 | 50% |

³ Magnitude abuse is currently contained **incidentally** (extra fields rejected
by `extra: forbid`, write scope denied), not by a dedicated magnitude rule — see
weak spots.

## 2. Post-tool gate

Replays frozen tool outputs through `evaluate_tool_output` (injection scan → PII
→ secrets → size). Redaction recall is verified by `must_not_contain` on the
**sanitized** text, not by trusting the decision label.

| Category | Cases | OK | Rate |
|---|---:|---:|---:|
| Secret redaction (API keys, tokens, conn strings, JWT, private keys) | 6 | 6 | **100%** |
| PII redaction (email, phone, SSN, card, IP, IBAN) | 6 | 6 | **100%** |
| Indirect prompt injection blocked | 12 | 6 | **50%** ¹ |
| Benign output allowed (no over-redaction) | 10 | 10 | **100%** |
| Over-redaction rate | — | — | **0%** |

## 3. End-to-end agent traces

Each trace replays `user_prompt → proposed tool calls → pre-tool gate → (tool
output) → post-tool gate`. The safety property is checked by `must_not_execute`,
not a label.

| Metric | Result |
|---|---:|
| **Unsafe action success rate** | **0.0%** (0/5) |
| Safe task completion rate | **100%** (3/3) |
| Policy explainability (every block carries a reason) | **100%** |
| Audit coverage (trace records prompt/tool/decision/reason) | **100%** |

Scenarios: read-only order status (allow), privilege escalation (block),
argument injection (block), sensitive write/refund (confirmation-or-block),
mass exfiltration (block), malicious RAG output (block output), secret in tool
output (redact), unknown/untrusted tool (block).

---

## Weak spots

Where the agent boundary misses today — published so you can see we know where it
does not yet deliver (same discipline as the proxy benchmark):

- **Indirect prompt injection — 50%.** The post-tool injection scanner is
  pattern-based with a block threshold of 0.4; a **single** pattern scores
  0.2–0.3, so a lone "ignore previous instructions" or a single special token in
  tool output is **not blocked**. Multi-pattern payloads are. → roadmap:
  [B1 — indirect-injection detection](plan/B1-indirect-injection-detection.spec.md)
  (lower threshold / ML detector). This is the hard, honest part of agent security.
- **Argument-injection pattern gap.** The argument-validation injection scanner
  is narrower than the message-level one and misses some phrasings (e.g. "new
  system prompt: …") → 1/6 missed.
- **Over-length args are truncated, not rejected.** A malformed `order_id`
  longer than the schema is silently truncated to a *valid different* ID and
  allowed (sanitize → MODIFY). Safe for queries, but a silent-mutation risk for
  identifiers.
- **Confirmation accuracy 50%.** `issueRefund` (write scope) is **blocked** by
  the read-scoped RBAC check before reaching the confirmation step, instead of
  raising `require_confirmation`. Strictly safer, but it breaks the
  admin-refund-with-approval flow.

## What this benchmark does NOT prove

- It does **not** use a real LLM — the model's proposed tool calls and the tool
  outputs are part of the frozen trace. A real-LLM end-to-end tier is planned as
  separate, non-gating.
- No live MCP/tool-registry fuzzing, no multi-agent, no long-context RAG.
- Frozen-corpus only (102 cases) — a reproducible confidence signal, not a safety
  certificate. `0% unsafe` means "on these traces".

## Methodology

- **Deterministic:** gates are pure functions; replay is reproducible. No LLM, DB,
  or Redis (`session_id=""` uses the in-memory limits path).
- **Frozen corpus:** committed JSONL with a sha256 `manifest.json`; a
  `verify_manifest` step fails CI if a corpus changed without a manifest update.
- **Intent-based expectations:** corpus `expected_decision` encodes the *safe*
  outcome, not the gate's current behaviour — so gaps surface instead of hiding.

## Reproduce

```bash
cd apps/agent-demo
make -C ../.. benchmark-agent            # all three, report
python -m benchmarks.bench_pre_tool      # pre-tool gate
python -m benchmarks.bench_post_tool     # post-tool gate
python -m benchmarks.bench_agent_e2e     # e2e traces
python -m benchmarks.gen_corpora         # regenerate the frozen corpora + manifest
```

Plan & design: [docs/plan/agent-benchmarks/](plan/agent-benchmarks/README.md).
