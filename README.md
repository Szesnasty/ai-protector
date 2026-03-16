# AI Protector

**Ship agents with guardrails — not prayers.**

Open-source, self-hosted security layer for tool-calling agents and LLM backends.
Deterministically block unsafe prompts, gate tool calls, and redact sensitive output — without LLM-as-judge or third-party SaaS.

- **Block prompt injection** before it reaches the model
- **Enforce tool access** by role, arguments, and session budget
- **Redact secrets and PII** before data leaves the system
- **Protect any provider** through a single OpenAI-compatible endpoint

[![CI](https://github.com/Szesnasty/ai-protector/actions/workflows/ci.yml/badge.svg)](https://github.com/Szesnasty/ai-protector/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-83%25-green)](https://github.com/Szesnasty/ai-protector/actions/workflows/ci.yml)
[![Internal Suite](https://img.shields.io/badge/🎯_internal_suite-97.9%25-brightgreen)](BENCHMARK.md)
[![JailbreakBench](https://img.shields.io/badge/🛡_JailbreakBench-94.8%25-brightgreen)](BENCHMARK_JAILBREAKBENCH.md)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Nuxt 4](https://img.shields.io/badge/Nuxt-4-00DC82?logo=nuxt.js&logoColor=white)](https://nuxt.com/)

<p align="center">
  <img src="docs/assets/agent-demo.png" alt="AI Protector — Agent Demo blocking a fake API call" />
</p>

---

## Quickstart

```bash
git clone https://github.com/Szesnasty/ai-protector.git
cd ai-protector
make demo
```

Open **http://localhost:3000**. Done.

> **Requirements:** Docker & Docker Compose. No GPU, no API keys, no Ollama.
>
> Demo mode runs the full security pipeline with real scanners — only model responses are simulated.
> Paste an API key in **Settings** to switch to a real provider instantly.

---

## The problem

LLM apps usually fail at the edges:

| Approach | Why it fails |
|---|---|
| System prompt instructions | Ignored, overridden, or leaked by the model |
| LLM-as-judge | Non-deterministic, adds latency, fooled by the same attacks |
| Provider moderation | Doesn't know your roles, tools, or business rules |
| App-layer `if/else` | Duplicated across services, impossible to audit |

AI Protector enforces policy **deterministically** — the protected LLM is the target, not the judge.

---

## How it works

Two cooperating enforcement layers — each catches what the other cannot.

### Proxy firewall

Sits between your app and the LLM provider. Every request passes through **5 independent detection layers** before reaching the model:

```
Request
  │
  ├─ Layer 1: Rules      denylist · length · encoded content
  ├─ Layer 2: Intent     pattern classification → jailbreak / tool_abuse / exfiltration / …
  │
  ├─ Layer 3: LLM Guard  ML classifiers — injection · toxicity · secrets  (local, free)
  ├─ Layer 4: Presidio   spaCy NER — PII detection  (email · phone · card · ID)
  ├─ Layer 5: NeMo       semantic embeddings — 12 rails, catches paraphrases + multilingual
  │           (layers 3–5 run in parallel)
  │
  └─ Decision  weighted risk score → BLOCK / MODIFY / ALLOW
                    │                        │
               return error            Transform → LLM Call → Output Filter → Logging
```

All scanners run **locally** — no external API calls, no per-request cost. → [Full pipeline diagram](docs/architecture/PROXY_FIREWALL_PIPELINE.md)

### Agent runtime

Runs inside the agent graph, enforcing security **around every tool call**:

```
User request
  ↓
Input limits & sanitization      (rate limit · token budget · cost cap)
  ↓
Intent classification + policy check
  ↓
Tool router                       (LLM decides which tools are needed)
  ↓
Pre-tool gate                     (RBAC · arg validation · injection · limits · confirmation)
  ↓
Tool execution
  ↓
Post-tool gate                    (PII · secrets · indirect injection · size truncation)
  ↓
LLM call
  ├─ Phase 1: Proxy firewall scan  ← runs full 5-layer pipeline as backstop
  └─ Phase 2: Provider call
  ↓
Response + Memory + Trace
```

Three lines of defense for every agent request:

- **Pre-tool gate** blocks unsafe or unauthorized tool calls before execution
- **Post-tool gate** sanitizes tool outputs before they reach the LLM
- **Proxy firewall** scans the final message set before provider invocation

→ [Full agent pipeline diagram](docs/architecture/AGENT_PIPELINE.md)

---

## Use it as an OpenAI-compatible proxy

*One URL change. Your existing app gets a security layer.*

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",  # ← only change
    api_key="your-key",                   # or "not-needed" in demo mode
)

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello!"}],
)
```

Supported providers: OpenAI, Anthropic, Google Gemini, Mistral, Azure, Ollama — routed by model name via [LiteLLM](https://docs.litellm.ai/docs/providers).

<p align="center">
  <img src="docs/assets/playground.gif" alt="AI Protector Playground" />
</p>

---

## See it in action

<details>
<summary><strong>Attack Scenarios</strong> — launch pre-built prompt injection, jailbreak, PII, and exfiltration tests</summary>

Fire 350+ pre-built attack scenarios against the proxy and see whether
they are blocked, modified, or allowed. Each scenario is mapped to an
OWASP LLM Top 10 category.

**What you can inspect:**
- Detected threat category and intent classification
- Risk score breakdown and policy decision (BLOCK / MODIFY / ALLOW)
- Scanner evidence and human-readable explanation

</details>

<details>
<summary><strong>Playground</strong> — chat through the firewall with real-time risk scoring</summary>

<img src="docs/assets/playground.png" alt="Playground" />

Send any prompt through the full 9-node security pipeline and see the
firewall's decision in real time. Switch between policies to compare
how thresholds affect the outcome.

**What you can inspect:**
- Live risk score and scanner breakdown per message
- Policy decision with full explanation
- Side-by-side policy comparison (Compare mode)

</details>

<details>
<summary><strong>Compare</strong> — protected vs direct model response, side by side</summary>

<img src="docs/assets/compare.png" alt="Compare" />

Send one prompt and see both paths: through the firewall (protected) and straight to the model (direct). Spot exactly what the security pipeline catches, modifies, or blocks compared to the raw model output.

</details>

<details>
<summary><strong>Agent Demo</strong> — test a tool-calling agent with RBAC, budgets, and confirmation flows</summary>

<img src="docs/assets/agent-demo.png" alt="Agent Demo" />

Interact with a Customer Support Copilot that uses 5 tools gated by
role-based access control. Switch roles (customer → support → admin)
to see how permissions change what the agent can do.

**What you can inspect:**
- RBAC enforcement: which tools each role can call
- Pre-tool gate: argument validation and permission checks
- Post-tool gate: PII/secrets scanning on tool outputs
- Budget limits: token and tool call caps per session

</details>

<details>
<summary><strong>Policies</strong> — configure firewall thresholds and scanner weights</summary>

<img src="docs/assets/Policies.png" alt="Policies" />

Four built-in policies (fast, balanced, strict, paranoid) with adjustable risk thresholds and scanner weights. Switch policies per request or set a global default.

</details>

<details>
<summary><strong>Analytics</strong> — view blocked vs allowed, risk distribution, and timeline</summary>

<img src="docs/assets/analytics.png" alt="Analytics" />

Dashboard with charts showing how the firewall is performing across all
requests. Filter by time window, policy, or threat category.

</details>

---

## What you get

- **Prompt injection blocked** before the model call — via intent classification, pattern rules, and embedding-based rails
- **Unauthorized tool calls denied** by role, arguments, and session budget — RBAC with 3 roles × 5 tools
- **PII and secrets redacted** before output leaves the system — Presidio, LLM Guard, custom rules
- **Policy decisions logged and traceable** per request — Langfuse tracing, analytics dashboard, risk scoring
- **350+ attack scenarios** — one-click, mapped to OWASP LLM Top 10
- **4 firewall policies** — fast, balanced, strict, paranoid — with adjustable thresholds

Scanners: [Presidio](https://github.com/microsoft/presidio) (PII) · [LLM Guard](https://github.com/protectai/llm-guard) (injection/toxicity) · [NeMo Guardrails](https://github.com/NVIDIA/NeMo-Guardrails) (dialog rails via embeddings)

Covers key application-layer risks: prompt injection, insecure output, sensitive data disclosure, insecure tool use, and excessive agency.
Full scope and exclusions: [THREAT_MODEL.md](docs/architecture/THREAT_MODEL.md).

---

## Documentation

| Doc | What |
|-----|------|
| [architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md) | System design, pipeline internals, two-phase LLM call flow |
| [architecture/PROXY_FIREWALL_PIPELINE.md](docs/architecture/PROXY_FIREWALL_PIPELINE.md) | Full 9-node proxy pipeline — node internals, risk score calculator, scanner models |
| [architecture/AGENT_PIPELINE.md](docs/architecture/AGENT_PIPELINE.md) | Full 11-node agent pipeline — pre/post-tool gates, three lines of defense |
| [architecture/THREAT_MODEL.md](docs/architecture/THREAT_MODEL.md) | Threat categories, scanner mapping, what's in/out of scope |
| [agents-v1.spec.md](docs/agents-v1.spec.md) | Next milestone: self-serve agent onboarding spec |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to contribute |

---

## Quality & trust

| | |
|-|-|
| **1 500+ automated tests** | Across proxy and agent runtime — decisions, tool gating, attack scenarios |
| **~83% line coverage** | Proxy-service (CI-enforced) |
| **350+ attack scenarios** | One-click, mapped to OWASP LLM Top 10 |
| **No telemetry** | Zero third-party analytics; requests go only to your LLM provider |
| **API keys stay in browser** | sessionStorage, never stored or logged server-side |
| **Security headers** | Strict CSP, X-Frame-Options DENY, nosniff, restrictive Permissions-Policy |

---

## Benchmarks

### Internal benchmark — broad threat coverage

358 attack scenarios across 38 categories (OWASP LLM Top 10), covering prompt injection,
agent abuse, PII, tool abuse, exfiltration, and more.

| Metric | Value |
|--------|-------|
| Attack detection rate | **97.9%** (0% false positives) |
| Pre-LLM pipeline overhead | **~50 ms** (balanced policy) |
| Memory (all scanners) | ~1.1 GB |

→ Full results: [BENCHMARK.md](BENCHMARK.md)

### External benchmark — JailbreakBench (NeurIPS 2024)

698 published jailbreak artifacts from [JailbreakBench](https://jailbreakbench.github.io/) —
real attack prompts that bypassed target models in the original research. Pre-LLM pipeline only.

| Metric | Value |
|--------|-------|
| Overall pre-LLM detection rate | **94.8%** |
| Human-crafted & random search attacks | **100%** |
| PAIR (iterative black-box) | 88.8% |
| GCG (gradient-based) | 90.0% |

Strongest performance appears on human-crafted and random-search jailbreaks, with lower but still high detection on PAIR and GCG-style attacks.

→ Full results: [BENCHMARK_JAILBREAKBENCH.md](BENCHMARK_JAILBREAKBENCH.md)

> Internal suite covers the broader agent/runtime threat model.
> JailbreakBench provides an external reference point for jailbreak-style prompt attacks.
> All results deterministic, reproducible with `make benchmark`.

**AI Protector blocks 94.8% of published JailbreakBench artifacts and 97.9% of attacks in an internal agent-security benchmark, with ~50 ms median pre-LLM overhead — without relying on LLM-as-judge.**

---

## Known limitations

- **Semantic attacks** — pattern-based scanners can miss novel injection techniques. Defense-in-depth mitigates but doesn't eliminate.
- **No formal tool verification** — tool behavior is gated by RBAC/validation, but runtime side effects are not verified.
- **Domain-specific tuning** — default thresholds cover general use; production needs calibration.
- **Single-node** — horizontal scaling and HA not yet implemented.

---

## Roadmap

**Next milestone: [Agents v1](docs/agents-v1.spec.md)** — self-serve agent registration, tool/role CRUD, generated integration kits, attack validation runner, rollout modes, per-agent traces.

<p align="center">
  <img src="docs/assets/agent-wizard.png" alt="Agent Onboarding Wizard Screenshot" />
</p>

Branch: [`feat/agent-onboarding-wizard`](https://github.com/Szesnasty/ai-protector/tree/feat/agent-onboarding-wizard)

Full plan: [ROADMAP.spec.md](docs/ROADMAP.spec.md).

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Security

Found a vulnerability? See [SECURITY.md](SECURITY.md).

## License

[Apache-2.0](LICENSE)

---

Built with [LangGraph](https://github.com/langchain-ai/langgraph) · [LiteLLM](https://github.com/BerriAI/litellm) · [Presidio](https://github.com/microsoft/presidio) · [LLM Guard](https://github.com/protectai/llm-guard) · [NeMo Guardrails](https://github.com/NVIDIA/NeMo-Guardrails) · [Nuxt](https://nuxt.com/) · [Vuetify](https://vuetifyjs.com/)
