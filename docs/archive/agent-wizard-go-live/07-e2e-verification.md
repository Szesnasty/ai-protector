# Step 07 — End-to-End Verification

> **Effort:** 1 hour
> **Depends on:** ALL previous steps (01–06)
> **Blocks:** nothing — this is the final step

---

## Context

This is the final verification that everything works together. We walk through
the complete flow: create an agent in the wizard → generate kit → load it into
a test agent → chat with security enforcement → verify every gate decision.

We do this twice: once for Pure Python, once for LangGraph.

---

## Pre-flight Checklist

Before starting the E2E test, verify all services are running:

```bash
# Check all services
curl -s http://localhost:8000/health | jq .  # proxy-service
curl -s http://localhost:8003/health | jq .  # test-agent-python
curl -s http://localhost:8004/health | jq .  # test-agent-langgraph
curl -s http://localhost:3000                # frontend (should return HTML)

# All should return 200 OK
```

---

## Test Scenario A: Pure Python Agent

### A1. Create agent in wizard

1. Open `http://localhost:3000/agents/new`
2. Fill step 1 (Describe):
   - **Name:** `Order Manager Python`
   - **Framework:** `Raw Python`
   - **Description:** `Test agent for order and user management`
   - **Environment:** `dev`
   - **Team:** `QA`
   - Risk factors: ✅ `has_write_actions`, ✅ `touches_pii`
3. Click Next → agent created in DB

### A2. Register 5 tools (step 2)

| Name | Description | Access | Sensitivity | Confirmation | Returns PII |
|------|-------------|--------|:-----------:|:---:|:---:|
| `getOrders` | List all orders | read | low | no | no |
| `getUsers` | List all users | read | medium | no | yes |
| `searchProducts` | Search product catalog | read | low | no | no |
| `updateOrder` | Update order status | write | high | yes | no |
| `updateUser` | Update user profile | write | high | yes | no |

### A3. Define 2 roles + permissions (step 3)

**Role: `user`** (no inheritance)
- getOrders: ✅ scopes: [read]
- getUsers: ✅ scopes: [read]
- searchProducts: ✅ scopes: [read]
- updateOrder: ❌
- updateUser: ❌

**Role: `admin`** (inherits from: user)
- updateOrder: ✅ scopes: [read, write], requires_confirmation: true
- updateUser: ✅ scopes: [read, write], requires_confirmation: true

### A4. Configure security (step 4)

- Select policy pack: `customer_support` (or any — check that injection detection + PII scanning are ON)
- Review generated RBAC YAML → should show user with 3 tools, admin with 5 tools
- Review limits YAML → should show per-role limits
- Review policy YAML → should have `injection_detection: true`, `pii_redaction: true`

### A5. Generate kit (step 5)

- Click "Generate Kit"
- Verify 7 files appear: `rbac.yaml`, `limits.yaml`, `policy.yaml`, `protected_agent.py`, `.env.protector`, `test_security.py`, `README.md`
- `protected_agent.py` should use `protected_tool_call()` pattern (Raw Python)
- Note the agent ID (visible in URL or overview)

### A6. Deploy (steps 6-7)

- Run validation → should pass (all tests green)
- Set rollout mode to `observe` → click Deploy
- Agent status changes to `deployed`

### A7. Test in Pure Python agent page

1. Open `http://localhost:3000/test-agents/python`
2. Select "Order Manager Python" from dropdown
3. Click "Load Config" → should show ✅ loaded, roles: [user, admin]
4. Set role to **user**

**Test cases:**

| # | Message | Expected | Gate log |
|---|---------|----------|----------|
| 1 | `show me all orders` | JSON with 5 orders | ✅ pre_tool: ALLOW (getOrders) |
| 2 | `list all users` | JSON with 4 users | ✅ pre_tool: ALLOW + 🔎 post_tool: FLAGGED (PII: email, phone) |
| 3 | `search products laptop` | JSON with Laptop Stand | ✅ pre_tool: ALLOW (searchProducts) |
| 4 | `update order ORD-001 to shipped` | ❌ BLOCKED | ❌ pre_tool: BLOCK (RBAC: user cannot use updateOrder) |
| 5 | `update user USR-002` | ❌ BLOCKED | ❌ pre_tool: BLOCK (RBAC: user cannot use updateUser) |

