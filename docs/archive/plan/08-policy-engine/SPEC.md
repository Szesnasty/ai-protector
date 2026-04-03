# Step 08 — Policy Engine

| | |
|---|---|
| **Phase** | Firewall Pipeline |
| **Estimated time** | 6–8 hours |
| **Prev** | [Step 07 — Security Scanners](../07-security-scanners/SPEC.md) |
| **Next** | [Step 09 — Output Pipeline](../09-output-pipeline/SPEC.md) |
| **Master plan** | [MVP-PLAN.md](../MVP-PLAN.md) |

---

## Goal

Formalize the **policy engine**: expose policies via a REST CRUD API, add a dedicated `PolicyDecisionNode` that dynamically resolves thresholds from DB, enforce 4 policy levels (`fast` / `balanced` / `strict` / `paranoid`), and add policy validation + versioning.

After this step, operators can create/update/delete policies via API, each request selects its policy via `x-policy` header, and the pipeline dynamically applies the correct thresholds and scanner selection.

---

## Sub-steps

| # | File | Scope | Est. |
|---|------|-------|------|
| a | [08a — Policies CRUD API](08a-policies-crud.md) | REST endpoints for policies (list, get, create, update, delete), Pydantic schemas | 2–2.5h |
| b | [08b — Policy Validation & Seed Update](08b-policy-validation.md) | Config schema validation, version bumping, enforce required fields, update seed data | 1.5–2h |
| c | [08c — Policy-Aware Decision Node](08c-policy-decision.md) | Dynamic threshold resolution, policy-level scanner selection, Redis cache invalidation on CRUD | 2–2.5h |

---

## Architecture (after this step)

```
x-policy: "strict"
    │
    ▼
PolicyResolver (runner.py)
    │  ── Redis cache (60s TTL) → DB lookup
    ▼
policy_config: {
    "nodes": ["llm_guard", "presidio"],
    "thresholds": {
        "max_risk": 0.5,
        "injection_threshold": 0.3,
        "pii_action": "mask"
    }
}
    │
    ▼
parse → intent → rules → scanners → decision → ...
                                       │
                              uses policy_config.thresholds
                              to resolve max_risk, pii_action, etc.
```

```
REST API:
  GET    /v1/policies          → list all
  GET    /v1/policies/{id}     → get one
  POST   /v1/policies          → create
  PATCH  /v1/policies/{id}     → update (bumps version)
  DELETE /v1/policies/{id}     → soft-delete (is_active=false)
```

---

## Technical Decisions

### Why REST CRUD for policies (not hardcoded)?
Step 03 seeded 4 default policies. But operators need to customize thresholds, add new policies for specific clients, or disable scanners. A CRUD API makes policies a first-class resource.

### Why version bumping on update?
Policies are referenced by `policy_id` in the `requests` table. Version tracking lets us audit which config version was active when a request was processed.

### Why Redis cache invalidation on CRUD?
`runner.py` caches policy config in Redis (60s TTL). When a policy is updated via API, we must invalidate the cache so the next request picks up the new config immediately.

### Why policy config validation?
Invalid policy configs (e.g., `max_risk: "foo"`, missing `thresholds`) can crash the pipeline. A Pydantic model for `PolicyConfig` catches errors at API time, not at request time.

---

## Definition of Done (aggregate)

All sub-step DoDs must pass. Quick smoke test:

```bash
# List policies
curl -s http://localhost:8000/v1/policies | python3 -m json.tool

# Create custom policy
curl -s -X POST http://localhost:8000/v1/policies \
  -H "Content-Type: application/json" \
  -d '{"name":"custom","description":"Custom test","config":{"thresholds":{"max_risk":0.6},"nodes":["llm_guard"]}}' \
  | python3 -m json.tool

# Update policy → version bumps
curl -s -X PATCH http://localhost:8000/v1/policies/{id} \
  -H "Content-Type: application/json" \
  -d '{"config":{"thresholds":{"max_risk":0.5},"nodes":["llm_guard","presidio"]}}' \
  | python3 -m json.tool

# Use custom policy in chat
curl -s http://localhost:8000/v1/chat/completions \
  -H "x-policy: custom" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Hello!"}]}'
```

---

| **Prev** | **Next** |
|---|---|
| [Step 07 — Security Scanners](../07-security-scanners/SPEC.md) | [Step 09 — Output Pipeline](../09-output-pipeline/SPEC.md) |
