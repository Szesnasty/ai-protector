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

---

## Test plan

Minimum **52 tests** across 4 sub-steps. Tests in `tests/agents/test_tools_roles.py`.

### 27a tests — Tool CRUD (18 tests)

| # | Test | Assert |
|---|------|--------|
| 1 | `test_create_tool` | POST → 201, tool has id + agent_id |
| 2 | `test_create_tool_missing_name` | POST without name → 422 |
| 3 | `test_create_tool_duplicate_name` | Same tool name on same agent → 409 |
| 4 | `test_create_tool_same_name_diff_agent` | Same tool name on different agent → 201 (allowed) |
| 5 | `test_create_tool_smart_default_confirmation` | write + high → requires_confirmation=true auto-set |
| 6 | `test_create_tool_smart_default_no_confirmation` | read + low → requires_confirmation=false |
| 7 | `test_create_tool_smart_default_rate_limit_low` | sensitivity=low → rate_limit defaults to 20 |
| 8 | `test_create_tool_smart_default_rate_limit_critical` | sensitivity=critical → rate_limit defaults to 3 |
| 9 | `test_create_tool_with_arg_schema` | Valid JSON Schema in arg_schema → accepted |
| 10 | `test_create_tool_invalid_arg_schema` | Invalid JSON Schema → 422 |
| 11 | `test_list_tools_empty` | GET /agents/:id/tools on new agent → [] |
| 12 | `test_list_tools_returns_all` | Create 5 tools, GET → 5 items |
| 13 | `test_list_tools_scoped_to_agent` | Tools from agent A not visible in agent B |
| 14 | `test_patch_tool` | PATCH name → updated, smart defaults re-evaluated |
| 15 | `test_patch_tool_recomputes_confirmation` | PATCH sensitivity=critical → requires_confirmation flips to true |
| 16 | `test_delete_tool` | DELETE → 204, not in list anymore |
| 17 | `test_delete_tool_not_found` | DELETE nonexistent → 404 |
| 18 | `test_delete_tool_cascades_permissions` | Delete tool → role_tool_permissions for this tool also gone |

### 27b tests — Role CRUD + Inheritance (20 tests)

| # | Test | Assert |
|---|------|--------|
| 19 | `test_create_role` | POST → 201, role has id + agent_id |
| 20 | `test_create_role_missing_name` | POST without name → 422 |
| 21 | `test_create_role_duplicate_name` | Same role name on same agent → 409 |
| 22 | `test_create_role_with_inheritance` | POST inherits_from=parent_id → 201 |
| 23 | `test_create_role_circular_inheritance` | Role A inherits B, B inherits A → 422 |
| 24 | `test_create_role_deep_circular` | A→B→C→A chain → 422 |
| 25 | `test_list_roles` | GET → all roles with resolved permissions |
| 26 | `test_list_roles_scoped_to_agent` | Roles from agent A not in agent B |
| 27 | `test_patch_role` | PATCH name → updated |
| 28 | `test_delete_role` | DELETE → 204, cascade permissions deleted |
| 29 | `test_delete_role_with_children` | DELETE parent role → children's inherits_from set to null (or error) |
| 30 | `test_set_permissions_batch` | PUT permissions → all tool->role links created |
| 31 | `test_set_permissions_overwrites` | PUT twice → second call replaces first |
| 32 | `test_set_permissions_invalid_tool` | Permission for nonexistent tool → 422 |
| 33 | `test_inheritance_two_levels` | customer→support→admin, admin has all tools |
| 34 | `test_inheritance_child_override` | Child overrides parent scope for same tool |
| 35 | `test_default_deny` | Tool not in permission set → check returns DENY |
| 36 | `test_check_permission_allow` | /agents/:id/check-permission?role=admin&tool=issueRefund → ALLOW |
| 37 | `test_check_permission_deny` | /agents/:id/check-permission?role=customer&tool=issueRefund → DENY |
| 38 | `test_check_permission_inherited` | support inherits customer tools → customer tools return ALLOW |

### 27c tests — Permission matrix (8 tests)

| # | Test | Assert |
|---|------|--------|
| 39 | `test_matrix_empty` | No roles/tools → empty matrix |
| 40 | `test_matrix_structure` | Has tools[], roles[], matrix{} keys |
| 41 | `test_matrix_all_deny` | Role with no permissions → all "deny" |
| 42 | `test_matrix_with_confirmation` | Tool requires_confirmation → "confirm" in matrix |
| 43 | `test_matrix_inheritance_resolved` | Inherited permissions show as "allow", not missing |
| 44 | `test_matrix_matches_individual_checks` | Every cell in matrix matches individual check-permission call |
| 45 | `test_matrix_after_tool_delete` | Delete tool → matrix no longer includes it |
| 46 | `test_matrix_after_role_delete` | Delete role → matrix no longer includes it |

### 27d tests — Seed (6 tests)

| # | Test | Assert |
|---|------|--------|
| 47 | `test_seed_creates_5_tools` | Reference agent has exactly 5 tools |
| 48 | `test_seed_creates_3_roles` | Reference agent has exactly 3 roles |
| 49 | `test_seed_inheritance_chain` | customer→support→admin chain correct |
| 50 | `test_seed_matrix_matches_existing_config` | Permission matrix == existing rbac_config.yaml permissions |
| 51 | `test_seed_idempotent` | Run seed twice → still 5 tools, 3 roles |
| 52 | `test_seed_check_permission_matches_legacy` | check_permission for all combos matches existing RBACService |
