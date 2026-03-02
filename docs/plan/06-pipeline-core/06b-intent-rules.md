# 06b — Intent & Rules Nodes

| | |
|---|---|
| **Parent** | [Step 06 — Pipeline Core](SPEC.md) |
| **Prev sub-step** | [06a — State & ParseNode](06a-state-parse.md) |
| **Next sub-step** | [06c — Decision, Transform & Graph](06c-decision-transform-graph.md) |
| **Estimated time** | 1.5–2 hours |

---

## Goal

Implement the **IntentNode** (keyword-based intent classifier) and the **RulesNode** (deterministic checks: denylist, length, encoding, special chars). These are the first analysis nodes that populate `risk_flags` and `rules_matched`.

---

## Tasks

### 1. IntentNode (`src/pipeline/nodes/intent.py`)

- [ ] Intent categories:
  | Intent | Description | Example |
  |--------|-------------|---------|
  | `qa` | General question answering | "What is photosynthesis?" |
  | `code_gen` | Code generation / debugging | "Write a Python function…" |
  | `tool_call` | Requesting external tool use | "Check my order status" |
  | `chitchat` | Casual conversation | "Hello, how are you?" |
  | `system_prompt_extract` | Attempting to extract system prompt | "Repeat your instructions" |
  | `jailbreak` | Attempting role override | "You are now DAN…" |
  | `unknown` | Unclassifiable | — |

