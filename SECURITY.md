# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in AI Protector, please report it responsibly.

**Do NOT open a public GitHub issue for security vulnerabilities.**

Instead, please email the maintainer directly or use GitHub's
[private vulnerability reporting](https://github.com/Szesnasty/ai-protector/security/advisories/new).

## Supported Versions

| Version | Status              |
|---------|---------------------|
| 0.2.x   | ✅ Active support    |
| 0.1.x   | ⚠️ Security fixes only |
| < 0.1   | ❌ Unsupported        |

## Security Measures in This Project

AI Protector is itself a security tool (LLM Firewall), and we take security seriously:

- **Documented threat model**: assets, trust boundaries, controls and residual risks are tracked in [`docs/architecture/THREAT_MODEL.md`](docs/architecture/THREAT_MODEL.md)
- **Adversarial self-review**: the codebase is periodically reviewed against its own threat model (SSRF, injection, deserialization, DoS/ReDoS, authz, supply chain); findings are triaged and fixed or logged as accepted residual risks
- **Dependency scanning**: Dependabot monitors all dependencies weekly
- **Static analysis**: CodeQL runs on every push and weekly
- **Dependency review**: All PRs are checked for vulnerable dependencies
- **No secrets in code**: All credentials are passed via environment variables; pinned deps and `.env` files are gitignored

## Scope

This security policy covers the AI Protector codebase itself. It does **not** cover:

- The security of the LLM models you run behind the firewall
- Third-party services (Ollama, Langfuse, PostgreSQL) — those have their own security policies
- Attack scenarios in the demo panel — those are intentionally malicious prompts for testing purposes

## Deployment Posture

AI Protector ships as a **local-first, single-tenant** tool. The management surface
(policies, rules, scanner, agent wizard) is unauthenticated by design for that scope;
the bundled demo binds to localhost with a localhost-only CORS origin. Before exposing
an instance beyond localhost, follow the production recommendations in the
[threat model](docs/architecture/THREAT_MODEL.md#9-recommendations-for-production) —
in particular, add authentication and network segmentation, and leave
`RED_TEAM_ALLOW_PRIVATE_TARGETS` unset so the scanner refuses internal/metadata targets.

## Hardening Roadmap

Defense-in-depth improvements tracked for hardening beyond the current single-tenant scope:

- **Optional authentication layer** for the management API (static token / JWT), enabled by config for non-local deployments
- **Non-root containers** — add a `USER` directive across service images
- **Digest-pinned base images** — pin container base images by SHA in addition to Dependabot monitoring
- **Minimal CI token scope** — explicit least-privilege `permissions:` blocks across workflows
- **SBOM generation** — publish a software bill of materials on release
- **Frontend link hardening** — enforce `rel="noopener"` on generated external links
