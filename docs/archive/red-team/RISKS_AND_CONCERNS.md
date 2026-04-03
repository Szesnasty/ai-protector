# Red Team Module — Risks & Concerns

> **Date:** 2026-03-23
> **Context:** Pre-implementation review of the Red Team user journey spec

---

## 1. Heuristic Quality for Custom Endpoints (High Risk)

"Medium confidence" reads well in the spec, but in practice refusal detection and pattern matching on external agents will be fragile. A user who gets an unrepresentative score on their hosted agent will lose trust in the entire product.

**Mitigation:**
- Prioritize honest messaging: "this is a smoke test, not a security audit."
- Set clear boundaries on what heuristics can and cannot detect.
- Consider a dedicated "heuristic limitations" section in the results UI — not just a tooltip.
- Track false-negative rate on custom endpoints once real usage data is available.

---

## 2. Attack Pack Staleness (Medium Risk)

30 + 25 scenarios are sufficient for a demo, but a power user will memorize them after two runs. If packs don't evolve, the perceived value drops rapidly.

**Mitigation:**
- Define a pack refresh cadence early (monthly? quarterly?).
- Version packs with semver (`pack_version` is already in the data model — good).
- Plan a community-contributed scenario pipeline (post-v1 but should be on the roadmap).
- Consider "scenario rotation" within packs — randomly sample from a larger pool so reruns feel fresh.

---

## 3. No Multi-Tenant / Isolation Story (Medium Risk)

The spec has `auth_secret_ref` with an encrypted column, which is fine for MVP. But if this becomes SaaS, several questions are unanswered:

- **Who sees whose runs?** No tenant isolation model is defined.
- **How is benchmark traffic isolated?** One user's benchmark could interfere with another's endpoint.
- **Endpoint abuse:** What stops someone from benchmarking someone else's endpoint without authorization?

**Mitigation:**
- This doesn't need to be in Iter 1, but it should be on the radar before Iter 2.
- At minimum, add a `tenant_id` / `user_id` to `BenchmarkRun` early — retrofitting is painful.
- Consider rate limiting per endpoint URL to prevent abuse.

---

## 4. Proxy Setup Friction (High Risk)

"Change your base URL" sounds simple, but in practice: DNS, TLS, CORS, auth propagation, websocket support, streaming responses. If Proxy Setup doesn't work in 5 minutes, the user drops out at exactly the point where they were supposed to convert.

**Mitigation:**
- Invest in "one-click proxy" more than in additional packs.
- Provide copy-paste snippets for common frameworks (LangChain, OpenAI SDK, custom Python).
- Consider a CLI tool: `npx ai-protector proxy --target http://localhost:8080` that handles the plumbing.
- Track proxy setup completion rate as a top-level metric.
- Have a fallback: if proxy is too hard, offer "paste your OpenAI API key and we'll intercept at the LLM level."

---

## 5. The Before/After Moment Is Everything

This is not a risk — it's the single most important insight.

The user who does a re-run and sees the score improvement is converted. Screen 4's Before/After widget is worth more than the rest of the UI combined. Everything in Iter 1 should be optimized to get the user to that moment as fast as possible.

**Implication:**
- Don't over-invest in configure screen polish — defaults should just work.
- Don't block the re-run flow for any reason.
- The path from "results → protect → re-run → Before/After" should be < 5 minutes total.

---

## Summary

| Concern | Severity | When to Address |
|---------|----------|-----------------|
| Heuristic quality for custom endpoints | High | Iter 1 (messaging), Iter 2 (improve detection) |
| Attack pack staleness | Medium | Plan in Iter 1, execute from Iter 2 |
| Multi-tenant / isolation | Medium | Design in Iter 1, implement in Iter 2 |
| Proxy setup friction | High | Iter 1 (critical path) |
| Before/After is the conversion moment | — | Iter 1 (optimize everything around it) |
