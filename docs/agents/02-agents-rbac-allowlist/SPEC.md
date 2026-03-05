# 02 — RBAC + Tool Allowlist (Tool-Level Permissions)

> **Priority:** 2
> **Depends on:** none (foundational)
> **Used by:** 01 (Pre-tool Gate), 10 (Data Boundary)
> **Sprint:** 1
> **Status:** ✅ Implemented — `300f109`

---

## 1. Goal

Constrain the agent's "agency" — ensure the agent cannot use tools that the user/role should not have access to. This is the most business-understandable control and provides real governance over what agents can do.

---

## 2. Current State

Today in `agent-demo/src/agent/tools/registry.py`:

```python
ROLE_TOOLS: dict[str, list[str]] = {
    "customer": ["searchKnowledgeBase", "getOrderStatus"],
    "admin": ["searchKnowledgeBase", "getOrderStatus", "getInternalSecrets"],
}
```

This is:
- Hardcoded in Python (no runtime config)
- Flat — no scopes, no sensitivity levels, no confirmation flags
- Only 2 roles, 3 tools
- No description/metadata for audit
- No CRUD API — changes require code deployment

---

## 3. Target Model

### 3.1. Role Definition

```python
class Role:
    name: str             # "customer", "support", "admin"
    description: str
    parent: str | None    # Inheritance: "support" inherits from "customer"
    is_active: bool
```

### 3.2. Tool Definition

```python
class ToolDefinition:
    name: str                 # "getOrderStatus"
    description: str          # Human-readable purpose
    category: str             # "data_read", "data_write", "admin", "external"
    sensitivity: str          # "low", "medium", "high", "critical"
    requires_confirmation: bool  # If True → pre-tool gate returns REQUIRE_CONFIRMATION
    args_schema: dict         # JSON Schema / Pydantic model reference (→ point 4)
    rate_limit: int | None    # Max calls per session for this tool (→ point 6)
```

### 3.3. Permission Entry

```python
class ToolPermission:
    role: str
    tool: str
    scopes: list[str]      # ["read"], ["read", "write"], ["execute"]
    conditions: dict | None # Optional: {"max_per_session": 5, "business_hours_only": True}
    is_active: bool
```

### 3.4. Permissions Map (example)

| Role | Tool | Scopes | Sensitivity | Requires Confirmation |
|------|------|--------|-------------|----------------------|
| `customer` | `searchKnowledgeBase` | `[read]` | low | no |
| `customer` | `getOrderStatus` | `[read]` | low | no |
| `support` | `searchKnowledgeBase` | `[read]` | low | no |
| `support` | `getOrderStatus` | `[read]` | low | no |
| `support` | `getCustomerProfile` | `[read]` | medium | no |
| `admin` | `*` (all tools) | `[read, write, execute]` | — | no |
| `admin` | `getInternalSecrets` | `[read]` | critical | **yes** |
| `admin` | `issueRefund` | `[write]` | high | **yes** |

---

## 4. How It Works

### 4.1. Permission Resolution

When the pre-tool gate (point 1) asks "can role X use tool Y?":

1. Look up explicit `ToolPermission` for `(role, tool)`.
2. If not found, check role's `parent` (inheritance chain).
3. If still not found → **DENY** (default-deny policy).
4. If found, check:
   - `is_active` must be `true`
   - required `scope` must be in permission's `scopes`
   - optional `conditions` must pass (e.g. business hours, session limits)
5. If the tool's `requires_confirmation` is `true` → return `REQUIRE_CONFIRMATION` instead of `ALLOW`.

### 4.2. Storage

Two options (decided at implementation):

**Option A: Config file (YAML/JSON)**
- Simple, version-controlled
- Good for demo / small deployments
- Loaded at startup, cached in memory

**Option B: Database + CRUD API**
- Dynamic, runtime-configurable
- Good for multi-tenant / enterprise
- Cached in Redis (like proxy policies)

**Recommendation:** start with Option A (YAML), add Option B later when we have the CRUD UI.

### 4.3. Integration Points

