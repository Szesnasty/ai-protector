# 07b — Presidio PII Node

| | |
|---|---|
| **Parent** | [Step 07 — Security Scanners](SPEC.md) |
| **Prev sub-step** | [07a — LLM Guard Node](07a-llm-guard.md) |
| **Next sub-step** | [07c — Parallel Execution & Integration](07c-parallel-integration.md) |
| **Estimated time** | 2–2.5 hours |

---

## Goal

Integrate **Microsoft Presidio** as a pipeline node for PII detection and anonymization. Supports 10 entity types with configurable actions: `flag` (record only), `mask` (anonymize before LLM), or `block` (reject request).

---

## Tasks

### 1. Presidio node (`src/pipeline/nodes/presidio.py`)

- [x] Entity types to detect:
  | Entity | Examples |
  |--------|---------|
  | `PERSON` | "John Smith", "Dr. Martinez" |
  | `EMAIL_ADDRESS` | "john@example.com" |
  | `PHONE_NUMBER` | "+1-555-0123" |
  | `CREDIT_CARD` | "4111-1111-1111-1111" |
  | `US_SSN` | "123-45-6789" |
  | `IP_ADDRESS` | "192.168.1.1" |
  | `IBAN_CODE` | "DE89370400440532013000" |
  | `LOCATION` | "123 Main St, New York" |
  | `DATE_TIME` | "born on 1990-01-15" |
  | `NRP` | Nationality/religious/political groups |

- [x] Lazy initialization:
  ```python
  from presidio_analyzer import AnalyzerEngine, RecognizerResult
  from presidio_anonymizer import AnonymizerEngine

  _analyzer: AnalyzerEngine | None = None
  _anonymizer: AnonymizerEngine | None = None

  def get_analyzer() -> AnalyzerEngine:
      global _analyzer
      if _analyzer is None:
          _analyzer = AnalyzerEngine()
      return _analyzer

  def get_anonymizer() -> AnonymizerEngine:
      global _anonymizer
      if _anonymizer is None:
          _anonymizer = AnonymizerEngine()
      return _anonymizer
  ```

### 2. Node implementation

- [x] Detection:
  ```python
  PII_ENTITIES = [
      "PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD",
      "US_SSN", "IP_ADDRESS", "IBAN_CODE", "LOCATION", "DATE_TIME", "NRP",
  ]

  @timed_node("presidio")
  async def presidio_node(state: PipelineState) -> PipelineState:
      text = state["user_message"]
      thresholds = state["policy_config"].get("thresholds", {})
      pii_action = thresholds.get("pii_action", "flag")  # "flag"|"mask"|"block"

      analyzer = get_analyzer()
      results: list[RecognizerResult] = await asyncio.to_thread(
          analyzer.analyze,
          text=text,
          language="en",
          entities=PII_ENTITIES,
          score_threshold=0.4,
      )

      entities_found = [
          {
              "entity_type": r.entity_type,
              "score": round(r.score, 4),
              "start": r.start,
              "end": r.end,
          }
          for r in results
      ]

      risk_flags = {**state["risk_flags"]}
      if entities_found:
          risk_flags["pii"] = [e["entity_type"] for e in entities_found]
          risk_flags["pii_count"] = len(entities_found)

      return {
          **state,
          "risk_flags": risk_flags,
          "scanner_results": {
              **state.get("scanner_results", {}),
              "presidio": {
                  "entities": entities_found,
                  "pii_action": pii_action,
              },
          },
      }
  ```

### 3. PII masking (anonymization)

- [x] When `pii_action == "mask"`, anonymize the user message:
  ```python
  async def mask_pii_in_messages(
      messages: list[dict],
      original_text: str,
      analyzer_results: list[RecognizerResult],
  ) -> list[dict]:
      """Replace PII in user messages with placeholders like <PERSON>, <EMAIL_ADDRESS>."""
      anonymizer = get_anonymizer()
      anonymized = await asyncio.to_thread(
          anonymizer.anonymize,
          text=original_text,
          analyzer_results=analyzer_results,
      )

      masked_messages = [msg.copy() for msg in messages]
      for msg in masked_messages:
          if msg["role"] == "user" and msg["content"] == original_text:
              msg["content"] = anonymized.text
              break
      return masked_messages
  ```
- [x] Store `modified_messages` in state when masking is applied

### 4. Configuration (`src/config.py`)

- [x] Add settings:
  ```python
  enable_presidio: bool = True
  presidio_language: str = "en"
  presidio_score_threshold: float = 0.4
  ```

### 5. spaCy model dependency

- [x] Presidio requires a spaCy NER model
- [x] Options:
  | Model | Size | Accuracy | Recommended for |
  |-------|------|----------|----------------|
  | `en_core_web_sm` | ~12MB | Good | Development, fast builds |
  | `en_core_web_lg` | ~560MB | Better | Production |
- [x] Add to Dockerfile:
  ```dockerfile
  RUN pip install --no-cache-dir . && python -m spacy download en_core_web_lg
  ```
- [x] For dev: `pip install en_core_web_sm` or `python -m spacy download en_core_web_sm`

### 6. Tests (`tests/test_presidio_node.py`)

- [x] `"My email is john@example.com"` → `pii=["EMAIL_ADDRESS"]`
- [x] `"Call me at 555-0123"` → `pii=["PHONE_NUMBER"]`
- [x] `"My SSN is 123-45-6789"` → `pii=["US_SSN"]`
- [x] No PII present → empty pii list, no risk flags
- [x] `pii_action=mask` → `modified_messages` has anonymized text (`<EMAIL_ADDRESS>`, etc.)
- [x] `pii_action=block` → decision info passed downstream (tested in 07c)
- [x] Analyzer error → logged, not raised

---

## Definition of Done

- [x] `src/pipeline/nodes/presidio.py` — node with 10 entity types
- [x] Analyzer + Anonymizer lazy-initialized
- [x] `asyncio.to_thread()` for CPU-bound NER
- [x] PII entities recorded in `risk_flags.pii` and `scanner_results.presidio`
- [x] `mask_pii_in_messages()` replaces PII with `<ENTITY_TYPE>` placeholders
- [x] Config: `enable_presidio`, `presidio_language`, `presidio_score_threshold`
- [x] spaCy model installed (dev: sm, prod: lg)
- [x] All tests pass
- [x] `ruff check src/` → 0 errors

---

| **Prev** | **Next** |
|---|---|
| [07a — LLM Guard Node](07a-llm-guard.md) | [07c — Parallel Execution & Integration](07c-parallel-integration.md) |
