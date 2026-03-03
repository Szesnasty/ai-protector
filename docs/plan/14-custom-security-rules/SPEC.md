# Step 14 — Custom Security Rules

| | |
|---|---|
| **Phase** | Custom Security Rules |
| **Estimated time** | 8–10 hours |
| **Prev** | [Step 13 — Frontend: Agent Demo UI](../13-agent-demo-ui/SPEC.md) |
| **Next** | [Step 15 — Frontend: Policies & Request Log](../15-policies-request-log/SPEC.md) |
| **Depends on** | Step 08 (policy CRUD, DenylistPhrase model), Step 09 (pipeline + rules node) |
| **Master plan** | [MVP-PLAN.md](../MVP-PLAN.md) |

---

## Goal

Give users the ability to **create, edit, delete, import, and test** custom security rules — all without restarting the server. Rules extend the existing `DenylistPhrase` model with `action` and `severity` fields, get a full CRUD API, integrate with the intent classifier and rules node, and are managed via a dedicated **Rules Editor** page in the frontend.

After this step:
- Operators add custom keywords / regex rules via UI or API
- Rules are **per-policy**, cached in Redis, hot-reloaded (zero restarts)
- Rules can **block**, **flag** (soft alert), or **boost risk score**
- Custom `intent:*` category rules extend the keyword-based intent classifier
- Bulk import/export via JSON for sharing community rule packs
- Live "Test rule" preview shows matches against sample text

---

## Sub-steps

