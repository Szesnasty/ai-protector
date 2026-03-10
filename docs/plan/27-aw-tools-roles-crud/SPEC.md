# Step 27 — Tools & Roles CRUD API + DB Models

**Prereqs:** Step 26 (Agent CRUD)
**Spec ref:** agents-v1.spec.md → Req 2
**Effort:** 2–3 days
**Output:** Tool registry, role management, permission matrix — all in DB

---

## Why this step matters

Tools are attack surface. Roles are access control. Without them in the DB,
config generation (step 28) has nothing to work with.

---

## Sub-steps

### 27a — Tool DB model + CRUD API

| Table | `agent_tools` |
|-------|---------------|
| Columns | `id` (UUID), `agent_id` (FK), `name`, `description`, `category` (str), `access_type` (enum: read/write), `sensitivity` (enum: low/medium/high/critical), `requires_confirmation` (bool, auto-set from rules), `arg_schema` (JSONB, nullable — JSON Schema format), `returns_pii` (bool), `returns_secrets` (bool), `rate_limit` (int, nullable — max calls per session), `created_at`, `updated_at` |

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/agents/:id/tools` | POST | Register tool |
| `/agents/:id/tools` | GET | List tools for agent |
| `/agents/:id/tools/:tool_id` | PATCH | Update tool |
| `/agents/:id/tools/:tool_id` | DELETE | Remove tool |

Smart defaults (applied on POST/PATCH):
- `access_type=write` + `sensitivity≥high` → `requires_confirmation=true`
- `returns_pii=true` → auto-flag for post-tool PII scan
- `rate_limit` defaults: low=20, medium=10, high=5, critical=3

**DoD:**
- [ ] SQLAlchemy model `AgentTool`
- [ ] Alembic migration
- [ ] Pydantic schemas: `ToolCreate`, `ToolUpdate`, `ToolResponse`
- [ ] All 4 endpoints working
- [ ] Smart defaults applied and visible in response
- [ ] Validation: name unique per agent, arg_schema is valid JSON Schema (if provided)
- [ ] Tests: CRUD cycle, smart defaults, uniqueness constraint

### 27b — Role DB model + CRUD API

| Table | `agent_roles` |
|-------|---------------|
| Columns | `id` (UUID), `agent_id` (FK), `name`, `inherits_from` (FK to self, nullable), `description`, `created_at` |

| Table | `role_tool_permissions` |
|-------|------------------------|
| Columns | `id` (UUID), `role_id` (FK), `tool_id` (FK), `scopes` (JSONB: ["read","write"]), `requires_confirmation_override` (bool, nullable), `conditions` (JSONB, nullable — future use) |

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/agents/:id/roles` | POST | Create role |
| `/agents/:id/roles` | GET | List roles with resolved permissions (including inherited) |
| `/agents/:id/roles/:role_id` | PATCH | Update role |
| `/agents/:id/roles/:role_id` | DELETE | Remove role (cascade permissions) |
| `/agents/:id/roles/:role_id/permissions` | PUT | Set tool permissions for role (batch upsert) |

Permission resolution: if role inherits from parent, GET returns **merged** permissions
(child overrides parent). Default-deny: tool not in permission set → DENY.

**DoD:**
- [ ] SQLAlchemy models `AgentRole` + `RoleToolPermission`
- [ ] Alembic migration
- [ ] Pydantic schemas with inheritance resolution
- [ ] All 5 endpoints working
- [ ] Inheritance resolution: child tools merged with parent, child overrides win
- [ ] Default-deny: `/agents/:id/check-permission?role=X&tool=Y` returns ALLOW/DENY
- [ ] Tests: CRUD, inheritance chain (3 levels), default-deny, permission override

### 27c — Permission matrix endpoint

A single endpoint that returns the full role×tool grid for the UI:

```
GET /agents/:id/permission-matrix
→ {
    tools: ["searchKB", "getOrder", "issueRefund"],
    roles: ["customer", "support", "admin"],
    matrix: {
      customer: { searchKB: "allow", getOrder: "allow", issueRefund: "deny" },
      support:  { searchKB: "allow", getOrder: "allow", issueRefund: "deny" },
      admin:    { searchKB: "allow", getOrder: "allow", issueRefund: "confirm" }
    }
  }
```

**DoD:**
- [ ] Endpoint returns resolved matrix (with inheritance applied)
- [ ] `confirm` value for tools with `requires_confirmation=true`
- [ ] Tests: matrix matches expected output for demo agent config

### 27d — Seed demo agent tools + roles

Populate the reference agent (from 26d) with the Customer Support Copilot's
existing tools and roles.

**DoD:**
- [ ] Seed: 5 tools (searchKB, getOrderStatus, getCustomerProfile, issueRefund, getInternalSecrets)
- [ ] Seed: 3 roles (customer, support, admin) with inheritance
- [ ] Seed: permission matrix matches existing `rbac_config.yaml`
- [ ] Permission check against seeded data matches existing `check_permission()` results
