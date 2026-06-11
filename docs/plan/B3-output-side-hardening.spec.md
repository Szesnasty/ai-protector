# B3 — Output-Side Hardening

> **Track:** B (defense-in-depth)
> **Tracks issue:** ISS-007 (system-prompt leak), ISS-010 (secrets coverage)
> **Priority:** Medium
> **Effort:** S–M
> **Status:** Planned

---

## 1. Goal

Make response-side detection robust: catch system-prompt leakage by *meaning*
rather than four hardcoded strings, and expand secret detection to the formats
that actually appear in the wild.

## 2. Current state

In [`output_filter.py`](../../apps/proxy-service/src/pipeline/nodes/output_filter.py):

- **System-prompt leak (ISS-007):** `SYSTEM_FRAGMENTS` is **4 fixed strings**.
  An LLM that re-words the system prompt leaks it undetected.
- **Secrets (ISS-010):** `SECRET_PATTERNS` is **5 regexes** (OpenAI/GitHub keys,
  Bearer, private key, password). Missing AWS/Azure/GCP keys, Slack, JWT,
  connection strings, Stripe, etc.
- Meanwhile the **agent** post-tool gate already has a richer secret/PII set
  ([`post_tool_gate.py`](../../apps/agent-demo/src/agent/nodes/post_tool_gate.py)) —
  the two have drifted.

## 3. Approach (big blocks)

1. **Semantic system-prompt-leak detection.** When the request carries a system
   prompt, embed it and the response (reuse FastEmbed — already a NeMo
   dependency) and flag high cosine similarity between response spans and the
   system prompt. Keep a lightweight heuristic fallback when no system prompt is
   available.
2. **Expanded + shared secret detection.** Integrate `detect-secrets` (or expand
   the pattern set) and **unify** proxy + agent into one shared secrets module so
   they stop diverging. Cover AWS/Azure/GCP, Slack, JWT, connection strings,
   Stripe, generic high-entropy tokens.
3. **Streaming coverage (sub-block).** Confirm and, if needed, extend filtering
   to streamed responses (`llm/streaming.py`) — a leak that only appears in SSE
   chunks must still be caught/redacted.

## 4. Affected components

- `pipeline/nodes/output_filter.py`
- New shared `detectors/secrets.py` (imported by proxy + agent post-tool gate)
- FastEmbed embedding helper (reuse from NeMo stack)
- `llm/streaming.py` (streaming path)

## 5. Acceptance criteria

- [ ] A paraphrased system-prompt leak is detected (embedding similarity), not
      just verbatim fragments.
- [ ] Secret coverage expanded and shared between proxy and agent (one module).
- [ ] Streaming responses are filtered equivalently to non-streaming.
- [ ] No FPR regression on benign output (measured via A3).

## 6. Out of scope

- Input-side secret detection (already handled by LLM Guard `Secrets`).

## 7. Risks / open questions

- Embedding every response adds latency — gate behind policy and/or only run
  when a system prompt is present and the response is long enough to matter.
- `detect-secrets` plugin footprint and false positives on code-heavy outputs.
