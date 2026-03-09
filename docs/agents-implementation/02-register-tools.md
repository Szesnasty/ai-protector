# Step 2 — Register Tools

**Time: 10 minutes**
**Input: your agent's tools**
**Output: tool registry with access control, sensitivity, and argument schemas**

---

## Why this step matters

Every tool your agent can call is an attack surface. Before writing any
security code, you need a complete inventory of what your agent can do.

This step produces a **tool registry** — a complete inventory of
what tools exist, who can use them, how they should be validated, and
what protection each one needs.

> **Source of truth:** The database is the source of truth for tool registrations inside AI Protector. The tool registry YAML in the integration kit is a deployment artifact derived from DB state.

---

## Tool inventory worksheet

For each tool your agent has, fill in:

| Field | Description | Example |
|-------|-------------|---------|
| **Name** | Function name the agent calls | `issueRefund` |
| **Description** | What it does in plain English | `Processes a refund for an order` |
| **Category** | Functional grouping | `orders`, `search`, `admin`, `comms` |
| **Access type** | `read` or `write` | `write` |
| **Sensitivity** | `low` / `medium` / `high` / `critical` | `high` |
| **Requires confirmation** | Should a human approve? | Yes |
| **Arguments** | What args it takes with types | `order_id: str, reason: str` |
| **Returns PII?** | Could the output contain personal data? | Yes |
| **Returns secrets?** | Could the output contain keys/tokens? | No |
| **Rate limit** | Max calls per session | 5 |

---

## Example: Customer Support Copilot

| Tool | Access | Sensitivity | Confirmation | Returns PII | Rate limit |
|------|--------|-------------|-------------|-------------|------------|
| `searchKnowledgeBase` | read | low | No | No | 20 |
| `getOrderStatus` | read | low | No | No | 20 |
| `getCustomerProfile` | read | medium | No | Yes | 10 |
| `issueRefund` | write | high | Yes | No | 5 |
| `getInternalSecrets` | read | critical | Yes | No | 3 |

---

## Smart defaults and recommendations

AI Protector provides opinionated recommendations based on your tool
definitions. You don't have to figure out the right settings — the
system tells you:

### Automatic rules

| If your tool... | AI Protector recommends... |
|-----------------|---------------------------|
| Has `access: write` | `requires_confirmation: true` |
| Has `sensitivity: high` or `critical` | Not available to `customer` role |
| Returns PII | Post-tool PII redaction enabled |
| Returns secrets | Post-tool secrets scanning enabled |
| Has string arguments | Argument validation + injection scan |
| Has no explicit rate limit | Default based on sensitivity (low=50, medium=20, high=5, critical=3) |

### Warnings

The system warns you when:

- A `write` tool is available to the `customer` role
- A `critical` tool doesn't require confirmation
- A tool has string arguments with no max length
- A tool returns PII but post-tool scanning is disabled
- A tool has no rate limit configured
- The total number of tools available to `customer` exceeds 5

---

## Argument schemas

For each tool with arguments, define a validation schema. This prevents:

- Injection via arguments (`order_id: "ignore all previous instructions"`)
- Type confusion (`amount: "infinity"`)
- Oversized payloads (`query: <100KB string>`)

### Schema definition format

```yaml
tools:
  getOrderStatus:
    args:
      order_id:
        type: string
        required: true
        pattern: "^ORD-\\d{3,6}$"
        min_length: 7
        max_length: 10
        description: "Order ID in format ORD-XXXXX"

  searchKnowledgeBase:
    args:
      query:
        type: string
        required: true
        min_length: 1
        max_length: 500
        description: "Search query"

  issueRefund:
    args:
      order_id:
        type: string
        required: true
        pattern: "^ORD-\\d{3,6}$"
        min_length: 7
        max_length: 10
      reason:
        type: string
        required: false
        max_length: 500
        description: "Reason for refund"

  getInternalSecrets:
    args: {}  # No arguments — extra fields rejected
```

### What happens to invalid arguments

| Validation result | Decision | What happens |
|-------------------|----------|-------------|
| All args valid, no injection | **ALLOW** | Tool executes normally |
| Args valid but sanitized (whitespace, unicode) | **MODIFY** | Tool executes with cleaned args |
| Pydantic validation fails (wrong type, bad format) | **BLOCK** | Tool not called, error returned |
| Injection pattern detected in args | **BLOCK** | Tool not called, threat logged |

### Built-in injection patterns scanned

