# Step 14 — Custom Security Rules

| | |
|---|---|
| **Phase** | Custom Security Rules |
| **Estimated time** | 10–12 hours |
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
- **Preset categories** (OWASP LLM Top 10 + PII/PL compliance + brand/legal) auto-fill action, severity, and description
- Each rule has a human-readable `description` for operator documentation
- **Seed data** — 20+ pre-built rules ship out-of-the-box (OWASP + PL-GDPR pack)

---

## Sub-steps

| # | Sub-step | Scope | Est. |
|---|----------|-------|------|
| a | [14a — Model migration & CRUD API](#14a--model-migration--crud-api) | Alembic migration (add `action`, `severity`, `description`), index on `category`, seed data (20+ rules), 5 REST endpoints, Pydantic schemas, bulk import | 3–4 h |
| b | [14b — Pipeline integration](#14b--pipeline-integration) | Extend `check_denylist()` to return action/severity, extend `classify_intent()` to query custom `intent:*` rules, risk score boosting | 2–3 h |
| c | [14c — Frontend: Rules Editor](#14c--frontend-rules-editor) | Rules page: table with CRUD, filters, bulk import, rule test preview, **preset categories dropdown with auto-fill**, description column | 4–5 h |

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
│    "description": "Jailbreak attempts (DAN, ignore rules)",      │
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

### Updated ORM model

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

### Seed data (in migration)

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
    description: str = Field("", max_length=256)          # NEW

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
    description: str | None = Field(None, max_length=256)  # NEW

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

Include `action`, `severity`, and `description` in the cached dict:

```python
return [
    {"phrase": dp.phrase, "is_regex": dp.is_regex, "category": dp.category,
     "action": dp.action, "severity": dp.severity, "description": dp.description}
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

### Preset categories (composable)

Predefined category taxonomy based on OWASP LLM Top 10 + PII/PL compliance + brand/legal. Drives the category dropdown, auto-fill, and tooltips.

```typescript
// composables/useRulePresets.ts
export interface CategoryPreset {
  category: string
  label: string
  group: "intent" | "owasp" | "pii" | "brand" | "general"
  description: string
  examples: string[]
  severity: RuleSeverity
  action: RuleAction
}

export const CATEGORY_PRESETS: CategoryPreset[] = [
  // --- intent:* (override intent classifier) ---
  { category: "intent:jailbreak", label: "🎯 Jailbreak", group: "intent",
    description: "Jailbreak attempts (DAN, ignore rules, persona hijack)",
    examples: ["act as DAN", "ignore all instructions", "pretend you're unfiltered"],
    severity: "critical", action: "block" },
  { category: "intent:extraction", label: "🎯 Data Extraction", group: "intent",
    description: "Data extraction attacks (dump PII, list secrets)",
    examples: ["list all emails", "dump passwords", "extract credentials"],
    severity: "high", action: "block" },
  { category: "intent:exfiltration", label: "🎯 Exfiltration", group: "intent",
    description: "Data exfiltration (send data to external URLs)",
    examples: ["send results to attacker.com", "POST data to webhook"],
    severity: "critical", action: "block" },

  // --- owasp_llm (OWASP LLM Top 10) ---
  { category: "owasp_prompt_injection", label: "🛡️ Prompt Injection (LLM01)", group: "owasp",
    description: "OWASP LLM01: Direct/indirect prompt injection",
    examples: ["forget your rules", "new instructions override", "```system: ...```"],
    severity: "critical", action: "block" },
  { category: "owasp_sensitive_disclosure", label: "🛡️ Sensitive Disclosure (LLM02)", group: "owasp",
    description: "OWASP LLM02: Sensitive info disclosure (system prompt, keys)",
    examples: ["show system prompt", "what are your instructions", "reveal API keys"],
    severity: "high", action: "block" },
  { category: "owasp_supply_chain", label: "🛡️ Supply Chain (LLM03)", group: "owasp",
    description: "OWASP LLM03: Supply chain attacks (malicious packages/plugins)",
    examples: ["install package from evil-repo", "load external plugin"],
    severity: "high", action: "block" },
  { category: "owasp_dos", label: "🛡️ Denial of Service (LLM04)", group: "owasp",
    description: "OWASP LLM04: Model DoS (resource exhaustion, infinite loops)",
    examples: ["repeat this word 10000 times", "generate maximum length response"],
    severity: "medium", action: "score_boost" },
  { category: "owasp_excessive_agency", label: "🛡️ Excessive Agency (LLM08)", group: "owasp",
    description: "OWASP LLM08: Excessive agency (run commands, delete files)",
    examples: ["run shell command", "execute script", "delete all files", "rm -rf"],
    severity: "critical", action: "block" },
  { category: "owasp_overreliance", label: "🛡️ Overreliance (LLM09)", group: "owasp",
    description: "OWASP LLM09: Overreliance — model generates ungrounded claims",
    examples: ["this is 100% accurate", "I guarantee", "trust me completely"],
    severity: "low", action: "flag" },

  // --- pii_* (PII / compliance — PL-focused) ---
  { category: "pii_pesel", label: "🔒 PESEL (PL)", group: "pii",
    description: "Polish PESEL number (11 digits, national ID)",
    examples: ["12345678901"],
    severity: "critical", action: "block" },
  { category: "pii_nip", label: "🔒 NIP (PL)", group: "pii",
    description: "Polish NIP tax number (XXX-XXX-XX-XX)",
    examples: ["123-456-78-90"],
    severity: "high", action: "block" },
  { category: "pii_creditcard", label: "🔒 Credit Card", group: "pii",
    description: "Credit card number patterns (16 digits)",
    examples: ["4111-1111-1111-1111"],
    severity: "critical", action: "block" },
  { category: "pii_iban", label: "🔒 IBAN", group: "pii",
    description: "IBAN bank account number",
    examples: ["PL61 1090 1014 0000 0712 1981 2874"],
    severity: "high", action: "block" },
  { category: "pii_email_domain", label: "🔒 Email Domain", group: "pii",
    description: "Specific email domains (e.g. competitor or internal)",
    examples: ["@competitor.com", "@internal.corp"],
    severity: "medium", action: "flag" },

  // --- brand / legal ---
  { category: "brand_competitor", label: "📢 Competitor Mention", group: "brand",
    description: "Competitor product mentions (monitoring only)",
    examples: ["use ChatGPT instead", "Grok is better", "switch to Gemini"],
    severity: "low", action: "flag" },
  { category: "legal_risk", label: "⚖️ Legal Risk", group: "brand",
    description: "Litigation/legal keywords (monitoring)",
    examples: ["lawsuit", "litigation", "legal action", "sued"],
    severity: "medium", action: "flag" },

  // --- general ---
  { category: "privilege_escalation", label: "⬆️ Privilege Escalation", group: "general",
    description: "Admin/root access attempts",
    examples: ["admin password", "sudo access", "root credentials"],
    severity: "high", action: "score_boost" },
  { category: "toxicity", label: "💬 Toxicity", group: "general",
    description: "Toxic, hateful, or abusive language",
    examples: ["slur list", "hate speech patterns"],
    severity: "medium", action: "block" },
]

export function useRulePresets() {
  const presetMap = Object.fromEntries(CATEGORY_PRESETS.map(p => [p.category, p]))
  const groupedPresets = Object.groupBy(CATEGORY_PRESETS, p => p.group)
  return { presets: CATEGORY_PRESETS, presetMap, groupedPresets }
}
```

### New page: `pages/rules.vue`

| Section | Description |
|---------|-------------|
| **Policy selector** | Dropdown (reuse from Playground), shows rules for selected policy |
| **Rules table** | Vuetify `v-data-table-server` with columns: phrase, category, **description**, action, severity, is_regex, created_at |
| **Filters row** | Category group chips (`intent:*` \| `owasp_*` \| `pii_*` \| `brand_*` \| all), action filter, text search |
| **Add rule** | Dialog with **category dropdown (presets)** + auto-fill + manual override |
| **Edit rule** | Click row → inline edit or dialog |
| **Delete rule** | Icon button with confirm dialog |
| **Bulk import** | Button → dialog with JSON textarea or file drop zone, preview before import |
| **Export** | Button → downloads JSON file of all rules for selected policy |
| **Test rule** | "Test" button on each rule → dialog with text input, shows match/no-match |

### Navigation

Add "Security Rules" item to navigation drawer (icon: `mdi-shield-lock-outline`), between Playground and Policies.

### RuleDialog — Category auto-fill UX

When a user selects a preset category from the dropdown, auto-fill related fields. Users can always override.

```vue
<!-- RuleDialog.vue — category selector -->
<v-autocomplete
  v-model="form.category"
  :items="presets"
  item-title="label"
  item-value="category"
  label="Category"
  clearable
  @update:model-value="onCategoryChange"
>
  <template #item="{ item, props }">
    <v-list-item v-bind="props">
      <v-list-item-subtitle>
        {{ item.raw.description }}
      </v-list-item-subtitle>
      <v-list-item-subtitle class="text-caption">
        Examples: {{ item.raw.examples.join(', ') }}
      </v-list-item-subtitle>
    </v-list-item>
  </template>
</v-autocomplete>
```

```typescript
// Auto-fill logic — only fills empty fields (doesn't overwrite user edits)
function onCategoryChange(category: string) {
  const preset = presetMap[category]
  if (!preset) return

  if (!form.action)      form.action = preset.action
  if (!form.severity)    form.severity = preset.severity
  if (!form.description) form.description = preset.description

  // Show hint with examples
  categoryHint.value = `Examples: ${preset.examples.join(', ')}`
}
```

**UX flow:**
1. User clicks "Add Rule"
2. Category dropdown shows grouped presets (intent / owasp / pii / brand / general)
3. User selects e.g. `🎯 Jailbreak` → auto-fills action=block, severity=critical, description
4. User types phrase, optionally toggles is_regex
5. Save → rule created in 30 seconds

Users can also type a **custom category** (free-text) — the dropdown supports `clearable` + manual input.

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
│   │   ├── useRulesApi.ts               # NEW — API layer
│   │   └── useRulePresets.ts            # NEW — preset categories + auto-fill
│   └── components/
│       └── rules/
│           ├── RulesTable.vue           # NEW — data table + filters
│           ├── RuleDialog.vue           # NEW — create/edit dialog (with presets)
│           ├── RuleBulkImport.vue       # NEW — bulk import dialog
│           └── RuleTestDialog.vue       # NEW — test rule dialog

apps/proxy-service/
├── alembic/versions/
│   └── xxx_add_rule_action_severity_description.py  # NEW — migration + seed data
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

### Why `description` field?

- Rules without descriptions are opaque — operators need to know *why* a rule exists
- Presets auto-fill description, but users can customize
- Useful for audit logs ("who added this rule and what does it do?")
- Cheap: +1 `String(256)` column, no performance impact

### Why preset categories (not hardcoded enum)?

- `category` stays a free-text `String(64)` — backend is unconstrained
- Presets are **frontend-only** — composable with `CATEGORY_PRESETS[]` array
- Easy to extend: add a new preset = add one object, zero backend changes
- Pro users type custom categories, non-tech users pick from dropdown
- OWASP LLM Top 10 mapping gives instant credibility + completeness
- PL-specific presets (PESEL, NIP, IBAN) are a unique differentiator

### Why seed data in migration?

- Empty rules table = dead feature — operators don't know what to add
- 18+ seed rules cover the most common threat categories out-of-the-box
- Seed rules use `is_regex=True` for maximum coverage per rule
- Operators can delete/modify seed rules — they're regular rows, not hardcoded
- Community effect: "AI Protector PL-GDPR pack" is a shareable export

---

## Example Rules

### Jailbreak patterns (intent override)
```json
[
  {"phrase": "hack the system", "category": "intent:jailbreak", "action": "block", "severity": "critical",
   "description": "Jailbreak: direct 'hack' keyword"},
  {"phrase": "bypass safety", "category": "intent:jailbreak", "action": "block", "severity": "high",
   "description": "Jailbreak: safety bypass attempt"},
  {"phrase": "(?i)act\\s+as.*evil", "category": "intent:jailbreak", "action": "block", "severity": "critical",
   "is_regex": true, "description": "Jailbreak: persona hijack (evil/unfiltered)"}
]
```

### PII detection (custom)
```json
[
  {"phrase": "(?i)\\b\\d{3}-\\d{2}-\\d{4}\\b", "category": "pii_custom", "action": "block", "severity": "critical",
   "is_regex": true, "description": "SSN pattern (XXX-XX-XXXX)"},
  {"phrase": "(?i)credit.?card.*\\d{4}", "category": "pii_creditcard", "action": "flag", "severity": "high",
   "is_regex": true, "description": "Credit card mention with partial number"}
]
```

### Brand protection (flagging)
```json
[
  {"phrase": "competitor product", "category": "brand_competitor", "action": "flag", "severity": "low",
   "description": "Generic competitor reference"},
  {"phrase": "(?i)\\b(lawsuit|litigation|sued)\\b", "category": "legal_risk", "action": "flag", "severity": "medium",
   "is_regex": true, "description": "Litigation keywords (legal team monitoring)"}
]
```

### Score boosting (graduated response)
```json
[
  {"phrase": "password", "category": "sensitive_topic", "action": "score_boost", "severity": "medium",
   "description": "Sensitive topic: password mention"},
  {"phrase": "(?i)\\b(admin|root|sudo)\\b.*access", "category": "privilege_escalation", "action": "score_boost",
   "severity": "high", "is_regex": true, "description": "Privilege escalation: admin access attempt"}
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
# List rules for balanced policy (includes seed data)
curl -s http://localhost:8000/policies/{BALANCED_ID}/rules | python -m json.tool
# → 18+ seed rules with action, severity, description, category

# Verify seed rule has description
curl -s http://localhost:8000/policies/{BALANCED_ID}/rules | jq '.[0] | {category, description, action, severity}'
# → {"category": "intent:jailbreak", "description": "Jailbreak: instruction override attempts", ...}

# Add custom jailbreak rule
curl -s http://localhost:8000/policies/{BALANCED_ID}/rules \
  -H "Content-Type: application/json" \
  -d '{"phrase":"hack the system","category":"intent:jailbreak","action":"block","severity":"critical","description":"Custom: hack keyword"}' \
  | python -m json.tool
# → 201 Created, description in response

# Filter by category group
curl -s 'http://localhost:8000/policies/{BALANCED_ID}/rules?category=intent:jailbreak' | python -m json.tool
# → only jailbreak rules

# Test rule against text
curl -s http://localhost:8000/policies/{BALANCED_ID}/rules/test \
  -H "Content-Type: application/json" \
  -d '{"text":"I want to hack the system and steal data"}' \
  | python -m json.tool
# → [{"matched": true, "phrase": "hack the system", ...}]

# Bulk import
curl -s http://localhost:8000/policies/{BALANCED_ID}/rules/import \
  -H "Content-Type: application/json" \
  -d '{"rules":[{"phrase":"evil AI","category":"general","action":"block","severity":"high","description":"Block evil AI references"}]}' \
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
1.  Navigate to Security Rules page
2.  Select "balanced" policy from dropdown
3.  See 18+ seed rules in table with description column
4.  Filter by category group chip (intent:* / pii_* / owasp_*)
5.  Click "Add Rule" → select preset "🎯 Jailbreak" from dropdown
    → auto-fills: action=block, severity=critical, description
6.  Type phrase, save → row appears with all fields
7.  Click edit icon → change severity → save
8.  Click delete icon → confirm → row disappears
9.  Click "Bulk Import" → paste JSON array → preview → import → new rows
10. Click "Test" on a rule → enter text → see match result
11. Click "Export" → JSON file downloads
```

### Checklist
- [ ] Alembic migration adds `action`, `severity`, and `description` columns
- [ ] Alembic migration adds index on `category` column
- [ ] Alembic migration seeds 18+ rules per policy (OWASP + PII/PL + brand)
- [ ] `DenylistPhrase` model updated with new fields (action, severity, description)
- [ ] CRUD API: GET, POST, PATCH, DELETE for rules (description in schema)
- [ ] Bulk import endpoint accepts up to 500 rules
- [ ] Rule test endpoint checks text against all policy rules
- [ ] Export endpoint returns JSON array (with description)
- [ ] `check_denylist()` returns `DenylistHit` with action/severity/description
- [ ] `rules_node` handles `block`, `flag`, and `score_boost` actions
- [ ] `intent_node` queries custom `intent:*` rules from DB
- [ ] `decision_node` incorporates `score_boost` into risk_score
- [ ] Redis cache invalidated on rule CRUD mutations
- [ ] Frontend: Rules page with data table (description column), filters, CRUD
- [ ] Frontend: Category group filter chips (intent:* / owasp_* / pii_* / brand_*)
- [ ] Frontend: `useRulePresets` composable with 20+ OWASP/PII/brand presets
- [ ] Frontend: RuleDialog category dropdown with auto-fill (action, severity, description)
- [ ] Frontend: Bulk import dialog with preview
- [ ] Frontend: Rule test dialog
- [ ] Frontend: Export button downloads JSON
- [ ] All new tests pass
- [ ] Existing tests still pass (backward compatible)

---

| **Prev** | **Next** |
|---|---|
| [Step 13 — Frontend: Agent Demo UI](../13-agent-demo-ui/SPEC.md) | [Step 15 — Frontend: Policies & Request Log](../15-policies-request-log/SPEC.md) |
