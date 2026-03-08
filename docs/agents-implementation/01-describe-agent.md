# Step 1 — Describe Your Agent

**Time: 5 minutes**
**Output: risk profile + recommended protection level**

---

## Why this step matters

Before configuring anything, AI Protector needs to understand what your
agent does. The answers here determine:

- Which protection level you need (proxy / runtime / full)
- Which policy pack fits best
- Which attack test categories apply
- What defaults are sensible for limits, PII, and confirmation

You won't configure security from scratch. You'll describe your agent
and get an opinionated recommendation.

---

## Agent questionnaire

Answer these questions about your agent:

### 1. Identity

| Field | Your answer | Example |
|-------|-------------|---------|
| **Agent name** | | `Customer Support Copilot` |
| **Team / owner** | | `Platform team` |
| **Description** | | `Answers customer questions, checks order status, processes refunds` |

### 2. Exposure

| Question | Options | Impact |
|----------|---------|--------|
| **Who uses it?** | Internal employees / External customers / Both | External = stricter defaults |
| **Environment** | Dev / Staging / Production | Production = stricter rollout |
| **Multi-tenant?** | Yes / No | Yes = role isolation required |

### 3. Capabilities

| Question | Options | Impact |
|----------|---------|--------|
| **Uses tools?** | Yes / No | Yes = needs pre/post-tool gates |
| **Has write actions?** | Yes / No | Yes = needs confirmation flows |
| **Accesses databases?** | Yes / No | Yes = needs argument validation |
| **Sends emails/messages?** | Yes / No | Yes = needs output filtering |
| **Touches PII?** | Yes / No | Yes = needs PII redaction |
| **Handles secrets/keys?** | Yes / No | Yes = needs secrets scanning |
| **Calls external APIs?** | Yes / No | Yes = needs data boundary checks |

### 4. Framework

| Option | What changes |
|--------|-------------|
| **LangGraph** | Get ready-made graph nodes |
| **CrewAI** | Get middleware hooks |
| **AutoGen** | Get event handler pattern |
| **Raw Python** | Get function wrappers |
| **Proxy-only** | No agent code — firewall only |

---

## Risk classification

Based on your answers, AI Protector classifies your agent:

### Low risk

- Internal use only
- Read-only tools
- No PII, no secrets
- No external API calls

**Recommended:** Proxy only + basic RBAC
**Policy pack:** Read-only Research Agent

### Medium risk

- Customer-facing OR internal with write actions
- 2–5 tools, some with write access
- May touch PII indirectly
- No direct database writes

**Recommended:** Agent runtime (pre + post gates)
**Policy pack:** Customer Support Agent or Internal Copilot

### High risk

- Customer-facing with write actions
- Touches PII, secrets, or financial data
- Calls external APIs
- Database writes or admin actions available

**Recommended:** Full protection (proxy + runtime + tracing + budgets)
**Policy pack:** Finance Agent or custom

### Critical risk

- Multi-tenant with mixed roles
- Admin actions available
- Handles payment or healthcare data
- Compliance requirements (SOC 2, HIPAA, GDPR)

**Recommended:** Full protection + strict rollout + audit trace
**Policy pack:** Custom with enhanced limits

---

## Example: Customer Support Copilot

```
Agent name:        Customer Support Copilot
Team:              Platform
Description:       Answers FAQs, checks order status, processes refunds
Who uses it:       External customers
Environment:       Production
Uses tools:        Yes (5 tools)
Has write actions:  Yes (issueRefund)
Touches PII:       Yes (customer profiles)
Framework:         LangGraph
```

**Result:**

```
Risk classification:  HIGH
Recommended level:    Full Protection
Recommended pack:     Customer Support Agent
Key requirements:
  - RBAC with 3 roles (customer, support, admin)
  - Pre-tool gate with argument validation
  - Post-tool gate with PII redaction
  - Confirmation flow for issueRefund
  - Session budgets ($0.50 customer / $1.00 support / $5.00 admin)
  - Full trace to Langfuse
```

---

## What happens next

Take your risk classification and go to:

- **Step 2** → [Register your tools](02-register-tools.md)
- Or if proxy-only → skip to **Step 5** → [Generate Integration Kit](05-integration-kit.md)

---

## UI implementation plan

### Screen: "Protect New Agent"

**Route:** `/agents/new`

**Layout:**

```
┌───────────────────────────────────────────────────┐
│                Protect New Agent                  │
│                                                   │
│  Agent name:     [________________________]       │
│  Team:           [________________________]       │
│  Description:    [________________________]       │
│                                                   │
│  ─── Exposure ─────────────────────────────────   │
│                                                   │
│  Who uses it?   ○ Internal  ● External  ○ Both    │
│  Environment:   ○ Dev  ○ Staging  ● Production    │
│  Multi-tenant?  ○ Yes  ● No                       │
│                                                   │
│  ─── Capabilities ─────────────────────────────   │
│                                                   │
│  Uses tools?          ● Yes  ○ No                 │
│  Has write actions?   ● Yes  ○ No                 │
│  Touches PII?         ● Yes  ○ No                 │
│  Handles secrets?     ○ Yes  ● No                 │
│  Sends emails?        ○ Yes  ● No                 │
│                                                   │
│  Framework:  ● LangGraph  ○ CrewAI  ○ Raw Python  │
│                                                   │
│  ─── Recommendation ───────────────────────────   │
│                                                   │
│  ┌─────────────────────────────────────────────┐  │
│  │  Risk: HIGH                                 │  │
│  │  Recommended: Full Protection               │  │
│  │  Policy pack: Customer Support Agent        │  │
│  │                                             │  │
│  │  Includes:                                  │  │
│  │  ✓ RBAC with role inheritance               │  │
│  │  ✓ Pre-tool gate (5 checks)                 │  │
│  │  ✓ Post-tool gate (PII + secrets)           │  │
│  │  ✓ Confirmation for write actions           │  │
│  │  ✓ Session budgets                          │  │
│  │  ✓ Full observability trace                 │  │
│  └─────────────────────────────────────────────┘  │
│                                                   │
│           [ Continue → Register Tools ]           │
│                                                   │
└───────────────────────────────────────────────────┘
```

### API endpoint

```
POST /api/agents
{
  "name": "Customer Support Copilot",
  "team": "Platform",
  "description": "...",
  "exposure": "external",
  "environment": "production",
  "multi_tenant": false,
  "capabilities": {
    "uses_tools": true,
    "write_actions": true,
    "touches_pii": true,
    "handles_secrets": false,
    "sends_emails": false,
    "calls_external_apis": false
  },
  "framework": "langgraph"
}

Response:
{
  "agent_id": "agt_abc123",
  "risk_level": "high",
  "recommended_protection": "full",
  "recommended_pack": "customer_support",
  "requirements": ["rbac", "pre_tool_gate", "post_tool_gate", ...]
}
```

### Data model

```python
class Agent(BaseModel):
    id: str
    name: str
    team: str
    description: str
    exposure: Literal["internal", "external", "both"]
    environment: Literal["dev", "staging", "production"]
    multi_tenant: bool
    capabilities: AgentCapabilities
    framework: Literal["langgraph", "crewai", "autogen", "raw_python", "proxy_only"]
    risk_level: Literal["low", "medium", "high", "critical"]
    protection_level: Literal["proxy_only", "agent_runtime", "full"]
    policy_pack: str
    created_at: datetime
    status: Literal["draft", "configured", "validated", "deployed"]
```
