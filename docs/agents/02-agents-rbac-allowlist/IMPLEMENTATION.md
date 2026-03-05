# 02 — RBAC + Tool Allowlist: Implementation Notes

> **Branch:** `feat/agents-mode`
> **Commit:** `300f109`
> **Date:** 2026-03-05

---

## 1. What Changed

### Before (Spec 01 baseline)

Tool permissions were hardcoded in `registry.py`:

```python
ROLE_TOOLS = {
    "customer": ["searchKnowledgeBase", "getOrderStatus"],
    "admin":    ["searchKnowledgeBase", "getOrderStatus", "getInternalSecrets"],
}
```

- Only 2 roles, no inheritance
- No scopes, sensitivity levels, or confirmation flags
- `pre_tool_gate._check_rbac()` compared tool names against a flat list
- `pre_tool_gate._check_confirmation()` used a hardcoded `TOOLS_REQUIRING_CONFIRMATION` set (empty)
- Admin could access secrets without any confirmation gate

### After (Spec 02)

A dedicated RBAC module with YAML-driven configuration, role inheritance, scope checks, and sensitivity-based confirmation:

```
src/agent/rbac/
├── __init__.py
├── models.py         # Frozen dataclasses: ToolDefinition, ToolPermission, RoleConfig, PermissionResult
├── service.py        # RBACService class + singleton accessor
└── rbac_config.yaml  # Declarative role/tool configuration
```

---

## 2. Architecture

### 2.1. Data Models (`models.py`)

Four frozen dataclasses:

| Model | Purpose | Key Fields |
|-------|---------|------------|
| `ToolDefinition` | Tool metadata | `name`, `sensitivity` (low/medium/high/critical), `requires_confirmation`, `rate_limit` |
| `ToolPermission` | Single role→tool grant | `role`, `tool`, `scopes` (tuple of strings), `is_active` |
| `RoleConfig` | Role metadata | `name`, `description`, `inherits` (parent role name or None), `is_active` |
| `PermissionResult` | Check outcome | `allowed`, `reason`, `requires_confirmation`, `tool_sensitivity`, `scopes_granted` |

All are `frozen=True` for immutability and safe use as dict keys / in sets.

### 2.2. RBAC Service (`service.py`)

Singleton service loaded at first access:

```
get_rbac_service() → RBACService (singleton)
reset_rbac_service() → clears singleton (for tests)
```

**Initialization:**
1. Reads `rbac_config.yaml` (or custom path)
2. Builds internal maps: `_roles`, `_permissions` (keyed by `(role, tool)` tuple), `_tool_defs`
3. Logs loaded config summary via structlog

**Core API:**

| Method | Signature | Returns |
|--------|-----------|---------|
| `check_permission` | `(role, tool, scope="read")` | `PermissionResult` |
| `get_allowed_tools` | `(role)` | `list[str]` |
| `get_role_config` | `(role)` | `RoleConfig \| None` |
| `get_tool_definition` | `(tool)` | `ToolDefinition \| None` |

### 2.3. Permission Resolution Algorithm

`check_permission(role, tool, scope)`:

```
1. Build inheritance chain: [role, parent, grandparent, ...]
   └─ Cycle detection via visited set
2. If chain is empty → DENY ("Unknown role")
3. Walk chain looking for (ancestor, tool) in permissions map
   └─ First match wins (most-specific role takes priority)
4. If no match found → DENY ("Tool not in allowlist") — default-deny
5. If match found but is_active=false → DENY ("Permission inactive")
6. If scope not in permission.scopes → DENY ("Scope not granted")
7. Look up ToolDefinition for sensitivity + requires_confirmation
8. Return PermissionResult(allowed=True, requires_confirmation=..., ...)
```

### 2.4. Inheritance Resolution

`_resolve_inheritance_chain(role)`:

```
customer  →  [customer]
support   →  [support, customer]
admin     →  [admin, support, customer]
```

- Walks the `inherits` pointer from child to root
- Stops if role not found (unknown parent) or cycle detected
- `get_allowed_tools()` reverses the chain (ancestor→child) to collect tools, so direct permissions override inherited ones

### 2.5. YAML Configuration (`rbac_config.yaml`)

```yaml
roles:
  customer:               # Base role — no parent
    tools:
      searchKnowledgeBase: { scopes: [read], sensitivity: low }
      getOrderStatus:      { scopes: [read], sensitivity: low }

  support:                # Inherits customer's 2 tools
    inherits: customer
    tools:
      getCustomerProfile:  { scopes: [read], sensitivity: medium }

  admin:                  # Inherits support (→ customer) + 2 sensitive tools
    inherits: support
    tools:
      getInternalSecrets:  { scopes: [read], sensitivity: critical, requires_confirmation: true }
      issueRefund:         { scopes: [write], sensitivity: high, requires_confirmation: true }
```

**Effective tool access:**

| Role | Tools | Via |
|------|-------|-----|
| `customer` | searchKnowledgeBase, getOrderStatus | direct |
| `support` | searchKnowledgeBase, getOrderStatus, getCustomerProfile | inherited + direct |
| `admin` | searchKnowledgeBase, getOrderStatus, getCustomerProfile, getInternalSecrets, issueRefund | inherited + direct |

---

## 3. Integration Points

### 3.1. `registry.py` — Tool Dispatch

