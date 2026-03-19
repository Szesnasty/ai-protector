# AI Protector

**Runtime security for tool-calling agents — zero config, no SaaS, no LLM-as-judge.**

AI Protector wraps your agent in a deterministic security layer: register your tools and roles in a 7-step wizard, get generated RBAC policy and integration code, then ship with every tool call gated at runtime. An OpenAI-compatible proxy firewall provides a second line of defense across all LLM traffic.

[![CI](https://github.com/Szesnasty/ai-protector/actions/workflows/ci.yml/badge.svg)](https://github.com/Szesnasty/ai-protector/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-83%25-green)](https://github.com/Szesnasty/ai-protector/actions/workflows/ci.yml)
[![Internal Suite](https://img.shields.io/badge/🎯_internal_suite-97.9%25-brightgreen)](BENCHMARK.md)
[![JailbreakBench](https://img.shields.io/badge/🛡_JailbreakBench-94.8%25-brightgreen)](BENCHMARK_JAILBREAKBENCH.md)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Nuxt 4](https://img.shields.io/badge/Nuxt-4-00DC82?logo=nuxt.js&logoColor=white)](https://nuxt.com/)

<p align="center">
  <img src="docs/assets/agent-wizard.png" alt="AI Protector — Agent Onboarding Wizard" />
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
> Demo ships with two pre-configured agents so you can explore the full security pipeline immediately.
> Paste an API key in **Settings** to switch to a real LLM provider.

---

## The problem with agent security today

| Approach | Why it fails |
|---|---|
| System prompt instructions | Overridden or ignored by the model under adversarial input |
| LLM-as-judge | Non-deterministic, adds latency, fooled by the same attacks |
| Provider content filters | Unaware of your roles, tools, or business rules |
| Hand-rolled app-layer checks | Scattered, untested, impossible to audit at scale |

Agents make real API calls — `deleteUser`, `transferFunds`, `updateOrder`. A single bypassed check is a real incident. AI Protector enforces policy **deterministically** before and after every tool call — the model is the thing being protected, not the thing doing the protecting.

---

## Agent Wizard — from zero to secured agent in minutes

The wizard walks you through registering an agent in 7 steps and generates everything you need to enforce security at runtime.

<p align="center">
  <img src="docs/assets/agent-wizard.png" alt="Agent Wizard" />
</p>

### What the wizard produces

**Step 1 — Describe** your agent: name, framework (LangGraph / pure Python / custom), and the policy pack that matches your use case (e-commerce, internal copilot, customer support, …).

**Step 2 — Register tools** — declare every callable tool, its sensitivity level (low / medium / high), and whether it reads or writes. Presets for common tool sets are included.

**Step 3 — Define roles** — build your RBAC hierarchy. Roles inherit from each other. Each role gets exactly the tools it needs, nothing more.

**Step 4 — Security policy** — choose a base policy pack (balanced / strict / paranoid) and see which scanners activate and at what thresholds.

**Step 5 — Review** — inspect the full generated RBAC policy before it's saved.

**Step 6 — Integration kit** — generated `rbac.yaml`, `config.yaml`, and a framework-specific code snippet to drop into your agent.

**Step 7 — Validate** — run the built-in attack suite against your agent's config and see the results before going live.

### What gets enforced at runtime

Once integrated, every tool call your agent makes passes through two deterministic gates:

```
Agent decides to call a tool
          ↓
  ┌───────────────────┐
  │   Pre-tool gate   │  RBAC check · argument validation · injection scan
  │                   │  session budget · confirmation for high-risk tools
  └───────────────────┘
          ↓ allowed
    Tool executes
          ↓
  ┌───────────────────┐
  │  Post-tool gate   │  PII redaction · secrets scan · indirect injection
  │                   │  output size limits
  └───────────────────┘
          ↓ sanitized
  LLM receives clean output
```

**Pre-tool gate** — the agent cannot call a tool the current role doesn't have. Write operations with high sensitivity require explicit user confirmation before execution. Argument injection is scanned before parameters reach the tool.

**Post-tool gate** — tool output is scrubbed for PII (Presidio), secrets (LLM Guard), and indirect prompt injection before it's fed back to the model. If the output would carry an exfiltration payload hidden in a JSON field, it gets caught here.

**Proxy firewall backstop** — on the final assembled message set, the full 5-layer proxy pipeline runs as a last line of defense before the provider call is made.

---

## Full agent pipeline

```
User request
  ↓
Input limits & sanitization      (rate limit · token budget · cost cap)
  ↓
Intent classification + policy check
  ↓
Tool router                       (LLM chooses tool + args)
  ↓
Pre-tool gate  ─── BLOCKED → 403 + reason logged
  ↓ allowed
Tool execution
  ↓
Post-tool gate ─── BLOCKED → sanitized / truncated output
  ↓ clean
LLM call
  ├─ Phase 1: Proxy firewall scan  (5-layer pipeline)
  └─ Phase 2: Provider call
  ↓
Response + Trace
```

Three independent layers. Each catches what the others cannot. → [Full pipeline diagram](docs/architecture/AGENT_PIPELINE.md)

---

## Proxy firewall — second layer for all LLM traffic

An OpenAI-compatible proxy that sits between any app and any LLM provider. Every request passes through 5 detection layers before reaching the model:

```
Request
  │
  ├─ Layer 1: Rules      denylist · length · encoded content
  ├─ Layer 2: Intent     pattern classification → jailbreak / tool_abuse / exfiltration / …
  │
  ├─ Layer 3: LLM Guard  ML classifiers — injection · toxicity · secrets  (local, no cost)
  ├─ Layer 4: Presidio   spaCy NER — PII detection  (email · phone · card · ID)
  ├─ Layer 5: NeMo       semantic embeddings — 12 rails, catches paraphrases + multilingual
  │           (layers 3–5 run in parallel)
  │
  └─ Decision  weighted risk score → BLOCK / MODIFY / ALLOW
```

One URL change adds the firewall to any existing app:

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",  # ← only change
    api_key="your-key",
)
```

All scanners run **locally** — no external API calls, no per-request cost, no data leaving your environment. → [Full pipeline diagram](docs/architecture/PROXY_FIREWALL_PIPELINE.md)

Supported providers: OpenAI, Anthropic, Google Gemini, Mistral, Azure, Ollama — routed by model name via [LiteLLM](https://docs.litellm.ai/docs/providers).

---

## See it in action

<details>
<summary><strong>Agent Demo</strong> — interact with a secured tool-calling agent, switch roles, trigger the gates</summary>

<img src="docs/assets/agent-demo.png" alt="Agent Demo" />

Live agent with 5 tools gated by RBAC. Switch between `user` and `admin` roles and watch which tool calls are allowed, blocked, or held for confirmation.

**What you can inspect:**
- Pre-tool gate decisions with RBAC reason
- Post-tool gate: PII and secrets redacted from tool output
- Confirmation flow for high-sensitivity write operations
- Per-request gate log and trace

</details>

<details>
<summary><strong>Attack Scenarios</strong> — 350+ pre-built prompt injection, jailbreak, tool abuse, and exfiltration tests</summary>

Fire attack scenarios against the proxy and see whether they are blocked, modified, or allowed. Each is mapped to an OWASP LLM Top 10 category.

**What you can inspect:**
- Detected threat category and intent classification
- Risk score breakdown and policy decision (BLOCK / MODIFY / ALLOW)
- Scanner evidence and human-readable explanation

</details>

<details>
<summary><strong>Playground</strong> — chat through the firewall with real-time risk scoring</summary>

<img src="docs/assets/playground.png" alt="Playground" />

Send any prompt through the full pipeline and see the firewall's decision in real time. Switch policies to compare how thresholds change the outcome.

</details>

<details>
<summary><strong>Compare</strong> — protected vs direct model response, side by side</summary>

<img src="docs/assets/compare.png" alt="Compare" />

One prompt, two paths: through the firewall and straight to the model. See exactly what the security pipeline catches.

</details>

<details>
<summary><strong>Policies</strong> — configure thresholds and scanner weights</summary>

<img src="docs/assets/Policies.png" alt="Policies" />

Four built-in policies (fast, balanced, strict, paranoid) with fully adjustable risk thresholds and scanner weights.

</details>

<details>
<summary><strong>Analytics</strong> — blocked vs allowed, risk distribution, timeline</summary>

<img src="docs/assets/analytics.png" alt="Analytics" />

Dashboard across all requests. Filter by time window, policy, or threat category.

</details>

---

## What you get

| Capability | How |
|---|---|
| **Tool call gating by role** | RBAC with full inheritance chain, generated from wizard |
| **Argument-level injection scan** | Pre-tool gate scans every parameter before the tool runs |
| **High-risk operation confirmation** | Write + high-sensitivity tools require explicit approval |
| **PII and secrets redaction** | Post-tool gate strips output with Presidio + LLM Guard |
| **Indirect injection protection** | Post-tool gate detects payload hidden in tool output |
| **Session budgets** | Per-agent token and tool call caps |
| **Proxy firewall backstop** | 5-layer scan on final message set before provider call |
| **Per-request traces** | Full gate log, risk scores, RBAC decision per request |
| **350+ attack scenarios** | One-click, mapped to OWASP LLM Top 10 |
| **No telemetry, no SaaS** | All scanners local; API keys never logged server-side |

Scanners: [Presidio](https://github.com/microsoft/presidio) · [LLM Guard](https://github.com/protectai/llm-guard) · [NeMo Guardrails](https://github.com/NVIDIA/NeMo-Guardrails)

Threat coverage and explicit exclusions: [THREAT_MODEL.md](docs/architecture/THREAT_MODEL.md)

---

## Benchmarks

### Internal benchmark — agent security threat model

358 attack scenarios across 38 categories (OWASP LLM Top 10): prompt injection, agent abuse, tool abuse, PII exfiltration, and more.

| Metric | Value |
|--------|-------|
| Attack detection rate | **97.9%** (0% false positives) |
| Pre-LLM pipeline overhead | **~50 ms** (balanced policy) |
| Memory (all scanners) | ~1.1 GB |

→ [BENCHMARK.md](BENCHMARK.md)

### JailbreakBench (NeurIPS 2024) — external reference

698 published jailbreak artifacts — real prompts that bypassed target models in the original research.

| Metric | Value |
|--------|-------|
| Overall detection rate | **94.8%** |
| Human-crafted & random search | **100%** |
| PAIR (iterative black-box) | 88.8% |
| GCG (gradient-based) | 90.0% |

→ [BENCHMARK_JAILBREAKBENCH.md](BENCHMARK_JAILBREAKBENCH.md)

> All results are deterministic and reproducible with `make benchmark`.

---

## Quality & trust

| | |
|-|-|
| **1 500+ automated tests** | Proxy pipeline, agent gates, attack scenarios, RBAC decisions |
| **~83% line coverage** | Proxy-service, CI-enforced |
| **No telemetry** | Zero third-party analytics |
| **API keys stay in browser** | sessionStorage only, never logged server-side |
| **Security headers** | Strict CSP, X-Frame-Options DENY, nosniff, restrictive Permissions-Policy |

---

## Documentation

| Doc | What |
|-----|------|
| [architecture/AGENT_PIPELINE.md](docs/architecture/AGENT_PIPELINE.md) | Full 11-node agent pipeline — pre/post-tool gates, three lines of defense |
| [architecture/PROXY_FIREWALL_PIPELINE.md](docs/architecture/PROXY_FIREWALL_PIPELINE.md) | Full 9-node proxy pipeline — scanner models, risk score calculator |
| [architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md) | System design, two-phase LLM call flow |
| [architecture/THREAT_MODEL.md](docs/architecture/THREAT_MODEL.md) | Threat categories, scanner mapping, scope |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to contribute |

---

## Known limitations

- **Semantic attacks** — novel injection techniques can evade pattern-based scanners; defense-in-depth mitigates but doesn't eliminate.
- **No formal tool verification** — tool behavior is gated by RBAC and argument validation, but side effects after execution are not verified.
- **Domain-specific tuning** — default thresholds cover general use; production deployments need calibration.
- **Single-node** — horizontal scaling and HA not yet implemented.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Security

Found a vulnerability? See [SECURITY.md](SECURITY.md).

## License

[Apache-2.0](LICENSE)

---

Built with [LangGraph](https://github.com/langchain-ai/langgraph) · [LiteLLM](https://github.com/BerriAI/litellm) · [Presidio](https://github.com/microsoft/presidio) · [LLM Guard](https://github.com/protectai/llm-guard) · [NeMo Guardrails](https://github.com/NVIDIA/NeMo-Guardrails) · [Nuxt](https://nuxt.com/) · [Vuetify](https://vuetifyjs.com/)
