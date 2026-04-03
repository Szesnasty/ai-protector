# Go-Live Plan — AI Protector Public Launch

> **Branch:** `feat/go-live`
> **Goal:** Make the repo ready for public GitHub launch with a zero-friction demo experience.

---

## Specs (implementation order)

| # | Spec | Effort | Priority | Description |
|---|------|--------|----------|-------------|
| 01 | [Mock Provider + MODE](01-mock-provider.md) | 4–6h | Critical | `MODE=demo\|real`, MockProvider in proxy + agent-demo |
| 02 | [Docker Profiles](02-docker-profiles.md) | 1–2h | Critical | `make demo` / `make up` / `make dev` |
| 03 | [CSP & Security Headers](03-csp-headers.md) | 1–2h | Important | Dynamic CSP via server middleware, full security headers |
| 04 | [UI Demo Mode](04-ui-demo-mode.md) | 1–2h | Important | Badge, health endpoint extension, model selector |
| 05 | [Seed Demo Data](05-seed-demo.md) | 1h | Nice-to-have | Script to populate analytics on first start |
| 06 | [README Rewrite](06-readme-rewrite.md) | 2–3h | Critical | Hero section, screenshot/GIF, 3-line quickstart |
| 07 | [CI & GitHub Release](07-ci-release.md) | 1h | Important | Enable CI, topics, v0.1.0-beta tag, cleanup |

**Total estimated effort: ~1.5–2 days**

---

## Dependency graph

```
01-mock-provider ──┐
                   ├──→ 02-docker-profiles ──→ 05-seed-demo
                   │
                   └──→ 04-ui-demo-mode
                                       ╲
03-csp-headers (independent)            ╲
                                         ╲
06-readme-rewrite (needs 02 done)  ───────→ 07-ci-release (last)
```

## Principles

1. **Security pipeline is ALWAYS real** — NeMo, Presidio, LLM Guard, rules, pre/post tool gates run in all modes.
2. **Only LLM provider is mocked** — MockProvider replaces the LLM call, nothing else.
3. **Zero external dependencies for demo** — no Ollama, no API keys, no GPU.
4. **API key overlay** — user can paste a key in Settings UI at any time and get real responses, regardless of MODE.
