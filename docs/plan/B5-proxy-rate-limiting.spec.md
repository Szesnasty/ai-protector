# B5 — Proxy Rate Limiting / DoS Controls

> **Track:** B (defense-in-depth)
> **Tracks issue:** ISS-008 (hardcoded limits → policy-configurable)
> **Priority:** Medium
> **Effort:** S
> **Status:** Planned

---

## 1. Goal

Give the proxy request-volume and resource controls. The agent layer has
per-session budgets (tokens / tool calls / cost), but the proxy has none — it
catches token-bomb *text* via `RESOURCE_EXHAUSTION` patterns, but nothing caps
request *volume* or aggregate cost per client.

## 2. Current state

[`main.py`](../../apps/proxy-service/src/main.py) installs only CORS and a
correlation-id middleware. No rate limiting, no concurrency cap, no per-client
budget. Redis is already a dependency and is used for caching/pub-sub — the
backing store for limits already exists. Per-request length/message limits live
in `rules.py` but are hardcoded (ISS-008).

## 3. Approach (big blocks)

1. **Rate-limit middleware/dependency.** Token-bucket or sliding-window counter
   in Redis, keyed by client-id / API key / IP. Limits configurable globally and
   per policy.
2. **Concurrency + payload guards.** Max concurrent in-flight requests per
   client; max body size; make the existing `MAX_PROMPT_LENGTH`, `MAX_MESSAGES`,
   `SPECIAL_CHAR_THRESHOLD` (rules.py) policy-configurable per ISS-008.
3. **Cost/token budget at the proxy.** Mirror the agent's budget concept: cap
   tokens (and optionally estimated cost) per client per window.
4. **Responses & observability.** Return `429` with `Retry-After`; expose
   rate-limit headers; emit metrics/logs for breaches.

## 4. Affected components

- `main.py` (middleware registration), new `middleware/rate_limit.py`
- `db/session.py` Redis client, `config.py` (limit settings)
- `pipeline/nodes/rules.py` (make limits policy-configurable — ISS-008)

## 5. Acceptance criteria

- [ ] Configurable per-client rate limit enforced; breach returns `429` +
      `Retry-After`.
- [ ] Concurrency cap and max body size enforced.
- [ ] `rules.py` length/message/special-char limits are policy-configurable.
- [ ] A simple load test demonstrates the proxy sheds excess load instead of
      melting.
- [ ] Limits documented for production deployers (ties into the threat model's
      "add rate limiting" recommendation).

## 6. Out of scope

- Distributed/HA rate limiting across multiple proxy nodes (single-node scope
  for now; Redis keying leaves the door open for it later).

## 7. Risks / open questions

- Keying choice (API key vs IP vs client-id) affects multi-tenant fairness —
  default to client-id/API key, fall back to IP.
- Redis availability becomes part of the request path — fail-open or fail-closed
  on Redis outage must be a conscious, configurable decision.
