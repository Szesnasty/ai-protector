# Step 21 — OSS Maturity & Project Hygiene

> **Goal**: Transform AI Protector from a "personal repo" into a **credible open-source project**
> that looks professional on first GitHub visit. Cover CI/CD, security scanning, licensing,
> contributor experience, and social proof (badges, releases).

**Prev**: [Step 20 — Attack Scenarios Panel](../20-attack-scenarios-panel/SPEC.md)

---

## Why This Matters

When a recruiter, hiring manager, or potential contributor visits the GitHub repo, they form
an opinion in **10 seconds**. They look for:

1. Badges (CI green? tests pass? license?)
2. License (can I legally use this?)
3. Recent activity (is it maintained?)
4. Contributing guide (can I contribute?)
5. CI pipeline (is the code quality enforced?)
6. Security posture (does the author care about security?)

Without these, even a 19,000 LOC project with 348 tests looks like a student homework.

---

## Sub-steps

### 21a — License & Legal Files

| Item | Detail |
|------|--------|
| **LICENSE** | MIT License — most permissive, widest adoption. Create `LICENSE` in repo root. |
| **Why MIT** | We use MIT-compatible deps (FastAPI: MIT, LangGraph: MIT, Vuetify: MIT, LLM Guard: MIT). No copyleft contamination. |

**File**: `LICENSE`

```
MIT License

Copyright (c) 2026 Łukasz Jasiński

Permission is hereby granted, free of charge, to any person obtaining a copy...
```

**Definition of Done:**
- [x] `LICENSE` file exists in repo root
- [x] GitHub detects it (shows "MIT License" in sidebar)

---

### 21b — Community Files

| File | Purpose |
|------|---------|
| `CONTRIBUTING.md` | How to set up dev env, PR process, commit convention, code style |
| `CODE_OF_CONDUCT.md` | Contributor Covenant v2.1 (industry standard) |
| `.github/ISSUE_TEMPLATE/bug_report.md` | Structured bug report (steps to reproduce, expected/actual) |
| `.github/ISSUE_TEMPLATE/feature_request.md` | Feature request template |
| `.github/PULL_REQUEST_TEMPLATE.md` | PR checklist (tests, lint, description) |
| `SECURITY.md` | Security vulnerability disclosure policy |

**CONTRIBUTING.md outline:**
```markdown
# Contributing to AI Protector

## Quick Setup
git clone ... && make init

## Development
make dev-infra   # infrastructure only
# then run apps natively with hot-reload (see README)

## Before Submitting a PR
- make lint
- make test
- Commit messages follow Conventional Commits (feat:, fix:, docs:, etc.)

## Code Style
- Python: ruff (config in pyproject.toml)
- TypeScript/Vue: ESLint (config in eslint.config.mjs)
- No manual formatting — CI enforces it
```

**Definition of Done:**
- [x] All 6 community files exist
- [x] GitHub shows "Community Standards" checklist as mostly complete

---

### 21c — GitHub Actions CI Pipeline

The most important signal of project maturity. Three workflows:

#### Workflow 1: `ci.yml` — Lint & Test (on every push/PR)

```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint-python:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install ruff
      - run: ruff check apps/proxy-service/src/ apps/proxy-service/tests/
      - run: ruff check apps/agent-demo/src/ apps/agent-demo/tests/

  lint-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "22" }
      - run: cd apps/frontend && npm ci && npx eslint .

  test-proxy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: cd apps/proxy-service && pip install -e ".[dev]" && pytest tests/ -v --tb=short

  test-agent:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: cd apps/agent-demo && pip install -e ".[dev]" && pytest tests/ -v --tb=short

  build-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "22" }
      - run: cd apps/frontend && npm ci && npm run build

  docker-build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: cd infra && docker compose build
```

#### Workflow 2: `codeql.yml` — Security Analysis (weekly + on PR)

```yaml
name: CodeQL
on:
  push:
    branches: [main]
  schedule:
    - cron: "0 6 * * 1"  # Monday 6am

jobs:
  analyze:
    runs-on: ubuntu-latest
    permissions:
      security-events: write
    strategy:
      matrix:
        language: [python, javascript]
    steps:
      - uses: actions/checkout@v4
      - uses: github/codeql-action/init@v3
        with: { languages: "${{ matrix.language }}" }
      - uses: github/codeql-action/analyze@v3
```

#### Workflow 3: `dependency-review.yml` — Dependency Audit (on PR)

```yaml
name: Dependency Review
on: pull_request

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/dependency-review-action@v4
```

**Definition of Done:**
- [x] All 3 workflow files in `.github/workflows/`
- [x] CI passes on main (green badge!)
- [x] CodeQL scanning enabled in repo settings
- [ ] Dependency review blocks PRs with vulnerable deps

---

### 21d — Dependabot Configuration

Auto-creates PRs when dependencies have security updates.

**File**: `.github/dependabot.yml`

```yaml
version: 2
updates:
  - package-ecosystem: pip
    directory: /apps/proxy-service
    schedule: { interval: weekly }
    open-pull-requests-limit: 5

  - package-ecosystem: pip
    directory: /apps/agent-demo
    schedule: { interval: weekly }
    open-pull-requests-limit: 5

  - package-ecosystem: npm
    directory: /apps/frontend
    schedule: { interval: weekly }
    open-pull-requests-limit: 5

  - package-ecosystem: docker
    directory: /infra
    schedule: { interval: weekly }
    open-pull-requests-limit: 3

  - package-ecosystem: github-actions
    directory: /
    schedule: { interval: weekly }
    open-pull-requests-limit: 3
```

