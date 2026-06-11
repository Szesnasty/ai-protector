# Agent Boundary Benchmark — Plan

> **Status:** Planned — detailed (scoping docs, not implementation guides)
> Coarse-grained "big blocks". Each file is one deliverable.

## The thesis

We have **two product pillars** and should benchmark them separately:

1. **Proxy Firewall Benchmark** *(exists — [docs/BENCHMARKS.md](../../BENCHMARKS.md))* — "can we
   detect bad prompts / jailbreaks / harm?" → 99% JailbreakBench, 91% promptfoo (harm-on).
2. **Agent Boundary Benchmark** *(this plan)* — **"even if the model is manipulated, does the
   system still block the unauthorized *action* and treat tool output as untrusted?"**

The second question is more defensible and more marketable: it measures **outcome control**, not
classifier accuracy. The current proxy benchmark already states — honestly — that the agent
**pre-tool** and **post-tool** gates are *out of scope* and "benchmarked separately." This plan is
that separate benchmark.

> Headline we are aiming for: **`0% unsafe tool execution across the agent benchmark`** — stronger
> than "99% jailbreaks blocked" because it shows we control the *effect*, not just the input.

## Core principle (read this first)

**Do not** benchmark `user prompt → LLM → maybe a tool → check`. The LLM is non-deterministic and is
not our security layer. Benchmark this instead:

```
deterministic replay of (proposed tool call + tool output)  →  agent gates  →  allow / block / redact / require_confirmation
```

This tests **our** security boundary, reproducibly and fast — exactly like `bench_external` replays a
frozen attack corpus through the pre-LLM pipeline. A real-LLM end-to-end benchmark can come **later**
as a separate, non-gating tier (see [C](C-e2e-agent-traces.spec.md)).

## Why this is cheap to build (current state)

The gates are **already decomposed into pure, deterministic functions** — no LLM, no DB needed to
exercise them. The harness wraps them; it is not a refactor.

| Surface | Pure function (exists) | File |
|---|---|---|
| RBAC / scope | `rbac.check_permission(role, tool, scope) → allowed, requires_confirmation` | `apps/agent-demo/src/agent/rbac/service.py` |
| RBAC allowlist | `_check_rbac(tool, allowed, role) → CheckResult` | `apps/agent-demo/src/agent/nodes/pre_tool_gate.py` |
| Arg validation | JSON-schema validation → `VALID / SANITIZED / INVALID` | `pre_tool_gate.py` |
| Context-risk / budget | escalation + budget checks | `pre_tool_gate.py` |
| PII / secrets | `scan_pii(text)`, `scan_secrets(text) → (redacted, count)` | `apps/agent-demo/src/agent/nodes/post_tool_gate.py` |
| Indirect injection | `scan_injection(text) → (score, signals)` | `post_tool_gate.py` |

- **Config exists:** [`rbac_config.yaml`](../../../apps/agent-demo/src/agent/rbac/rbac_config.yaml) —
  roles `customer / support / admin`, per-tool `scopes: [read|write]`, `requires_confirmation: true`
  (e.g. `getInternalSecrets`, `issueRefund`).
- **Seed corpus exists:** ~131 deterministic tests already exercise the gates —
  `test_rbac.py` (27), `test_pre_tool_gate.py` (37), `test_post_tool_gate.py` (52). Extract their
  inputs + expected decisions into the frozen JSONL corpora.
- **Missing:** no `apps/agent-demo/benchmarks/` dir, no agent attack corpus, no `AGENT_BENCHMARKS.md`.

## Index

| # | Spec | Effort | What it buys |
|---|------|--------|--------------|
| **A** | [Pre-tool gate benchmark](A-pre-tool-gate.spec.md) | **S–M — start here** | "100% unauthorized tool calls blocked", scope/confirmation accuracy, fast win (wraps pure fns) |
| **B** | [Post-tool gate benchmark](B-post-tool-gate.spec.md) | M | secret/PII redaction recall, indirect-injection block rate (the hard, honest part) |
| **C** | [E2E agent attack traces](C-e2e-agent-traces.spec.md) | M | the **`0% unsafe action`** headline on full frozen traces |
| **D** | [CI, reporting & `AGENT_BENCHMARKS.md`](D-ci-reporting-and-doc.spec.md) | S–M | freeze + manifest, regression gate, badges, the doc, honest weak-spots |

Phasing: **A + B first** (both wrap pure functions, seeded from existing tests), then **C**, with
**D** wiring CI/badges/doc throughout.

## Honest-claiming principles (do not skip — this is the credibility moat)

The whole value is being *believed*. Apply the same discipline as the proxy benchmark:

1. **Frame absolutes as corpus-relative.** Not "0% unsafe" but **"0% unsafe action success on N
   frozen traces"**. Not "100% blocked" but "100% of M RBAC cases".
2. **Deterministic 100% is discounted by reviewers** ("you tested that an `if` works"). The value is
   in **adversarial** cases — tool-name spoofing (unicode / case / trailing space), argument
   injection, magnitude abuse. Weight the corpus there.
3. **Some "block" outcomes are aspirational, not implemented.** Magnitude/business-logic checks
   (`amount: 5000`, `limit: 100000`) may have **no gate logic yet**. The first run will show them as
   **gaps** — that is a roadmap, not a headline. Mark them explicitly.
4. **Measure indirect injection before quoting a number.** `scan_injection` is regex-based; on a
   diverse corpus expect **~70–90%**, not 95–99%. Publish the measured value and the misses.
5. **Always publish a "weak spots" section** (like proxy `BENCHMARKS.md`) and a benign / over-redaction
   FPR. An all-100% table is *less* credible, not more.
6. **Name a recognized source.** Seed indirect-injection from **AgentDojo** / **InjecAgent**, map
   coverage to **OWASP LLM06 (excessive agency) / LLM07 (insecure plugin) / LLM08**. Recognized
   provenance did for promptfoo/JailbreakBench what hand-written cases cannot.

## Proposed file layout

```
apps/agent-demo/benchmarks/
  corpora/
    pre_tool_rbac.jsonl
    pre_tool_args.jsonl
    pre_tool_business_logic.jsonl
    post_tool_pii_secrets.jsonl
    post_tool_indirect_injection.jsonl
    e2e_agent_traces.jsonl
    benign_tool_calls.jsonl
    benign_tool_outputs.jsonl
  manifest.json            # sha256 per corpus — harvest-and-freeze
  bench_pre_tool.py
  bench_post_tool.py
  bench_agent_e2e.py
  bench_agent_latency.py
  baseline.json
  badge.py
  results/                 # gitignored; uploaded as CI artifact
docs/AGENT_BENCHMARKS.md   # the canonical agent doc (separate from BENCHMARKS.md)
```

## Open decisions (pick before Phase A)

- [ ] **Magnitude/business-logic gates:** implement now (so they can pass) or benchmark-as-gap first?
- [ ] **Decision vocabulary:** lock the enum — `allow / block / redact / allow_redacted / require_confirmation / sanitize`.
- [ ] **One agent badge or three?** (`agent boundary` vs `pre-tool` + `post-tool` + `e2e`).
- [ ] **External corpus:** AgentDojo, InjecAgent, or both — and which slice to freeze.
