# AI Protector

**Ship AI agents with guardrails — not prayers.**

AI Protector is a self-hosted runtime security layer for tool-calling agents. Generate RBAC policies in a 7-step wizard, wire them into your agent, and enforce every tool call deterministically at runtime — with an OpenAI-compatible proxy firewall as a second line of defense.

[![CI](https://github.com/Szesnasty/ai-protector/actions/workflows/ci.yml/badge.svg)](https://github.com/Szesnasty/ai-protector/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-83%25-green)](https://github.com/Szesnasty/ai-protector/actions/workflows/ci.yml)
[![Internal Suite](https://img.shields.io/badge/🎯_internal_suite-97.9%25-brightgreen)](BENCHMARK.md)
[![JailbreakBench](https://img.shields.io/badge/🛡_JailbreakBench-94.8%25-brightgreen)](BENCHMARK_JAILBREAKBENCH.md)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Nuxt 4](https://img.shields.io/badge/Nuxt-4-00DC82?logo=nuxt.js&logoColor=white)](https://nuxt.com/)

<p align="center">
  <img src="docs/assets/agent-demo.png" alt="AI Protector — live agent with gate log showing allowed and blocked tool calls" />
</p>

---

## Quickstart

```bash
git clone https://github.com/Szesnasty/ai-protector.git
cd ai-protector
make demo
```

Open **http://localhost:3000**. Done. Start with the **Agent Demo** to see allowed and blocked tool calls immediately.

> **Requirements:** Docker & Docker Compose. No GPU, no API keys, no Ollama.
>
> The demo ships with two pre-configured agents and 350+ attack scenarios. Paste an API key in **Settings** to switch to a real LLM provider.

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

## Agent Wizard + runtime enforcement

The wizard generates your security config in 7 steps. The runtime enforces it on every tool call.

<p align="center">
  <img src="docs/assets/agent-wizard.png" alt="Agent Wizard" />
</p>

**What the wizard produces:**

| Step | What happens |
|---|---|
| 1 — Describe | Name, framework (LangGraph / pure Python / custom), policy pack |
| 2 — Register tools | Declare each tool: sensitivity (low/medium/high), read or write |
| 3 — Define roles | RBAC hierarchy with inheritance — each role gets exactly what it needs |
| 4 — Security policy | Choose a base pack (balanced/strict/paranoid), see activated scanners |
| 5 — Review | Inspect the full generated RBAC policy before saving |
| 6 — Integration kit | Generated `rbac.yaml`, `config.yaml`, and framework-specific code snippet |
| 7 — Validate | Run the built-in attack suite against your config before going live |

**What gets enforced at runtime:**

```
Agent decides to call a tool
          ↓
  ┌───────────────────┐
  │   Pre-tool gate   │  RBAC · argument injection scan · budget · confirmation
  └───────────────────┘
          ↓ allowed
    Tool executes
          ↓
  ┌───────────────────┐
  │  Post-tool gate   │  PII redaction · secrets scan · indirect injection
  └───────────────────┘
          ↓ sanitized
  LLM call  →  proxy firewall scan (5 layers)  →  provider
```

The pre-tool gate blocks any call the current role doesn't have, requires confirmation for high-sensitivity writes, and scans arguments for injection before they reach the tool. The post-tool gate scrubs output for PII, secrets, and indirect injection payloads before they're fed back to the model. The proxy firewall runs as a final backstop on the assembled message set. → [Full pipeline](docs/architecture/AGENT_PIPELINE.md)

---

## Proxy firewall — second line of defense

An OpenAI-compatible proxy backstop for all LLM traffic. 5 detection layers (rules → intent → LLM Guard → Presidio → NeMo embeddings) run locally before every model call — no external API calls, no per-request cost. One URL change to add it to any app:

```python
client = OpenAI(base_url="http://localhost:8000/v1", api_key="your-key")
```

Supported providers: OpenAI, Anthropic, Google Gemini, Mistral, Azure, Ollama via [LiteLLM](https://docs.litellm.ai/docs/providers). → [Full pipeline](docs/architecture/PROXY_FIREWALL_PIPELINE.md)

---

## What you get

| Capability | How |
|---|---|
| **Wizard-generated RBAC + integration kit** | `rbac.yaml`, `config.yaml`, and code snippet — ready to drop in |
| **Tool call gating by role** | Full inheritance chain enforced deterministically at runtime |
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