**Before:** `ROLE_TOOLS` dict + `get_allowed_tools()` did dict lookup.

**After:** `ROLE_TOOLS` removed entirely. `get_allowed_tools()` delegates to `get_rbac_service().get_allowed_tools(role)`.

`TOOL_FUNCTIONS` and `TOOL_DESCRIPTIONS` remain unchanged — they map tool names to callables and descriptions, independent of permissions.

### 3.2. `pre_tool_gate.py` — Security Gate

Two checks updated:

**`_check_rbac(tool_name, allowed_tools, user_role="")`**
- Now calls `get_rbac_service().check_permission(user_role, tool_name, scope="read")`
- Returns structured `PermissionResult` instead of flat list membership check
- `allowed_tools` parameter kept for signature compatibility but not used

**`_check_confirmation(tool_name, user_role="")`**
- Now calls `get_rbac_service().check_permission(user_role, tool_name)`
- If `result.requires_confirmation` is True → returns failed CheckResult
- Falls back to legacy `TOOLS_REQUIRING_CONFIRMATION` set (now empty) for backward compat

**`_evaluate_tool()`**
- Passes `user_role` from state to both `_check_rbac` and `_check_confirmation`

### 3.3. Graph Flow Impact

The LangGraph remains unchanged structurally. The behavioral change:

```
BEFORE:  admin + getInternalSecrets → ALLOW → tool_executor → llm_call → END
AFTER:   admin + getInternalSecrets → REQUIRE_CONFIRMATION → confirmation_response → memory → END
```

The confirmation gate now fires for any tool with `requires_confirmation: true` in YAML, based on the role's resolved permissions.

---

## 4. Test Coverage

### New: `test_rbac.py` — 27 tests

| Test Class | Count | Coverage |
|------------|-------|----------|
| `TestDefaultConfig` | 5 | Customer/support/admin tool lists, unknown role, tool count |
| `TestCheckPermission` | 9 | Read/write scopes, confirmation flags, inheritance, unknown role/tool |
| `TestRoleConfig` | 4 | Inheritance chain, unknown roles |
| `TestInheritanceChain` | 6 | Custom 3-level hierarchy (viewer→editor→superadmin), deep inheritance, confirmation inheritance |
| `TestToolDefinition` | 2 | Known/unknown tool lookup |
| `TestSingleton` | 2 | Singleton instance reuse + reset |

The `TestInheritanceChain` tests create a custom YAML config at runtime to verify multi-level inheritance without depending on the default config.

### Updated: Existing Tests

| File | Changes |
|------|---------|
| `test_pre_tool_gate.py` | `_check_rbac` calls now include `user_role=`; confirmation test uses RBAC-driven admin+secrets; admin access test split into non-sensitive (ALLOW) + secrets (REQUIRE_CONFIRMATION) |
| `test_graph.py` | `test_admin_can_access_secrets` → `test_admin_secrets_requires_confirmation` — expects confirmation response, not tool execution |
| `test_integration.py` | `TestScenario4AdminSecrets` → expects REQUIRE_CONFIRMATION, no tool execution, confirmation message in response |

### Final Suite: 122 tests, all passing

---

## 5. Key Design Decisions

1. **YAML over database** — Spec recommends starting with Option A (config file). Simple, version-controlled, no migration needed. Database storage (Option B) deferred to future sprint.

2. **Frozen dataclasses** — All models are immutable (`frozen=True`). Safe for concurrent access, prevents accidental mutation of permission state.

3. **Singleton pattern** — `get_rbac_service()` returns a module-level singleton. `reset_rbac_service()` allows test isolation. Config loaded once at startup.

4. **Default-deny** — Any (role, tool) pair not explicitly granted is denied. Unknown roles are denied. This is the most secure default.

5. **Scope as string** — Scopes are simple strings (`"read"`, `"write"`, `"execute"`). No enum to allow extensibility without code changes.

6. **Legacy fallback** — `TOOLS_REQUIRING_CONFIRMATION` set kept (empty) for backward compatibility. Real confirmation logic is RBAC-driven.

7. **`requires_confirmation` on ToolDefinition, not ToolPermission** — Confirmation is a property of the tool's sensitivity, not who's asking. All roles with access to a confirmation-required tool will be asked to confirm.

---

## 6. Files Changed

| File | Action | Lines |
|------|--------|-------|
| `src/agent/rbac/__init__.py` | **Created** | 0 (empty package) |
| `src/agent/rbac/models.py` | **Created** | 50 |
| `src/agent/rbac/service.py` | **Created** | 221 |
| `src/agent/rbac/rbac_config.yaml` | **Created** | 42 |
| `src/agent/tools/registry.py` | **Modified** | 60 (removed ROLE_TOOLS, added RBAC delegation) |
| `src/agent/nodes/pre_tool_gate.py` | **Modified** | 388 (RBAC calls in _check_rbac + _check_confirmation) |
| `tests/test_rbac.py` | **Created** | 310 |
| `tests/test_pre_tool_gate.py` | **Modified** | Updated for RBAC signatures |
| `tests/test_graph.py` | **Modified** | Admin secrets test → confirmation |
| `tests/test_integration.py` | **Modified** | Admin secrets scenario → confirmation |

**Total: 11 files changed, +785 / -58 lines**