**Definition of Done:**
- [x] `.github/dependabot.yml` exists
- [x] Dependabot enabled in repo Settings → Code security
- [ ] First Dependabot PRs appear within a week

---

### 21e — Fix Failing Tests

20 tests currently fail. This MUST be fixed before CI goes green.

| Test file | Issue | Fix |
|-----------|-------|-----|
| `test_rules_crud` | 404 on rules endpoint | Check router prefix / registration |
| `test_intent_rules` | Attribute errors (denylist) | Update test fixtures to match current schema |
| Other | Various attribute mismatches | Audit each failure, fix test or code |

```bash
# Identify all failures
cd apps/proxy-service && pytest tests/ -v --tb=short 2>&1 | grep FAILED
```

**Definition of Done:**
- [x] `pytest tests/ -v` → **0 failures** (unit tests; integration tests need DB)
- [x] `ruff check src/ tests/` → **0 errors**
- [x] CI pipeline green

---

### 21f — README Badges

Add status badges to the top of README.md:

```markdown
[![CI](https://github.com/Szesnasty/ai-protector/actions/workflows/ci.yml/badge.svg)](https://github.com/Szesnasty/ai-protector/actions/workflows/ci.yml)
[![CodeQL](https://github.com/Szesnasty/ai-protector/actions/workflows/codeql.yml/badge.svg)](https://github.com/Szesnasty/ai-protector/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Nuxt 4](https://img.shields.io/badge/nuxt-4-00DC82.svg)](https://nuxt.com/)
```

**Definition of Done:**
- [x] Badges visible on GitHub repo page
- [x] CI badge shows green ✅

---

### 21g — First GitHub Release + Tag

Create a proper versioned release to signal "this is a real product":

```bash
git tag -a v0.1.0 -m "v0.1.0 — MVP: LLM Firewall + Agent Demo + Dashboard"
git push origin v0.1.0
```

Then create a **GitHub Release** (via UI or `gh` CLI):
- Title: `v0.1.0 — MVP`
- Body: changelog highlights (Steps 01-20 summary)
- Mark as pre-release (honest about maturity)

**Definition of Done:**
- [x] Git tag `v0.1.0` exists
- [x] GitHub Release published with description
- [x] Release visible on repo main page ("1 Release")

---

### 21h — Branch Protection Rules

Prevent direct pushes to main — enforce PR workflow:

**Settings → Branches → Branch protection rule for `main`:**

| Setting | Value |
|---------|-------|
| Require pull request before merging | ✅ |
| Require status checks to pass | ✅ (ci.yml jobs) |
| Require CodeQL to pass | ✅ |
| Require conversation resolution | ✅ |
| Include administrators | ❌ (you can still push directly if needed) |

**Definition of Done:**
- [x] Branch protection rule active on `main`
- [x] Pushing directly to main is blocked (except for admin override)

---

### 21i — Repository Settings Polish

Small touches that signal professionalism:

| Setting | Value |
|---------|-------|
| **Description** | "Self-hosted LLM Firewall with agentic security pipeline — OpenAI-compatible proxy for AI safety" |
| **Topics** | `llm-security`, `llm-firewall`, `ai-safety`, `langraph`, `fastapi`, `prompt-injection`, `owasp-llm-top-10`, `guardrails` |
| **Website** | (empty for now, or link to README) |
| **Social preview** | Generate an OG image (1280×640) with project name + architecture diagram |
| **Sponsor button** | Optional — adds credibility |
| **Discussions** | Enable GitHub Discussions for Q&A |

**Definition of Done:**
- [x] Description and topics set
- [ ] Social preview image uploaded
- [x] Discussions enabled

---

## Implementation Order

Execute in this sequence — each step builds on the previous:

```
21e  Fix failing tests           ← FIRST (CI won't pass without this)
 ↓
21a  LICENSE                      ← 1 minute
 ↓
21b  Community files              ← 15 minutes
 ↓
21c  GitHub Actions CI            ← 30 minutes (most impactful)
 ↓
21d  Dependabot                   ← 5 minutes
 ↓
21f  README badges                ← 5 minutes (after CI is green)
 ↓
21g  First release + tag          ← 10 minutes
 ↓
21h  Branch protection            ← 5 minutes (GitHub UI)
 ↓
21i  Repository settings          ← 10 minutes (GitHub UI)
```

**Total estimated time: 2-3 hours**

---

## Impact Assessment

| Before | After |
|--------|-------|
| No license → legally unusable | MIT → anyone can use/fork |
| No CI → "does it even work?" | Green badge → confidence |
| No security scanning → risky | CodeQL + Dependabot → enterprise-grade |
| No contributing guide → "closed project" | CONTRIBUTING.md → "come help!" |
| No release → "is it done?" | v0.1.0 → "it's shipped" |
| No badges → amateur look | 5 badges → professional first impression |
| 20 failing tests → broken | 0 failures → solid |

**Expected OSS score improvement: 6.5/10 → 8.5/10**

---

*Prev: [Step 20 — Attack Scenarios Panel](../20-attack-scenarios-panel/SPEC.md)*