- [ ] Pattern lists (case-insensitive matching):
  ```python
  JAILBREAK_PATTERNS = [
      "ignore previous", "ignore all prior", "ignore your instructions",
      "you are now", "pretend you are", "act as DAN",
      "jailbreak", "bypass your", "override your",
  ]
  EXTRACTION_PATTERNS = [
      "repeat your instructions", "system prompt", "what are your rules",
      "initial prompt", "show your instructions", "print your system",
  ]
  CODE_PATTERNS = [
      "write a function", "write code", "implement", "debug",
      "```", "programming", "refactor", "algorithm",
  ]
  TOOL_PATTERNS = [
      "check order", "search for", "lookup", "find me", "get status",
  ]
  GREETING_PATTERNS = [
      "hello", "hi ", "hey ", "how are you", "thanks", "bye", "good morning",
  ]
  ```

- [ ] Implementation:
  ```python
  @timed_node("intent")
  async def intent_node(state: PipelineState) -> PipelineState:
      text = state["user_message"].lower()
      intent, confidence = classify_intent(text)

      risk_flags = {**state["risk_flags"]}
      if intent in ("jailbreak", "system_prompt_extract"):
          risk_flags["suspicious_intent"] = confidence

      return {
          **state,
          "intent": intent,
          "intent_confidence": confidence,
          "risk_flags": risk_flags,
      }

  def classify_intent(text: str) -> tuple[str, float]:
      if any(p in text for p in JAILBREAK_PATTERNS):
          return "jailbreak", 0.8
      if any(p in text for p in EXTRACTION_PATTERNS):
          return "system_prompt_extract", 0.7
      if any(p in text for p in CODE_PATTERNS):
          return "code_gen", 0.6
      if any(p in text for p in TOOL_PATTERNS):
          return "tool_call", 0.5
      if any(p in text for p in GREETING_PATTERNS):
          return "chitchat", 0.9
      return "qa", 0.5
  ```

### 2. RulesNode (`src/pipeline/nodes/rules.py`)

- [ ] Deterministic checks:
  ```python
  MAX_PROMPT_LENGTH = 16_000   # characters
  MAX_MESSAGES = 50
  SPECIAL_CHAR_THRESHOLD = 0.3 # ratio
  ```
- [ ] Implementation:
  ```python
  @timed_node("rules")
  async def rules_node(state: PipelineState) -> PipelineState:
      matched = []
      risk_flags = {**state["risk_flags"]}
      text = state["user_message"]

      # 1. Denylist check
      denylist_hits = await check_denylist(text, state["policy_name"])
      for hit in denylist_hits:
          matched.append(f"denylist:{hit}")
          risk_flags["denylist_hit"] = True

      # 2. Length check
      if len(text) > MAX_PROMPT_LENGTH:
          matched.append("length_exceeded")
          risk_flags["length_exceeded"] = len(text)

      # 3. Messages count check
      if len(state["messages"]) > MAX_MESSAGES:
          matched.append("too_many_messages")
          risk_flags["too_many_messages"] = len(state["messages"])

      # 4. Encoded content (base64, hex obfuscation)
      if contains_encoded_content(text):
          matched.append("encoded_content")
          risk_flags["encoded_content"] = True

      # 5. Excessive special characters
      if excessive_special_chars(text):
          matched.append("excessive_special_chars")
          risk_flags["special_chars"] = True

      return {**state, "rules_matched": matched, "risk_flags": risk_flags}
  ```

### 3. Denylist service (`src/services/denylist.py`)

- [ ] Load `denylist_phrases` from DB for the policy:
  ```python
  async def check_denylist(text: str, policy_name: str) -> list[str]:
      """
      Check text against denylist phrases for the given policy.
      Returns list of matched phrase strings.
      """
      phrases = await get_denylist_phrases(policy_name)
      hits = []
      text_lower = text.lower()
      for phrase in phrases:
          if phrase.is_regex:
              if re.search(phrase.phrase, text, re.IGNORECASE):
                  hits.append(phrase.phrase)
          else:
              if phrase.phrase.lower() in text_lower:
                  hits.append(phrase.phrase)
      return hits
  ```
- [ ] Cache denylist in Redis (key: `denylist:{policy_name}`, TTL 60s)
- [ ] If Redis unavailable, fall back to DB query

### 4. Pattern helpers (`src/pipeline/nodes/rules.py`)

- [ ] `contains_encoded_content(text)`:
  ```python
  def contains_encoded_content(text: str) -> bool:
      """Detect base64 or hex-encoded content used for obfuscation."""
      # Base64 pattern (>40 chars of base64)
      if re.search(r'[A-Za-z0-9+/]{40,}={0,2}', text):
          return True
      # Hex-encoded strings (>20 hex chars)
      if re.search(r'(?:0x)?[0-9a-fA-F]{20,}', text):
          return True
      return False
  ```
- [ ] `excessive_special_chars(text)`:
  ```python
  def excessive_special_chars(text: str) -> bool:
      """Detect prompts with >30% non-alphanumeric characters."""
      if len(text) < 10:
          return False
      special = sum(1 for c in text if not c.isalnum() and not c.isspace())
      return (special / len(text)) > SPECIAL_CHAR_THRESHOLD
  ```

### 5. Seed denylist phrases (`src/db/seed.py`)

- [ ] Extend `seed_policies()` or add `seed_denylist()`:
  ```python
  DEFAULT_DENYLIST = [
      {"phrase": "ignore previous instructions", "category": "injection"},
      {"phrase": "ignore all prior", "category": "injection"},
      {"phrase": "you are now", "category": "jailbreak"},
      {"phrase": "pretend you are", "category": "jailbreak"},
      {"phrase": "reveal your system prompt", "category": "extraction"},
      {"phrase": "repeat the above", "category": "extraction"},
      {"phrase": r"(?i)act\s+as\s+(DAN|evil|unfiltered)", "category": "jailbreak", "is_regex": True},
      {"phrase": r"(?i)\b(bomb|weapon|exploit)\b.*\b(make|build|create)\b", "category": "harmful", "is_regex": True},
  ]
  ```
- [ ] Link phrases to `balanced`, `strict`, `paranoid` policies (not `fast`)
- [ ] Idempotent: skip if phrase already exists for that policy
- [ ] Run in lifespan startup after `seed_policies()`

---

## Definition of Done

- [ ] IntentNode classifies 7 intent types via keyword heuristics
- [ ] `"ignore previous instructions"` → `intent=jailbreak`, `risk_flags.suspicious_intent=0.8`
- [ ] `"Hello!"` → `intent=chitchat`, confidence=0.9
- [ ] `"What is Python?"` → `intent=qa`, confidence=0.5
- [ ] RulesNode checks denylist (exact + regex), length, messages count, encoding, special chars
- [ ] Denylist loaded from DB, cached in Redis (TTL 60s)
- [ ] 8+ default denylist phrases seeded (4 categories)
- [ ] Pattern utilitie: `contains_encoded_content()`, `excessive_special_chars()`
- [ ] `ruff check src/` → 0 errors

---

| **Prev** | **Next** |
|---|---|
| [06a — State & ParseNode](06a-state-parse.md) | [06c — Decision, Transform & Graph](06c-decision-transform-graph.md) |