| # | Sub-step | Scope | Est. |
|---|----------|-------|------|
| a | [14a — Model migration & CRUD API](#14a--model-migration--crud-api) | Alembic migration (add `action`, `severity`), 5 REST endpoints, Pydantic schemas, bulk import | 2–3 h |
| b | [14b — Pipeline integration](#14b--pipeline-integration) | Extend `check_denylist()` to return action/severity, extend `classify_intent()` to query custom `intent:*` rules, risk score boosting | 2–3 h |
| c | [14c — Frontend: Rules Editor](#14c--frontend-rules-editor) | Rules page: table with CRUD, filters, bulk import, rule test preview | 3–4 h |

---

## Architecture

### How rules flow through the system

```
┌──────────────────────────────────────────────────────────────────┐
│                     User creates rule via UI / API               │
│                                                                  │
│  POST /policies/{id}/rules                                       │
│  { "phrase": "hack the system",                                  │
│    "category": "intent:jailbreak",                               │
│    "action": "block",                                            │
│    "severity": "critical",                                       │
│    "is_regex": false }                                           │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│  PostgreSQL: denylist_phrases table                               │
│  + Redis cache invalidation (denylist:{policy_name})             │
└────────────────────────┬─────────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
┌─────────────┐  ┌──────────────┐  ┌──────────────┐
│ IntentNode  │  │  RulesNode   │  │ DecisionNode │
│             │  │              │  │              │
│ category=   │  │ category=    │  │ risk_score   │
│ "intent:*"  │  │ other        │  │ boosted by   │
│ → override  │  │ → denylist   │  │ score_boost  │
│   intent    │  │   match      │  │ rules        │
└─────────────┘  └──────────────┘  └──────────────┘
```

### Data flow per action type

| `action` | Effect in pipeline | Where |
|----------|-------------------|-------|
| `block` | Sets `rules_matched`, `risk_flags.denylist_hit=True` → triggers BLOCK in DecisionNode | `rules_node` (existing) |
| `flag` | Adds to `risk_flags.custom_flags[]` for visibility, does NOT auto-block | `rules_node` (new) |
| `score_boost` | Adds `severity_weight` to `risk_score` (low=+0.1, medium=+0.2, high=+0.3, critical=+0.5) | `rules_node` (new) |

### Intent-aware matching

Rules with `category` starting with `intent:` extend the keyword classifier:

```python
# After hardcoded pattern check in classify_intent():
# Query DB/cache for custom intent rules
custom_rules = await get_custom_intent_rules(policy_name)
for rule in custom_rules:
    # category = "intent:jailbreak" → intent = "jailbreak"
    target_intent = rule["category"].removeprefix("intent:")
    if matches(text, rule):
        return target_intent, 0.75  # custom-rule confidence
```

This means users can add new jailbreak patterns, new extraction patterns, or even entirely new intent categories — without touching Python code.

---

## 14a — Model migration & CRUD API

### Alembic migration

Add two columns to `denylist_phrases`:

```python
# alembic/versions/xxx_add_rule_action_severity.py
op.add_column("denylist_phrases", sa.Column(
    "action", sa.String(16), nullable=False, server_default="block"
))
op.add_column("denylist_phrases", sa.Column(
    "severity", sa.String(16), nullable=False, server_default="medium"
))
```

### Updated ORM model

```python
class DenylistPhrase(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "denylist_phrases"

    policy_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("policies.id", ondelete="CASCADE"))
    phrase: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(64), default="general")
    is_regex: Mapped[bool] = mapped_column(Boolean, default=False)
    action: Mapped[str] = mapped_column(String(16), default="block")      # NEW
    severity: Mapped[str] = mapped_column(String(16), default="medium")   # NEW
```

### Pydantic schemas

```python
class RuleAction(str, Enum):
    BLOCK = "block"
    FLAG = "flag"
    SCORE_BOOST = "score_boost"

class RuleSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class RuleCreate(BaseModel):
    phrase: str = Field(..., min_length=1, max_length=1000)
    category: str = Field("general", max_length=64)
    is_regex: bool = False
    action: RuleAction = RuleAction.BLOCK
    severity: RuleSeverity = RuleSeverity.MEDIUM

class RuleRead(RuleCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    policy_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

class RuleUpdate(BaseModel):
    phrase: str | None = None
    category: str | None = None
    is_regex: bool | None = None
    action: RuleAction | None = None
    severity: RuleSeverity | None = None

class RuleBulkImport(BaseModel):
    rules: list[RuleCreate] = Field(..., min_length=1, max_length=500)

class RuleTestRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)

class RuleTestResult(BaseModel):
    matched: bool
    phrase: str
    is_regex: bool
    match_details: str | None = None  # e.g. regex match group
```

### API endpoints

```
GET    /policies/{policy_id}/rules         → list[RuleRead]  (filter: ?category=&action=&search=)
POST   /policies/{policy_id}/rules         → RuleRead         (201)
PATCH  /policies/{policy_id}/rules/{id}    → RuleRead
DELETE /policies/{policy_id}/rules/{id}    → 204
POST   /policies/{policy_id}/rules/import  → {created: int, skipped: int}
POST   /policies/{policy_id}/rules/test    → list[RuleTestResult]
GET    /policies/{policy_id}/rules/export  → list[RuleRead]   (JSON download)
```

After every mutation: invalidate Redis cache `denylist:{policy_name}`.

### Router file

```
apps/proxy-service/src/routers/rules.py    # NEW
apps/proxy-service/src/schemas/rule.py     # NEW
```

---

## 14b — Pipeline integration

### Extend `check_denylist()` return type

Currently returns `list[str]` (matched phrases). Change to return rich results:

```python
@dataclass
class DenylistHit:
    phrase: str
    category: str
    action: str       # "block" | "flag" | "score_boost"
    severity: str     # "low" | "medium" | "high" | "critical"
    is_regex: bool

async def check_denylist(text: str, policy_name: str) -> list[DenylistHit]:
    ...
```

### Extend `rules_node`

```python
SEVERITY_SCORE = {"low": 0.1, "medium": 0.2, "high": 0.3, "critical": 0.5}

async def rules_node(state: PipelineState) -> PipelineState:
    ...
    denylist_hits = await check_denylist(text, policy_name)
    for hit in denylist_hits:
        if hit.action == "block":
            matched.append(f"denylist:{hit.phrase}")
            risk_flags["denylist_hit"] = True
        elif hit.action == "flag":
            custom_flags = risk_flags.get("custom_flags", [])
            custom_flags.append({"phrase": hit.phrase, "category": hit.category, "severity": hit.severity})
            risk_flags["custom_flags"] = custom_flags
        elif hit.action == "score_boost":
            boost = SEVERITY_SCORE.get(hit.severity, 0.2)
            risk_flags["score_boost"] = risk_flags.get("score_boost", 0.0) + boost
    ...
```

### Extend `intent_node`

Make `classify_intent` async-capable (or add a post-classification hook in `intent_node`):

```python
async def intent_node(state: PipelineState) -> PipelineState:
    text = state.get("user_message", "").lower()

    # 1. Hardcoded patterns (base layer — always runs)
    intent, confidence = classify_intent(text)

    # 2. Custom intent rules from DB (overlay — can override)
    policy_name = state.get("policy_name", "balanced")
    custom_intent_hits = await check_custom_intent_rules(text, policy_name)
    if custom_intent_hits:
        # Custom rules override with their own confidence
        best = custom_intent_hits[0]  # highest severity first
        intent = best.category.removeprefix("intent:")
        confidence = 0.75

    risk_flags = {**state.get("risk_flags", {})}
    if intent in ("jailbreak", "system_prompt_extract"):
        risk_flags["suspicious_intent"] = confidence

    return {**state, "intent": intent, "intent_confidence": confidence, "risk_flags": risk_flags}
```

### Update `_load_phrases_from_db` / cache

Include `action` and `severity` in the cached dict:

```python
return [
    {"phrase": dp.phrase, "is_regex": dp.is_regex, "category": dp.category,
     "action": dp.action, "severity": dp.severity}
    for dp in policy.denylist_phrases
]
```

### Extend `DecisionNode` for score_boost

In `decision_node`, add accumulated `score_boost` from rules to the total `risk_score`:

```python
risk_score += risk_flags.get("score_boost", 0.0)
risk_score = min(risk_score, 1.0)
```

---

## 14c — Frontend: Rules Editor

### New page: `pages/rules.vue`

| Section | Description |
|---------|-------------|
| **Policy selector** | Dropdown (reuse from Playground), shows rules for selected policy |
| **Rules table** | Vuetify `v-data-table-server` with columns: phrase, category, action, severity, is_regex, created_at |
| **Filters row** | Category filter (chips), action filter (chips), text search |
| **Add rule** | Dialog/inline form: phrase, category, is_regex toggle, action select, severity select |
| **Edit rule** | Click row → inline edit or dialog |
| **Delete rule** | Icon button with confirm dialog |
| **Bulk import** | Button → dialog with JSON textarea or file drop zone, preview before import |
| **Export** | Button → downloads JSON file of all rules for selected policy |
| **Test rule** | "Test" button on each rule → dialog with text input, shows match/no-match |

### Navigation

Add "Security Rules" item to navigation drawer (icon: `mdi-shield-lock-outline`), between Playground and Policies.

### API composable

```typescript
// composables/useRulesApi.ts
export function useRulesApi(policyId: Ref<string>) {
  const listRules = (params?) => api.get(`/policies/${policyId.value}/rules`, { params })
  const createRule = (data) => api.post(`/policies/${policyId.value}/rules`, data)
  const updateRule = (ruleId, data) => api.patch(`/policies/${policyId.value}/rules/${ruleId}`, data)
  const deleteRule = (ruleId) => api.delete(`/policies/${policyId.value}/rules/${ruleId}`)
  const bulkImport = (rules) => api.post(`/policies/${policyId.value}/rules/import`, { rules })
  const exportRules = () => api.get(`/policies/${policyId.value}/rules/export`)
  const testRule = (text) => api.post(`/policies/${policyId.value}/rules/test`, { text })
  return { listRules, createRule, updateRule, deleteRule, bulkImport, exportRules, testRule }
}
```

### File Tree (new/modified)

```
apps/frontend/
├── app/
│   ├── pages/
│   │   └── rules.vue                    # NEW — Rules Editor page
│   ├── composables/
│   │   └── useRulesApi.ts               # NEW — API layer
│   └── components/
│       └── rules/
│           ├── RulesTable.vue           # NEW — data table + filters
│           ├── RuleDialog.vue           # NEW — create/edit dialog
│           ├── RuleBulkImport.vue       # NEW — bulk import dialog
│           └── RuleTestDialog.vue       # NEW — test rule dialog

apps/proxy-service/
├── alembic/versions/
│   └── xxx_add_rule_action_severity.py  # NEW — migration
├── src/
│   ├── models/
│   │   └── denylist.py                  # MODIFIED — add action, severity
│   ├── schemas/
│   │   └── rule.py                      # NEW — RuleCreate, RuleRead, etc.
│   ├── routers/
│   │   └── rules.py                     # NEW — CRUD + bulk + test
│   ├── services/
│   │   └── denylist.py                  # MODIFIED — DenylistHit dataclass, action handling
│   ├── pipeline/nodes/
│   │   ├── intent.py                    # MODIFIED — custom intent rules overlay
│   │   └── rules.py                     # MODIFIED — flag/score_boost actions
│   └── main.py                          # MODIFIED — register rules router
└── tests/
    ├── test_rules_crud.py               # NEW
    ├── test_rules_pipeline.py           # NEW
    └── test_custom_intent.py            # NEW
```

---

## Technical Decisions

### Why extend DenylistPhrase (not a new model)?

- Already has `phrase`, `is_regex`, `category`, `policy_id` — 80% of what we need
- Already integrated with `check_denylist()` service + Redis cache
- Adding `action` + `severity` columns is a non-breaking migration (defaults: `block` + `medium`)
- Avoids duplicating cache logic, DB relationships, Alembic history

### Why `action` enum instead of just blocking?

Three use cases:
1. **`block`** — existing behaviour, hard block on match (jailbreak patterns, dangerous content)
2. **`flag`** — soft alert, visible in debug panel but no auto-block (compliance keywords, brand monitoring)
3. **`score_boost`** — adds to risk_score based on severity, may push over threshold (suspicious but not lethal)

This gives operators graduated response instead of binary block/allow.

### Why `intent:*` category convention?

Using a prefix convention instead of a separate field:
- No database schema change needed (category is already `String(64)`)
- Clear visual distinction in UI (can render as `🎯 jailbreak` vs `🛡️ general`)
- Users can create new intent categories that don't exist in hardcoded patterns
- Filtering: `SELECT ... WHERE category LIKE 'intent:%'`

### Why severity field?

Maps to risk score weights for `score_boost` action:
```
low      → +0.1  (noise, monitoring)
medium   → +0.2  (worth noting)
high     → +0.3  (likely malicious)
critical → +0.5  (near-certain threat, block-equivalent for most policies)
```

Also useful for UI sorting/priority and audit logs.

### Why JSON bulk import (not YAML)?

- JSON is natively handled by browser/backend without extra deps
- YAML needs a parser on both ends (js-yaml + PyYAML)
- JSON is copy-pasteable, curl-friendly, and exported by the API
- Can always add YAML support later as a frontend-only parser layer

---

## Example Rules

### Jailbreak patterns (intent override)
```json
[
  {"phrase": "hack the system", "category": "intent:jailbreak", "action": "block", "severity": "critical"},
  {"phrase": "bypass safety", "category": "intent:jailbreak", "action": "block", "severity": "high"},
  {"phrase": "(?i)act\\s+as.*evil", "category": "intent:jailbreak", "action": "block", "severity": "critical", "is_regex": true}
]
```

### PII detection (custom)
```json
[
  {"phrase": "(?i)\\b\\d{3}-\\d{2}-\\d{4}\\b", "category": "pii_custom", "action": "block", "severity": "critical", "is_regex": true},
  {"phrase": "(?i)credit.?card.*\\d{4}", "category": "pii_custom", "action": "flag", "severity": "high", "is_regex": true}
]
```

### Brand protection (flagging)
```json
[
  {"phrase": "competitor product", "category": "brand", "action": "flag", "severity": "low"},
  {"phrase": "(?i)\\b(lawsuit|litigation|sued)\\b", "category": "legal", "action": "flag", "severity": "medium", "is_regex": true}
]
```

### Score boosting (graduated response)
```json
[
  {"phrase": "password", "category": "sensitive_topic", "action": "score_boost", "severity": "medium"},
  {"phrase": "(?i)\\b(admin|root|sudo)\\b.*access", "category": "privilege_escalation", "action": "score_boost", "severity": "high", "is_regex": true}
]
```

---

## Definition of Done

### Automated
```bash
cd apps/proxy-service && python -m pytest tests/test_rules_crud.py tests/test_rules_pipeline.py tests/test_custom_intent.py -v
# All pass
```

### Smoke tests — API

```bash
# List rules for balanced policy
curl -s http://localhost:8000/policies/{BALANCED_ID}/rules | python -m json.tool
# → existing seed rules with action="block", severity="medium"

# Add custom jailbreak rule
curl -s http://localhost:8000/policies/{BALANCED_ID}/rules \
  -H "Content-Type: application/json" \
  -d '{"phrase":"hack the system","category":"intent:jailbreak","action":"block","severity":"critical"}' \
  | python -m json.tool
# → 201 Created

# Test rule against text
curl -s http://localhost:8000/policies/{BALANCED_ID}/rules/test \
  -H "Content-Type: application/json" \
  -d '{"text":"I want to hack the system and steal data"}' \
  | python -m json.tool
# → [{"matched": true, "phrase": "hack the system", ...}]

# Bulk import
curl -s http://localhost:8000/policies/{BALANCED_ID}/rules/import \
  -H "Content-Type: application/json" \
  -d '{"rules":[{"phrase":"evil AI","category":"general","action":"block","severity":"high"}]}' \
  | python -m json.tool
# → {"created": 1, "skipped": 0}

# Verify chat with new rule triggers block
curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" -H "x-policy: balanced" \
  -d '{"model":"llama3.1:8b","messages":[{"role":"user","content":"hack the system please"}]}' \
  | python -m json.tool
# → decision: BLOCK (or elevated risk score)
```

### Smoke tests — Frontend

```
1. Navigate to Security Rules page
2. Select "balanced" policy from dropdown
3. See existing rules in table
4. Click "Add Rule" → fill form → save → row appears
5. Click edit icon → change severity → save
6. Click delete icon → confirm → row disappears
7. Click "Bulk Import" → paste JSON array → preview → import → new rows
8. Click "Test" on a rule → enter text → see match result
9. Click "Export" → JSON file downloads
```

### Checklist
- [ ] Alembic migration adds `action` and `severity` columns
- [ ] `DenylistPhrase` model updated with new fields
- [ ] CRUD API: GET, POST, PATCH, DELETE for rules
- [ ] Bulk import endpoint accepts up to 500 rules
- [ ] Rule test endpoint checks text against all policy rules
- [ ] Export endpoint returns JSON array
- [ ] `check_denylist()` returns `DenylistHit` with action/severity
- [ ] `rules_node` handles `block`, `flag`, and `score_boost` actions
- [ ] `intent_node` queries custom `intent:*` rules from DB
- [ ] `decision_node` incorporates `score_boost` into risk_score
- [ ] Redis cache invalidated on rule CRUD mutations
- [ ] Frontend: Rules page with data table, filters, CRUD
- [ ] Frontend: Bulk import dialog with preview
- [ ] Frontend: Rule test dialog
- [ ] Frontend: Export button downloads JSON
- [ ] All new tests pass
- [ ] Existing tests still pass (backward compatible)

---

| **Prev** | **Next** |
|---|---|
| [Step 13 — Frontend: Agent Demo UI](../13-agent-demo-ui/SPEC.md) | [Step 15 — Frontend: Policies & Request Log](../15-policies-request-log/SPEC.md) |
