# B1 — Indirect / Second-Order Injection Detection

> **Track:** B (defense-in-depth)
> **Priority:** High
> **Effort:** M
> **Status:** Planned
> **Depends on:** A1 (shared ML detector), A2 (normalization of content)

---

## 1. Goal

Detect prompt injection that arrives **inside tool outputs and retrieved/RAG
content**, not in the user prompt. This is the 2026 frontier and aligns with the
product's thesis: security is about what the model *does*, driven by content it
ingests from untrusted sources.

## 2. Current state

- Agent side: [`post_tool_gate.py`](../../apps/agent-demo/src/agent/nodes/post_tool_gate.py)
  has a regex `INJECTION_PATTERNS` list (~15 English patterns) + `scan_injection()`.
  Same brittleness as the keyword intent classifier — obfuscated or paraphrased
  indirect injection sails through, and it is English-only.
- Proxy side: there is **no** scan path for retrieved/RAG documents before they
  enter the prompt. RAG-poisoning scenarios are caught (if at all) only by the
  user-message pipeline, which never sees the retrieved chunks.

## 3. Approach (big blocks)

1. **Shared injection detector.** Extract one detector module used by *both*
   `post_tool_gate` and the proxy, upgraded from regex to the A1 ML model +
   A2 normalization applied to tool/RAG text. Kills the divergent-regex problem.
2. **Untrusted-content scan path.** Add a node/endpoint that scans retrieved
   documents / RAG chunks *before* they are concatenated into the prompt, so
   RAG poisoning is caught pre-LLM rather than relying on the user-message path.
3. **Spotlighting / provenance for content.** Extend the delimiter-wrapping that
   [`transform.py`](../../apps/proxy-service/src/pipeline/nodes/transform.py)
   already does for user input to tool outputs and retrieved content
   (datamarking / `[TOOL_OUTPUT_START]…`), so the model can distinguish data
   from instructions.
4. **Canary-in-content (links B2).** Plant a canary in sensitive tool data;
   if it later appears in an outbound response, flag exfiltration.
5. **Severity-aware action.** BLOCK / strip-instructions / REDACT depending on
   score, consistent with the existing PASS/REDACT/TRUNCATE/BLOCK gate.

## 4. Affected components

- New shared `detectors/injection.py` (proxy + agent import it)
- `agent-demo` `post_tool_gate.py`, `security/message_builder.py`, `security/sanitizer.py`
- Proxy: new untrusted-content scan node/endpoint; `transform.py` spotlighting

## 5. Acceptance criteria

- [ ] Indirect-injection scenarios (RAG poisoning, cross-tool exploitation) show
      improved detection, measured via A3.
- [ ] Obfuscated indirect injection (leet/ROT inside a tool result) is caught
      (A2 applied to content).
- [ ] Proxy and agent share one detector implementation (no divergent regex).
- [ ] Threat model doc updated to reflect the new coverage.

## 6. Out of scope

- The ML model training (A1) and normalization (A2) — consumed here, not built.

## 7. Risks / open questions

- Scanning large RAG payloads adds latency — apply size limits / sampling.
- Over-blocking legitimate documents that quote instructions — tune with the
  benign corpus from A3.
