# 07 — CI & GitHub Release

> **Priority:** Important | **Effort:** 1h | **Dependencies:** none (independent, do last)

---

## Goal

Enable CI on push/PR, create first GitHub release, set repository metadata, clean up dead scaffolding. Signal to visitors: "this is a maintained, serious project."

---

## 1. Enable CI workflows

### 1.1 `.github/workflows/ci.yml`

Currently disabled (`workflow_dispatch` only). Re-enable:

```yaml
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:
```

**Before enabling:** Run CI locally to make sure it passes:
```bash
make lint && make test
```

Fix any failures first. Don't enable CI with a red badge.

### 1.2 `.github/workflows/codeql.yml`

Same — enable on push/PR:
```yaml
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 6 * * 1'  # Weekly Monday
```

### 1.3 `.github/workflows/dependency-review.yml`

Enable on PR only:
```yaml
on:
  pull_request:
    branches: [main]
```

---

## 2. GitHub repository settings

### 2.1 Topics (set via GitHub UI → About → Topics)

```
llm-security
ai-firewall
prompt-injection
langgraph
agent-security
owasp-llm-top-10
llm-proxy
self-hosted
presidio
nemo-guardrails
```

### 2.2 Description (set via GitHub UI → About)

```
Self-hosted LLM Firewall with agentic security pipeline. OpenAI-compatible proxy that protects LLM apps and AI agents from prompt injection, jailbreaks, PII leaks, and more. Demo mode included.
```

### 2.3 Website URL

```
http://localhost:3000
```
(Or deployed demo URL once available)

---

## 3. First release: v0.1.0-beta

### 3.1 Create tag

```bash
git tag -a v0.1.0-beta -m "First public beta — demo mode, 820+ tests, 358 attack scenarios"
git push origin v0.1.0-beta
```

### 3.2 GitHub Release notes

```markdown
# v0.1.0-beta — First Public Release

AI Protector is a self-hosted LLM Firewall with an agentic security pipeline.

## Highlights

- **Demo mode** — run without LLM models or API keys (`make demo`)
- **11-node LangGraph firewall pipeline** — Parse → Intent → Rules → Scanners → Decision → Output Filter
- **3 scanner backends** — Presidio PII, LLM Guard, NeMo Guardrails
- **Agent demo** — Customer Support Copilot with RBAC, pre/post tool gates, budget limits
- **358 attack scenarios** — one-click tests for OWASP LLM Top 10
- **820+ passing tests** across proxy-service and agent-demo
- **Full dashboard** — Playground, Agent Demo, Analytics, Policies, Rules, Request Log

## Quick Start

\```bash
git clone https://github.com/Szesnasty/ai-protector.git
cd ai-protector
make demo
# Open http://localhost:3000
\```

## Requirements

- Docker & Docker Compose
- No GPU, no API keys, no Ollama needed for demo mode

## What's next

See [ROADMAP](docs/ROADMAP.spec.md) for planned features: Red Team Lab, adaptive policies, multi-tenancy, and more.
```

---

## 4. Clean up dead scaffolding

### 4.1 Remove empty TypeScript SDK

```bash
rm -rf sdks/
```

The `sdks/typescript/` directory contains only empty folders. Better to remove it than show visitors an empty skeleton. Add it back when implementation starts.

### 4.2 Update `.gitignore` (if needed)

Ensure no build artifacts, `.env` with secrets, or `node_modules` are tracked.

---

## 5. Good First Issues (create via GitHub UI)

Create 5–10 issues with `good first issue` label:

| Issue title | Description | Label |
|-------------|-------------|-------|
| Add Playwright E2E test for playground chat | Write a basic E2E test that sends a message and verifies response | `good first issue`, `testing` |
| Add response time to request log table | Show response latency column in the Request Log page | `good first issue`, `frontend` |
| Add dark/light theme toggle | Persist user's theme preference in localStorage | `good first issue`, `frontend` |
| Add export to CSV for request log | Download filtered request history as CSV | `good first issue`, `feature` |
| Add Spanish PII detection support | Configure Presidio with `es` language model | `good first issue`, `security` |
| Add rate limit display in agent demo | Show remaining budget/calls in the agent chat UI | `good first issue`, `frontend` |
| Write MockProvider unit tests | Test all 5 intent-based responses + streaming | `good first issue`, `testing` |
| Add Docker health check for frontend | Add healthcheck to frontend service in docker-compose | `good first issue`, `infra` |

---

## 6. Files to modify

| File | Change |
|------|--------|
| `.github/workflows/ci.yml` | Uncomment `push`/`pull_request` triggers |
| `.github/workflows/codeql.yml` | Uncomment triggers |
| `.github/workflows/dependency-review.yml` | Uncomment triggers |
| `sdks/` | Delete empty directory |

---

## 7. Execution order

1. Run `make lint && make test` — fix any failures
2. Enable CI triggers in workflow files
3. Push to `main` → verify CI passes (green badge)
4. Set topics + description on GitHub
5. Create `v0.1.0-beta` tag + GitHub Release
6. Create Good First Issues
7. Remove empty `sdks/`

---

## 8. Verification

| Check | How |
|-------|-----|
| CI badge green | Visit repo → see badge |
| CodeQL badge green | Visit repo → see badge |
| Release visible | Visit repo → Releases section shows v0.1.0-beta |
| Topics visible | Visit repo → see topic tags under description |
| Good First Issues | Visit Issues tab → filter by `good first issue` label |
| `sdks/` removed | Not in file tree |
