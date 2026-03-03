# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in AI Protector, please report it responsibly.

**Do NOT open a public GitHub issue for security vulnerabilities.**

Instead, please email the maintainer directly or use GitHub's
[private vulnerability reporting](https://github.com/Szesnasty/ai-protector/security/advisories/new).

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅ Current |

## Security Measures in This Project

AI Protector is itself a security tool (LLM Firewall), and we take security seriously:

- **Dependency scanning**: Dependabot monitors all dependencies weekly
- **Static analysis**: CodeQL runs on every push and weekly
- **Dependency review**: All PRs are checked for vulnerable dependencies
- **No secrets in code**: All credentials are passed via environment variables

## Scope

This security policy covers the AI Protector codebase itself. It does **not** cover:

- The security of the LLM models you run behind the firewall
- Third-party services (Ollama, Langfuse, PostgreSQL) — those have their own security policies
- Attack scenarios in the demo panel — those are intentionally malicious prompts for testing purposes
