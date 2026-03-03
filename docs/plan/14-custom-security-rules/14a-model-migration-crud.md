# 14a — Model Migration & CRUD API

| | |
|---|---|
| **Parent** | [Step 14 — Custom Security Rules](SPEC.md) |
| **Estimated time** | 3–4 hours |
| **Depends on** | Step 08 (DenylistPhrase model, policy CRUD) |

---

## Goal

Extend the `DenylistPhrase` model with `action`, `severity`, and `description` columns. Add a category index. Seed 18+ OWASP/PII/PL rules. Build a full CRUD REST API with bulk import, export, and rule-test endpoints.

---

## Alembic Migration

Add three columns + index to `denylist_phrases`:

```python
# alembic/versions/xxx_add_rule_action_severity_description.py
op.add_column("denylist_phrases", sa.Column(
    "action", sa.String(16), nullable=False, server_default="block"
))
op.add_column("denylist_phrases", sa.Column(
    "severity", sa.String(16), nullable=False, server_default="medium"
))
op.add_column("denylist_phrases", sa.Column(
    "description", sa.String(256), nullable=False, server_default=""
))
op.create_index("ix_denylist_phrases_category", "denylist_phrases", ["category"])
```

---

## Updated ORM Model

```python
class DenylistPhrase(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "denylist_phrases"

    policy_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("policies.id", ondelete="CASCADE"))
    phrase: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(64), default="general", index=True)
    is_regex: Mapped[bool] = mapped_column(Boolean, default=False)
    action: Mapped[str] = mapped_column(String(16), default="block")          # NEW
    severity: Mapped[str] = mapped_column(String(16), default="medium")       # NEW
    description: Mapped[str] = mapped_column(String(256), default="")         # NEW
```

---

## Seed Data (in migration)

Pre-populate all policies with OWASP + PL-compliance rules. Operators get value on first boot.

```python
SEED_RULES = [
    # --- intent:* (override intent classifier) ---
    {"phrase": "(?i)(ignore|forget|disregard)\\s+(all\\s+)?(previous\\s+)?instructions",
     "category": "intent:jailbreak", "action": "block", "severity": "critical", "is_regex": True,
     "description": "Jailbreak: instruction override attempts"},
    {"phrase": "(?i)\\bDAN\\b|do anything now",
     "category": "intent:jailbreak", "action": "block", "severity": "critical", "is_regex": True,
     "description": "Jailbreak: DAN (Do Anything Now) pattern"},
    {"phrase": "(?i)(act|pretend|behave)\\s+as\\s+(an?\\s+)?(evil|unfiltered|unrestricted)",
     "category": "intent:jailbreak", "action": "block", "severity": "critical", "is_regex": True,
     "description": "Jailbreak: persona hijack (evil/unfiltered)"},
    {"phrase": "(?i)(extract|dump|list)\\s+(all\\s+)?(emails?|passwords?|secrets?|credentials?)",
     "category": "intent:extraction", "action": "block", "severity": "high", "is_regex": True,
     "description": "Data extraction: attempts to dump sensitive data"},
    {"phrase": "(?i)send\\s+(data|info|results?)\\s+to\\s+https?://",
     "category": "intent:exfiltration", "action": "block", "severity": "critical", "is_regex": True,
     "description": "Data exfiltration: attempts to send data to external URLs"},

    # --- owasp_llm (OWASP LLM Top 10 mapping) ---
    {"phrase": "(?i)(system\\s+prompt|your\\s+(instructions|rules|prompt))",
     "category": "owasp_sensitive_disclosure", "action": "block", "severity": "high", "is_regex": True,
     "description": "OWASP LLM02: Sensitive information disclosure (system prompt leak)"},
    {"phrase": "(?i)(run|execute)\\s+(command|shell|bash|cmd|script)",
     "category": "owasp_excessive_agency", "action": "block", "severity": "critical", "is_regex": True,
     "description": "OWASP LLM08: Excessive agency (command execution)"},
    {"phrase": "(?i)(delete|drop|truncate|rm\\s+-rf)\\s+",
     "category": "owasp_excessive_agency", "action": "score_boost", "severity": "high", "is_regex": True,
     "description": "OWASP LLM08: Destructive action keywords"},

    # --- pii_* (PII / compliance) ---
    {"phrase": "\\b\\d{11}\\b",
     "category": "pii_pesel", "action": "block", "severity": "critical", "is_regex": True,
     "description": "PII Poland: PESEL number (11 digits)"},
    {"phrase": "\\b\\d{3}-\\d{3}-\\d{2}-\\d{2}\\b",
     "category": "pii_nip", "action": "block", "severity": "high", "is_regex": True,
     "description": "PII Poland: NIP tax number (XXX-XXX-XX-XX)"},
    {"phrase": "\\b\\d{4}[- ]?\\d{4}[- ]?\\d{4}[- ]?\\d{4}\\b",
     "category": "pii_creditcard", "action": "block", "severity": "critical", "is_regex": True,
     "description": "PII: Credit card number pattern (16 digits)"},
    {"phrase": "(?i)\\b[A-Z]{2}\\d{2}\\s?\\d{4}\\s?\\d{4}\\s?\\d{4}\\s?\\d{4}\\s?\\d{4}\\s?\\d{4}\\b",
     "category": "pii_iban", "action": "block", "severity": "high", "is_regex": True,
     "description": "PII: IBAN bank account number"},

    # --- brand / legal ---
    {"phrase": "(?i)\\b(use|try|switch\\s+to)\\s+(chatgpt|gpt-?4|gemini|grok|claude)\\b",
     "category": "brand_competitor", "action": "flag", "severity": "low", "is_regex": True,
     "description": "Brand: competitor product mention (monitoring)"},
    {"phrase": "(?i)\\b(lawsuit|litigation|sued|legal\\s+action)\\b",
     "category": "legal_risk", "action": "flag", "severity": "medium", "is_regex": True,
     "description": "Legal: litigation-related keywords (monitoring)"},

    # --- general ---
    {"phrase": "(?i)\\b(admin|root|sudo)\\b.*\\b(password|access|credentials?)\\b",
     "category": "privilege_escalation", "action": "score_boost", "severity": "high", "is_regex": True,
     "description": "Privilege escalation: admin access requests"},
    {"phrase": "(?i)\\.onion\\b",
     "category": "exfiltration", "action": "score_boost", "severity": "medium", "is_regex": True,
     "description": "Tor hidden service URL (potential exfiltration channel)"},
]
# Insert for every existing policy in the migration's upgrade()
```