5. Switch role to **admin**

| # | Message | Expected | Gate log |
|---|---------|----------|----------|
| 6 | `show me all orders` | JSON with 5 orders | ✅ pre_tool: ALLOW |
| 7 | `update order ORD-001 to shipped` | ⚠️ Requires confirmation | ⚠️ pre_tool: CONFIRM |
| 8 | [Click Confirm] | ✅ Order updated | ✅ executed |
| 9 | `update user USR-001` | ⚠️ Requires confirmation | ⚠️ pre_tool: CONFIRM |
| 10 | [Click Confirm] | ✅ User updated | ✅ executed |

---

## Test Scenario B: LangGraph Agent

### B1. Create agent in wizard

Same as A1–A6 but:
- **Name:** `Order Manager LangGraph`
- **Framework:** `LangGraph`

### B2. Test in LangGraph agent page

1. Open `http://localhost:3000/test-agents/graph`
2. Select "Order Manager LangGraph" from dropdown
3. Click "Load Config"
4. Run the **same 10 test cases** as scenario A

**Additional LangGraph-specific checks:**
- Response should include `graph_nodes_visited` showing the path taken
- For allowed calls: `[pre_tool, post_tool]` (both gates visited)
- For blocked calls: `[pre_tool]` only (blocked before execution)
- For confirmations: `[pre_tool]` (stopped at confirmation)

---

## Regression Matrix

After both scenarios pass, verify these edge cases:

| # | Test | Expected | Passes? |
|---|------|----------|:-------:|
| 1 | Chat without loading config | Error: "No config loaded" | ✅ |
| 2 | Load config with invalid agent ID | Error: 404 | ✅ |
| 3 | Send empty message | "Could not determine tool" or similar | ✅ |
| 4 | Unknown tool name (explicit) | Error or "unknown tool" | ✅ |
| 5 | Switch agent → old config replaced | New roles/tools in effect | ✅ |
| 6 | Admin confirms write → verify post-gate scan runs | gate_log has post_tool entry | ✅ |
| 7 | PII in getUsers output detected | gate_log shows PII findings | ✅ |
| 8 | Re-generate kit in wizard → reload in agent | New config takes effect | ✅ |

---

## Final Definition of Done — Agent Wizard Go-Live

**All of these must be true to consider the go-live complete:**

### Backend
- [x] All Alembic migrations applied (`aw_001`–`aw_006`)
- [x] Wizard API fully functional (create agent, add tools/roles, generate config, generate kit)
- [x] Both test agents start and serve `/health`
- [x] Test agents can load wizard kit via `/load-config`
- [x] RBAC enforcement works: unauthorized role → blocked
- [x] Limits enforcement works: call count tracking
- [x] PostToolGate PII detection works: emails/phones flagged
- [x] Confirmation flow works: high-sensitivity write tools require confirm

### Frontend
- [x] `/test-agents/python` page renders and functions
- [x] `/test-agents/graph` page renders and functions
- [x] Agent selector filtered by framework
- [x] Role selector works
- [x] Chat panel shows messages with correct styling (blocked=red, confirm=amber)
- [x] Gate log panel shows all security decisions
- [x] Confirmation button triggers re-send with `confirmed: true`
- [x] Navigation sidebar includes Test Agents section

### Integration
- [x] Full wizard flow (7 steps) → test agent (load → chat → verify gates) works end-to-end
- [x] Both frameworks tested: Pure Python + LangGraph
- [x] All 10 test cases pass for each framework (20 total)
- [x] Regression matrix (8 edge cases) passes
- [x] Docker compose with `--profile test-agents` starts all services cleanly

### Documentation
- [x] All 7 go-live spec files completed and accurate
- [x] README reflects final architecture
