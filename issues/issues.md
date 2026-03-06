# Known Issues & Improvements

Tracked issues for the AI Protector project, prioritised by impact.

---

## Critical

### ISS-001: ~~LLM Guard threshold singleton — no hot-reload~~ ✅ RESOLVED

**Component:** `apps/proxy-service/src/pipeline/nodes/llm_guard.py`

**Status:** Fixed. `get_scanners()` now tracks the thresholds used at init
time (`_active_thresholds`). On every call, the requested thresholds are
compared with the active ones — if they differ the scanners are rebuilt
automatically. No container restart required.

**Commit:** `feat/go-live` branch

---

### ISS-002: ~~Cold start ~50 s on first request~~ ✅ RESOLVED

**Component:** `apps/proxy-service/src/main.py`

**Status:** Fixed. ML models (LLM Guard, NeMo, Presidio) are now preloaded
in the background via `asyncio.create_task(_preload_scanners())` during
application startup. The server responds immediately; first real request
latency dropped from ~50 s → ~0.9 s.

**Commit:** `2434ec2`

---

## High

### ISS-003: ML Judge is a phantom feature

**Component:** UI policy editor (`Scanner Nodes` chips), decision node

The "ML Judge" chip appears in the policy editor, suggesting a dedicated ML
model for judging request safety. In reality there is no `ml_judge` scanner
node — the chip only sets a flag that slightly adjusts risk weights in the
decision node.

**Impact:** Misleading to users. Implies a capability that does not exist.

**Fix:** Either implement a real ML Judge scanner (e.g., a fine-tuned
classifier) or remove the chip from the UI until it is implemented.

---

### ISS-004: Canary Tokens chip has no backing implementation

**Component:** UI policy editor, pipeline

The "Canary" chip sets `enable_canary: true` in the policy thresholds, but
no pipeline node reads or acts on this flag. Canary token injection and
detection is not implemented.

**Impact:** Feature advertised in UI but non-functional.

**Fix:** Either implement canary token injection in the transform node and
detection in the output filter, or hide the chip until implemented.

---

### ISS-005: Intent classifier is keyword-only — easily evaded

**Component:** `apps/proxy-service/src/pipeline/nodes/intent.py`

Intent classification uses pure substring matching (`if keyword in text`).
Paraphrasing an attack easily bypasses it (e.g., "show me your instructions"
vs "reveal your system prompt"). NeMo Guardrails partly compensates with
embedding matching, but only for its 11 predefined categories.

**Impact:** Security gap — attackers can rephrase to bypass intent detection.

**Fix:** Replace keyword matcher with a lightweight ML classifier (e.g.,
`setfit` or a small transformer distilled to ~50 MB) or rely entirely on
NeMo embeddings for intent classification.

---

## Medium

### ISS-006: NeMo Guardrails returns hardcoded score (0.85)

**Component:** `apps/proxy-service/src/pipeline/nodes/nemo_guardrails.py`

When NeMo matches an attack intent, the node always reports a risk score of
0.85 regardless of the actual cosine similarity. The real similarity score
is not extracted from the NeMo response.

**Impact:** Risk scores are less granular — all NeMo detections look
identical. Fine-tuning `nemo_weight` has limited practical effect.

**Fix:** Extract the actual cosine similarity from NeMo's response metadata
and use it as the per-rail score.

---

### ISS-007: Output filter system-prompt leak detection is minimal

**Component:** `apps/proxy-service/src/pipeline/nodes/output_filter.py`

System prompt leak detection checks only 4 hardcoded string fragments.
An LLM can easily leak the system prompt using different wording.

**Impact:** Low effectiveness against prompt extraction attacks on the
output side.

**Fix:** Use embedding similarity against the actual system prompt (if
available) or a small classifier trained on system-prompt-like text.

---

### ISS-008: Several pipeline constants are not policy-configurable

**Component:** Various pipeline nodes

The following limits are hardcoded and cannot be tuned per-policy:

| Constant | Location | Default |
|----------|----------|---------|
| `MAX_PROMPT_LENGTH` | `rules.py` | 16 000 chars |
| `MAX_MESSAGES` | `rules.py` | 50 |
| `SPECIAL_CHAR_THRESHOLD` | `rules.py` | 0.3 |
| `max_turns` | `memory_hygiene.py` | 20 |
| `max_chars_per_message` | `memory_hygiene.py` | 4 000 |
| `max_total_chars` | `memory_hygiene.py` | 32 000 |
| Presidio `score_threshold` | `presidio.py` | env var |
| NeMo similarity threshold | `config.yml` | 0.4 |
| Intent confidence values | `intent.py` | hardcoded |

**Impact:** Power users cannot fine-tune these per policy level.

**Fix:** Read these from `policy_config.thresholds` with current values as
defaults, so they can be overridden per-policy.

---

### ISS-009: Presidio score threshold is env-var-only

**Component:** `apps/proxy-service/src/pipeline/nodes/presidio.py`

The PII detection confidence threshold comes from `settings.presidio_score_threshold`
(environment variable), not from per-policy config. All policies share the
same sensitivity.

**Impact:** Cannot make `strict` more sensitive to PII than `balanced`.

**Fix:** Read threshold from `policy_config.thresholds.presidio_score_threshold`
with the env var as fallback.

---

## Low

### ISS-010: Secret detection regex patterns are limited

**Component:** `apps/proxy-service/src/pipeline/nodes/output_filter.py`

Only 5 regex patterns for secret detection (OpenAI keys, GitHub tokens,
Bearer tokens, private keys, passwords). Missing: AWS keys, Azure keys,
Slack tokens, database connection strings, JWTs, etc.

**Fix:** Expand patterns or integrate a dedicated secret scanner library
(e.g., `detect-secrets`).

---

### ISS-011: Langfuse `trace` AttributeError in demo mode

**Component:** `apps/proxy-service/src/services/langfuse_client.py`

In demo mode (no Langfuse server), each request logs
`AttributeError: 'Langfuse' object has no attribute 'trace'`. Non-blocking
but noisy.

**Fix:** Guard with `hasattr` check or disable Langfuse client entirely when
in demo mode.