Every string argument is automatically scanned for these patterns:

```
ignore (previous|all|your) (instructions|rules|constraints)
you are now
act as (if|a|an)
pretend to be
reveal (your|the) (system|secret|prompt)
(system|assistant):
[INST]
<|im_start|>
forget (everything|what)
new instructions:
disregard (all)? (prior|previous|above)
override (all)? rules
do anything now
jailbreak
<<SYS>>
```

You don't configure these — they run automatically on every tool call.

---

## Generated output: tools.yaml

After completing this step, AI Protector generates:

```yaml
# tools.yaml — generated by AI Protector
# Agent: Customer Support Copilot
# Generated: 2026-03-09

tools:
  searchKnowledgeBase:
    description: "Search FAQ and knowledge base articles"
    category: search
    access: read
    sensitivity: low
    requires_confirmation: false
    rate_limit: 20
    returns_pii: false
    returns_secrets: false
    args:
      query:
        type: string
        required: true
        min_length: 1
        max_length: 500

  getOrderStatus:
    description: "Look up order status by order ID"
    category: orders
    access: read
    sensitivity: low
    requires_confirmation: false
    rate_limit: 20
    returns_pii: false
    returns_secrets: false
    args:
      order_id:
        type: string
        required: true
        pattern: "^ORD-\\d{3,6}$"
        min_length: 7
        max_length: 10

  getCustomerProfile:
    description: "Retrieve customer profile by ID"
    category: customers
    access: read
    sensitivity: medium
    requires_confirmation: false
    rate_limit: 10
    returns_pii: true        # ← triggers post-tool PII scanning
    returns_secrets: false
    args:
      customer_id:
        type: string
        required: true
        max_length: 50

  issueRefund:
    description: "Process a refund for an order"
    category: orders
    access: write            # ← auto-recommends confirmation
    sensitivity: high
    requires_confirmation: true
    rate_limit: 5
    returns_pii: false
    returns_secrets: false
    args:
      order_id:
        type: string
        required: true
        pattern: "^ORD-\\d{3,6}$"
      reason:
        type: string
        required: false
        max_length: 500

  getInternalSecrets:
    description: "Retrieve internal API keys and configuration"
    category: admin
    access: read
    sensitivity: critical    # ← auto-excludes from customer role
    requires_confirmation: true
    rate_limit: 3
    returns_pii: false
    returns_secrets: true    # ← triggers post-tool secrets scanning
    args: {}
```

---

## UI implementation plan

### Screen: "Register Tools"

**Route:** `/agents/:id/tools`

**Layout:**

```
┌───────────────────────────────────────────────────────────┐
│          What can your agent do?                          │
│                                                           │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  searchKnowledgeBase                                │  │
│  │  Search FAQ and knowledge base articles             │  │
│  │  read · low · no confirm · 20/session               │  │
│  │  Args: query (string, max 500)                      │  │
│  │                                        [Edit] [×]   │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                           │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  issueRefund                              ⚠ write   │  │
│  │  Process a refund for an order                      │  │
│  │  write · high · ⚠ requires confirm · 5/session      │  │
│  │  Args: order_id (string, ORD-XXX), reason (string)  │  │
│  │                                        [Edit] [×]   │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                           │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  ⚠ Recommendations:                                │  │
│  │  • issueRefund is write → confirmation enabled ✓    │  │
│  │  • getInternalSecrets is critical → excluded from   │  │
│  │    customer role ✓                                  │  │
│  │  • getCustomerProfile returns PII → post-tool       │  │
│  │    redaction enabled ✓                              │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                           │
│       [ + Add Tool ]        [ Continue → Map Roles ]      │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

### Auto-import from OpenAI function schema

If your agent already uses OpenAI function calling format, AI Protector
can import tools directly:

```json
{
  "type": "function",
  "function": {
    "name": "getOrderStatus",
    "description": "Look up order status",
    "parameters": {
      "type": "object",
      "properties": {
        "order_id": { "type": "string", "pattern": "^ORD-\\d{3,6}$" }
      },
      "required": ["order_id"]
    }
  }
}
```

**Import flow:**
1. Paste your OpenAI tools JSON
2. AI Protector auto-fills name, description, args
3. You add security metadata: access, sensitivity, PII, rate limit
4. Done

This eliminates duplicate work — your existing tool definitions become
the starting point.

---

## Next step

Take your tool registry and go to:

→ **Step 3** — [Generate RBAC](03-generate-rbac.md)
