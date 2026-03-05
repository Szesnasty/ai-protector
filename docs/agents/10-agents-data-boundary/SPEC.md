# 10 — Data Boundary: Role-Dependent Disclosure Rules

> **Priority:** 10
> **Depends on:** 02-RBAC (role definitions), 03-Post-tool Gate (enforcement point)
> **Consumed by:** output filter, agent trace
>
> **Architectural note:** This spec is a **policy configuration layer**, not a new graph node.
> It defines *what* data each role can see. The *enforcement* happens inside the post-tool gate
> (spec 03, scanner step #5) and optionally in the proxy output filter. This spec owns:
> - `DisclosurePolicy` / `DisclosureRule` data models,
> - masking strategies per entity type,
> - YAML/DB configuration,
> - audit trail for disclosure events.
>
> The post-tool gate (spec 03) calls `apply_disclosure(tool_result, role)` from this module.
> Without spec 10 implemented, the post-tool gate redacts all detected PII uniformly.
> With spec 10, redaction becomes role-aware (admin sees full data, customer sees masked).

---

## 1. Goal

Control "what the agent can reveal" depending on who the user is, even if the data is available in the tool. This is information-level governance — the last line of defense.

**Example:** `getOrderStatus` returns the customer's full name, email, phone, and address. A `customer` role should see only their own data with some fields masked. A `support` role should see partial data. An `admin` sees everything (with audit trail).

**This is different from RBAC:** RBAC controls _which tools_ you can call. Data Boundary controls _what data you see_ from the tools you're already allowed to call.

---

## 2. How It Works

### 2.1. Disclosure Policy

A set of rules defining what data fields/entity types can be revealed per role:

```yaml
disclosure_policies:
  customer:
    description: "End users see only their own data, PII masked"
    rules:
      - entity: EMAIL_ADDRESS
        action: mask          # john@acme.com → j***@acme.com
      - entity: PHONE_NUMBER
        action: mask          # +1-555-123-4567 → +1-555-***-****
      - entity: CREDIT_CARD
        action: hide          # Completely removed
      - entity: US_SSN
        action: hide
      - entity: PERSON
        action: allow         # Names are OK for customers
      - entity: IP_ADDRESS
        action: hide
      - field: "internal_notes"
        action: hide          # Field-level rule
      - field: "api_key"
        action: hide

  support:
    description: "Support agents see partial PII for assistance"
    rules:
      - entity: EMAIL_ADDRESS
        action: allow         # Full email visible
      - entity: PHONE_NUMBER
        action: mask          # Partially masked
      - entity: CREDIT_CARD
        action: mask          # Last 4 digits only
      - entity: US_SSN
        action: hide
      - entity: PERSON
        action: allow
      - field: "internal_notes"
        action: allow
      - field: "api_key"
        action: hide

  admin:
    description: "Full access with audit trail"
    rules:
      - entity: "*"
        action: allow         # Everything visible
      - field: "*"
        action: allow
    audit: true                # Log every disclosure
```

### 2.2. Action Types

| Action | Effect | Example |
|--------|--------|---------|
| `allow` | Data passes through unchanged | `john@acme.com` → `john@acme.com` |
| `mask` | Partially redacted (entity-type-specific) | `john@acme.com` → `j***@a***.com` |
| `hide` | Completely removed / replaced | `john@acme.com` → `[REDACTED]` |
| `hash` | One-way hashed (for correlation without exposure) | `john@acme.com` → `[USER#a3f2]` |

### 2.3. Enforcement Points

Data Boundary rules are enforced inside **existing nodes** — no new graph node is added:

```
Tool Output ──► Post-tool Gate (spec 03, step #5) ──► LLM ──► Output Filter ──► User
                     │                                            │
              Disclosure rules                             Disclosure rules
              applied HERE                                 applied HERE
              (before LLM sees)                            (before user sees)
              PRIMARY enforcement                          SECONDARY catch-all
```

**Post-tool gate (primary):** the `apply_disclosure()` function from this module is called
as step #5 in the post-tool gate. It replaces the generic PII redaction with role-specific
masking. This is preferred because:
- LLM never sees the sensitive data → cannot hallucinate or repeat it.
- Reduces context window usage.

**Output filter (secondary):** catches anything the LLM might generate that bypasses
tool data masking (e.g. LLM hallucinates a phone number pattern).

---

## 3. Data Model

### 3.1. DisclosureRule

```python
class DisclosureRule(BaseModel):
    """A single disclosure rule for an entity type or field."""
    entity: str | None = None        # Presidio entity type (e.g. "EMAIL_ADDRESS") or "*"
    field: str | None = None         # Field name in structured tool output (e.g. "api_key")
    action: Literal["allow", "mask", "hide", "hash"]
    mask_format: str | None = None   # Custom mask format (e.g. "{first}***@{domain}")
```

### 3.2. DisclosurePolicy

```python
class DisclosurePolicy(BaseModel):
    """Disclosure policy for a specific role."""
    role: str
    description: str
    rules: list[DisclosureRule]
    audit: bool = False              # Log every disclosure decision
    default_action: Literal["allow", "mask", "hide"] = "hide"  # For unlisted entities/fields
```

### 3.3. DisclosureResult

```python
class DisclosureResult(TypedDict):
    """Result of applying disclosure rules to a piece of data."""
    original_length: int
    sanitized_length: int
    entities_masked: list[str]       # ["EMAIL_ADDRESS", "PHONE_NUMBER"]
    entities_hidden: list[str]       # ["CREDIT_CARD", "US_SSN"]
    fields_hidden: list[str]         # ["api_key"]
    modifications_count: int
```

---

## 4. Masking Strategies

### 4.1. Entity-Specific Masks

| Entity | Mask Strategy | Example |
|--------|--------------|---------|
| `EMAIL_ADDRESS` | Keep first char + domain hint | `j***@a***.com` |
| `PHONE_NUMBER` | Keep country code + last 2 digits | `+1-***-***-**67` |
| `CREDIT_CARD` | Last 4 digits | `****-****-****-4242` |
| `US_SSN` | Completely hidden | `[REDACTED]` |
| `PERSON` | First name only | `John D.` |
| `IP_ADDRESS` | Completely hidden | `[IP_REDACTED]` |
| `URL` | Domain only | `https://***example.com***/...` |

### 4.2. Field-Level Masking

For structured tool outputs (JSON), specific fields can be targeted:

```python
def apply_field_rules(data: dict, rules: list[DisclosureRule]) -> dict:
    """Apply field-level disclosure rules to structured data."""
    result = {}
    for key, value in data.items():
        rule = find_matching_field_rule(key, rules)
        if rule and rule.action == "hide":
            continue  # Skip this field entirely
        elif rule and rule.action == "mask":
            result[key] = mask_value(value, rule)
        else:
            result[key] = value
    return result
```

---

## 5. Integration with Post-tool Gate

The disclosure filter runs as step #4 in the post-tool gate (see 03-SPEC):

```python
# In post_tool_gate_node
def apply_disclosure(tool_result: str, role: str) -> tuple[str, DisclosureResult]:
    """Apply disclosure policy to a tool result."""
    policy = get_disclosure_policy(role)

    # Entity-level: use Presidio to find entities, then mask/hide per rules
    entities = presidio_analyze(tool_result)
    sanitized = tool_result
    for entity in entities:
        rule = find_matching_entity_rule(entity.entity_type, policy.rules)
        action = rule.action if rule else policy.default_action
        if action == "hide":
            sanitized = replace_entity(sanitized, entity, "[REDACTED]")
        elif action == "mask":
            sanitized = replace_entity(sanitized, entity, mask_entity(entity))
        elif action == "hash":
            sanitized = replace_entity(sanitized, entity, hash_entity(entity))
        # "allow" → no change

    return sanitized, disclosure_result
```

---

## 6. Integration with Output Filter

The proxy-service's `OutputFilterNode` also applies disclosure rules to the final LLM response:

```python
# In output_filter_node (proxy-service pipeline)
# If x-user-role header is present, apply disclosure rules
user_role = state.get("client_metadata", {}).get("user_role")
if user_role:
    response_text = apply_disclosure(response_text, user_role)
```

---

## 7. Configuration

### 7.1. Policy Storage

**Option A — YAML config** (start here):
```
src/agent/config/disclosure_policies.yaml
```

**Option B — Database** (future):
```sql
CREATE TABLE disclosure_policies (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role        VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    rules       JSONB NOT NULL,
    audit       BOOLEAN DEFAULT false,
    default_action VARCHAR(10) DEFAULT 'hide',
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);
```

### 7.2. API (optional, for UI management)

```
GET    /agent/disclosure-policies               → list all policies
GET    /agent/disclosure-policies/{role}         → policy detail
PUT    /agent/disclosure-policies/{role}         → update policy rules
```

---

## 8. Audit Trail

When `audit: true` is set for a role (e.g. admin), every data disclosure is logged:

```json
{
  "event": "data_disclosure",
  "session_id": "sess-123",
  "user_role": "admin",
  "tool": "getOrderStatus",
  "entities_disclosed": ["EMAIL_ADDRESS", "PHONE_NUMBER", "PERSON"],
  "fields_disclosed": ["order_total", "shipping_address"],
  "action": "allow",
  "timestamp": "2026-03-05T14:30:00Z"
}
```

This creates an audit trail for compliance: "Admin user viewed full PII at 14:30 via getOrderStatus tool".

---

## 9. Definition of Done

- [ ] `DisclosureRule`, `DisclosurePolicy`, `DisclosureResult` data models
- [ ] Disclosure policies for customer, support, admin roles (YAML)
- [ ] `apply_disclosure()` function with entity-level and field-level masking
- [ ] Entity-specific mask strategies (email, phone, CC, SSN, etc.)
- [ ] Integration with post-tool gate (step #4 in 03-SPEC)
- [ ] Integration with proxy output filter (secondary enforcement)
- [ ] `default_action` for unlisted entities/fields
- [ ] Audit logging when `audit: true`
- [ ] Structured logging for every disclosure decision
- [ ] Unit tests: mask/hide/allow/hash for each entity type
- [ ] Unit tests: field-level rules on structured data
- [ ] Integration test: customer calls tool → PII masked in response
- [ ] Integration test: admin calls same tool → full data visible + audit log
- [ ] Integration test: support sees partial data
