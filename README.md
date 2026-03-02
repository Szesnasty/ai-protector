# AI Protector

Self-hosted **LLM Firewall with an Agentic Security Pipeline** — an OpenAI-compatible proxy that scans, classifies, and enforces policies on every LLM request and response. Includes a demo agent app (Customer Support Copilot) to showcase both **building** and **securing** AI agents.

## Highlights

- **Policy Agent** — LangGraph-based firewall pipeline (not a dumb filter chain)
- **Two-Level Security** — agent-level + proxy-level protection
- **Agent Demo** — working tool-calling agent running behind the firewall
- **Full Observability** — Langfuse tracing, structured logging, risk scoring
- **Local-first** — runs on Ollama (Llama 3.1 8B), no cloud keys needed

## Tech Stack

**Frontend:** Nuxt 4 · Vuetify 3 · Pinia · vue-echarts
**Backend:** FastAPI · LangGraph · LiteLLM · LLM Guard · Presidio · NeMo Guardrails
**Infra:** Docker Compose · PostgreSQL 16 · Redis 7 · Ollama · Langfuse

## Docs

- [MVP Spec](docs/MVP.spec.md) — architecture, agentic pipeline, agent demo, implementation plan
- [Roadmap](docs/ROADMAP.spec.md) — Red Team engine, adaptive policies, enterprise features