---

## Pydantic Schemas

```python
# apps/proxy-service/src/schemas/rule.py  (NEW)

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
    description: str = Field("", max_length=256)

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
    description: str | None = Field(None, max_length=256)

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

---

## API Endpoints

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

Register in `main.py`:
```python
from .routers import rules
app.include_router(rules.router)
```

---

## File Tree

```
apps/proxy-service/
├── alembic/versions/
│   └── xxx_add_rule_action_severity_description.py  # NEW — migration + seed data
├── src/
│   ├── models/
│   │   └── denylist.py                  # MODIFIED — add action, severity, description
│   ├── schemas/
│   │   └── rule.py                      # NEW — RuleCreate, RuleRead, etc.
│   ├── routers/
│   │   └── rules.py                     # NEW — CRUD + bulk + test
│   └── main.py                          # MODIFIED — register rules router
└── tests/
    └── test_rules_crud.py               # NEW
```

---

## Definition of Done

### Automated
```bash
cd apps/proxy-service && python -m pytest tests/test_rules_crud.py -v
# All CRUD + bulk + test + export tests pass
```

### Smoke tests
```bash
# List rules (includes seed data)
curl -s http://localhost:8000/policies/{BALANCED_ID}/rules | python -m json.tool
# → 18+ seed rules with action, severity, description, category

# Verify seed rule has description
curl -s http://localhost:8000/policies/{BALANCED_ID}/rules | jq '.[0] | {category, description, action, severity}'
# → {"category": "intent:jailbreak", "description": "Jailbreak: instruction override attempts", ...}

# Create rule
curl -s http://localhost:8000/policies/{BALANCED_ID}/rules \
  -H "Content-Type: application/json" \
  -d '{"phrase":"hack the system","category":"intent:jailbreak","action":"block","severity":"critical","description":"Custom: hack keyword"}' \
  | python -m json.tool
# → 201 Created

# Filter by category
curl -s 'http://localhost:8000/policies/{BALANCED_ID}/rules?category=intent:jailbreak' | python -m json.tool
# → only jailbreak rules

# Update rule
curl -s -X PATCH http://localhost:8000/policies/{BALANCED_ID}/rules/{RULE_ID} \
  -H "Content-Type: application/json" \
  -d '{"severity":"high","description":"Updated description"}' \
  | python -m json.tool
# → 200, updated fields

# Delete rule
curl -s -X DELETE http://localhost:8000/policies/{BALANCED_ID}/rules/{RULE_ID}
# → 204

# Bulk import
curl -s http://localhost:8000/policies/{BALANCED_ID}/rules/import \
  -H "Content-Type: application/json" \
  -d '{"rules":[{"phrase":"evil AI","category":"general","action":"block","severity":"high","description":"Block evil AI"}]}' \
  | python -m json.tool
# → {"created": 1, "skipped": 0}

# Test rule
curl -s http://localhost:8000/policies/{BALANCED_ID}/rules/test \
  -H "Content-Type: application/json" \
  -d '{"text":"I want to hack the system and steal data"}' \
  | python -m json.tool
# → [{"matched": true, "phrase": "hack the system", ...}]

# Export
curl -s http://localhost:8000/policies/{BALANCED_ID}/rules/export | python -m json.tool
# → JSON array of all rules
```

### Checklist
- [ ] Alembic migration adds `action`, `severity`, and `description` columns
- [ ] Alembic migration adds index on `category` column
- [ ] Alembic migration seeds 18+ rules per policy (OWASP + PII/PL + brand)
- [ ] `DenylistPhrase` model updated with new fields (action, severity, description)
- [ ] Pydantic schemas: `RuleCreate`, `RuleRead`, `RuleUpdate`, `RuleBulkImport`, `RuleTestRequest/Result`
- [ ] CRUD API: GET (with `?category=` / `?action=` / `?search=` filters), POST, PATCH, DELETE
- [ ] Bulk import endpoint accepts up to 500 rules, returns `{created, skipped}`
- [ ] Rule test endpoint checks text against all policy rules
- [ ] Export endpoint returns JSON array (with description)
- [ ] Redis cache `denylist:{policy_name}` invalidated on every mutation
- [ ] Router registered in `main.py`
- [ ] `test_rules_crud.py` covers all endpoints + edge cases
- [ ] Existing tests still pass (backward compatible — defaults: action=block, severity=medium, description="")

---

| **Prev** | **Next** |
|---|---|
| — | [14b — Pipeline Integration](14b-pipeline-integration.md) |