The RBAC service exposes these functions:

```python
def check_permission(role: str, tool: str, scope: str = "read") -> PermissionResult:
    """Check if role can use tool with given scope."""
    # Returns: PermissionResult(allowed=True/False, reason=..., requires_confirmation=...)

def get_allowed_tools(role: str) -> list[ToolDefinition]:
    """Return all tools accessible by role (for LLM system prompt)."""

def get_role_config(role: str) -> RoleConfig:
    """Return full role configuration (tools, scopes, limits)."""
```

These are called by:
- `pre_tool_gate` (point 1) — primary check
- `llm_call_node` — to build system prompt with available tools
- `tool_router_node` — to filter tool plans

---

## 5. Data Structures

### 5.1. PermissionResult

```python
class PermissionResult(TypedDict):
    allowed: bool
    reason: str | None             # "tool_not_in_allowlist", "scope_denied", "inactive_role"
    requires_confirmation: bool
    tool_sensitivity: str          # "low", "medium", "high", "critical"
    scopes_granted: list[str]
```

### 5.2. Config Schema (YAML)

```yaml
roles:
  customer:
    description: "End-user customer"
    tools:
      searchKnowledgeBase:
        scopes: [read]
        sensitivity: low
      getOrderStatus:
        scopes: [read]
        sensitivity: low

  support:
    description: "Support agent"
    inherits: customer
    tools:
      getCustomerProfile:
        scopes: [read]
        sensitivity: medium

  admin:
    description: "System administrator"
    inherits: support
    tools:
      getInternalSecrets:
        scopes: [read]
        sensitivity: critical
        requires_confirmation: true
      issueRefund:
        scopes: [write]
        sensitivity: high
        requires_confirmation: true
```

---

## 6. Implementation Steps

- [x] **6a.** Define `ToolDefinition`, `ToolPermission`, `PermissionResult` data structures
- [x] **6b.** Create RBAC config schema (YAML) with default roles and tools
- [x] **6c.** Create `src/agent/rbac/service.py` with `check_permission()`, `get_allowed_tools()`, `get_role_config()`
- [x] **6d.** Implement role inheritance resolution
- [x] **6e.** Implement scope checking logic
- [x] **6f.** Implement `requires_confirmation` flag handling
- [x] **6g.** Replace hardcoded `ROLE_TOOLS` dict in `registry.py` with RBAC service calls
- [x] **6h.** Update `policy_check_node` to use RBAC service
- [x] **6i.** Update `tool_router_node` to filter by RBAC permissions
- [x] **6j.** Add RBAC config file with default roles (customer, support, admin)
- [x] **6k.** Write tests: permission resolution, inheritance, scope checks, confirmation flag
- [x] **6l.** Write tests: unknown role → default deny, inactive permission → deny

---

## 7. Test Scenarios

| Scenario | Expected |
|----------|----------|
| `customer` + `getOrderStatus` + `read` | ALLOW |
| `customer` + `getInternalSecrets` + `read` | DENY (not in allowlist) |
| `support` + `getOrderStatus` + `read` | ALLOW (inherited from customer) |
| `support` + `getCustomerProfile` + `read` | ALLOW |
| `admin` + `getInternalSecrets` + `read` | ALLOW + REQUIRE_CONFIRMATION |
| `admin` + `issueRefund` + `write` | ALLOW + REQUIRE_CONFIRMATION |
| `unknown_role` + any tool | DENY (default deny) |
| `customer` + `getOrderStatus` + `write` | DENY (scope not granted) |

---

## 8. Definition of Done

- [x] RBAC service exists with `check_permission()`, `get_allowed_tools()`, `get_role_config()`
- [x] Role inheritance works (support inherits customer's tools)
- [x] Scopes are checked (read/write/execute)
- [x] `requires_confirmation` flag is returned correctly
- [x] Default-deny policy: unknown role/tool → DENY
- [x] Hardcoded `ROLE_TOOLS` replaced with RBAC service
- [x] Config loaded from YAML file
- [x] All test scenarios pass
