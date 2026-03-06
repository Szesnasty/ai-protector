# 06 — README Rewrite

> **Priority:** Critical | **Effort:** 2–3h | **Dependencies:** 02-docker-profiles (for correct make targets)

---

## Goal

Rewrite the README hero section for GitHub landing page conversion. A visitor should understand what AI Protector does and have it running in 60 seconds.

---

## 1. Current problem

The README is thorough but optimized for someone who already decided to use the project. GitHub visitors need:
1. **What is this?** (5 seconds)
2. **Show me** (screenshot/GIF)
3. **How do I try it?** (2 commands)
4. **Why should I care?** (key features)

---

## 2. New README structure

```
# AI Protector

[one-line description]
[badges]

[SCREENSHOT or GIF — full width]

## Try it now (2 commands)

## What it does (bullet list)

## Demo mode vs Real mode (one table)

## Architecture (existing diagram — keep)

## Features (keep existing, reorganize)

## Tech Stack (keep)

## API Reference (keep)

## Contributing (keep)

## License (keep)
```

---

## 3. Hero section (new)

```markdown
# AI Protector

Self-hosted **LLM Firewall** with an agentic security pipeline. 
Drop-in OpenAI-compatible proxy that scans, classifies, and enforces 
policies on every LLM request and response — in real time.

[![CI](badge)](link) [![License: MIT](badge)](link) [![Python 3.12](badge)](link) [![Nuxt 4](badge)](link)

> **Demo mode included** — runs without LLM models or API keys. 
> Security pipeline is real. LLM responses are simulated.

![AI Protector Dashboard](docs/assets/screenshot-dashboard.png)
```

---

## 4. Quickstart section (new)

```markdown
## Quick Start

```bash
git clone https://github.com/Szesnasty/ai-protector.git
cd ai-protector
make demo
```

Open **http://localhost:3000**. That's it.

> **Requirements:** Docker & Docker Compose. No GPU, no API keys, no Ollama.

### What to try first

1. **Attack Scenarios** — click the ⚡ panel and run 358 pre-built attacks (injection, jailbreak, PII, exfiltration...)
2. **Playground** — chat with the firewall and see real-time risk scoring
3. **Agent Demo** — test a tool-calling agent with RBAC, pre/post tool gates, and budget limits
4. **Analytics** — view blocked vs allowed requests, risk distribution, timeline

### Want real LLM responses?

| Option | Command | What you need |
|--------|---------|---------------|
| **API key** | Paste in Settings → API Keys | OpenAI/Anthropic/Google/Mistral key |
| **Local LLM** | `make up` | 8GB+ RAM, ~15 min first setup |
```

---

## 5. "What it does" section (new — replaces verbose Highlights)

```markdown
## What it does

**Two-level security model:**

```
Level 1: AGENT-LEVEL (inside the agent)
  → RBAC, tool access control, argument validation, budget limits

Level 2: PROXY-LEVEL (firewall — model-agnostic)
  → Prompt injection, PII detection, jailbreak, toxicity, secrets, custom rules
```

- **11-node LangGraph pipeline** — not a filter chain, an agentic firewall
- **3 scanner backends** — Presidio (PII), LLM Guard (injection/toxicity), NeMo Guardrails (dialog rails)
- **358 attack scenarios** — one-click tests for OWASP LLM Top 10
- **OpenAI-compatible API** — change one URL to protect any existing app
- **Full observability** — Langfuse tracing, structured logging, per-request risk scoring
- **Agent security demo** — pre/post tool gates, RBAC, confirmation flows, budget caps
```

---

## 6. Screenshot / GIF requirements

### What to capture (priority order):

1. **Playground with attack scenario** — prompt → BLOCK with risk score and flags
2. **Agent Demo** — tool call → RBAC block or successful tool execution with trace
3. **Analytics dashboard** — charts showing blocked/allowed distribution
4. **Attack scenarios panel** — grid of 358 scenarios with one-click run

### Format:
- **Screenshot:** PNG, ~1200px wide, dark theme
- **GIF:** 15–30 seconds, 800px wide, showing: select scenario → click run → see BLOCK result
- Store in `docs/assets/`

### Placeholder until screenshots ready:
```markdown
<!-- TODO: Add screenshot before public launch -->
> 📸 Screenshot coming soon. Run `make demo` to see the UI.
```

---

## 7. Sections to keep (minor edits)

| Section | Change |
|---------|--------|
| Pipeline Architecture | Keep diagram, no changes |
| Two-Level Security Model | Keep, already good |
| Current Status | Update test count, mark demo mode |
| Tech Stack | Keep table |
| Project Structure | Keep, update LOC numbers if changed |
| API Reference | Keep |
| Configuration | Add `MODE` to table |
| Local Development | Rename to match `make dev` |
| Docs links | Keep |

---

## 8. Sections to remove / condense

| Section | Action |
|---------|--------|
| "Daily workflow" (make commands) | Condense into quickstart |
| "Already have the images built?" | Remove — redundant |
| Verbose Highlights bullets | Replace with "What it does" |

---

## 9. Files to modify

| File | Change |
|------|--------|
| `README.md` | Full rewrite of top section, keep bottom sections |
| `docs/assets/` | New directory for screenshots |

---

## 10. Checklist before publish

- [ ] Screenshot or GIF at top of README
- [ ] `make demo` works from clean clone
- [ ] "Quick Start" section tested on fresh machine
- [ ] All links in README work
- [ ] Badge URLs are correct
- [ ] No internal/private references
