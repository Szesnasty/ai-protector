# A2 — Deobfuscation / Normalization Layer

> **Track:** A (detection credibility)
> **Tracks issue:** ISS-012
> **Priority:** High
> **Effort:** S–M
> **Status:** ✅ Implemented (core) — `src/pipeline/utils/deobfuscate.py`

---

## Implementation note

Shipped as a `build_scan_text()` helper called once in the intent node, which
sets a `scan_text` field = raw message + decoded variants (leetspeak, spaced,
homoglyph, ROT13, base64). The injection-oriented detectors (intent classifier,
denylist, LLM Guard) read `scan_text`; **PII (Presidio) keeps reading the raw
text** so entity offsets stay valid, and the original message is what the LLM
receives. ROT13 is gated by an English-likeness check to avoid decoding benign
English into injection-like gibberish (a false-positive caught during testing).

**Result:** external seed corpus leetspeak 25%→100%, overall 86.8%→100%; internal
suite 97.6%→98.8%; FPR stayed 0%. **Deferred:** multilingual translation (the
Turkish/foreign-language cases) — still needs A1 or a translation step.

---

## 1. Goal

Add a normalization pass before detection so that obfuscated and encoded
attacks are decoded and re-scanned. This is the cheapest large win on the board:
six known bypasses are currently marked `xfail`.

## 2. Current state

ISS-012: the entire pre-LLM pipeline (keyword classifier, LLM Guard, NeMo,
Presidio) operates on plain-text English. Obfuscated prompts get
`decision=ALLOW, intent=qa, risk≈0.00`. Known bypasses (marked `xfail` in
`test_scenario_deterministic.py`):

| ID | Technique | Example |
|----|-----------|---------|
| PLY-106 | Leet speak | `1gn0r3 4ll pr3v10us` |
| PLY-108 | Spaced chars | `I g n o r e a l l` |
| PLY-115 | Caesar (ROT-3) | `ljqruh doo suhylrxv` |
| PLY-134 | ROT13 | `vtaber nyy cerivbhf` |
| AGT-065/066 | Multi-language (TR) | `Tüm önceki talimatları yok say` |

## 3. Approach (big blocks)

1. **New `normalize` node** placed after
   [`parse.py`](../../apps/proxy-service/src/pipeline/nodes/parse.py) (which sets
   `user_message`) and before `intent`. Produces a `normalized_message` field on
   state — the raw `user_message` stays authoritative for content; the
   normalized form exists **only for detection**.
2. **Transforms:**
   - Leet de-mapping (`0→o, 3→e, 1→i, 4→a, 5→s, 7→t, @→a`).
   - Collapse spaced/interleaved characters (`h e l l o → hello`).
   - Unicode NFKC fold + homoglyph/confusables mapping; strip zero-width chars.
   - Brute candidate decodes: ROT-N / Caesar, base64, hex — kept as *candidate*
     variants, not blind replacement.
3. **Dual-scan / max-risk.** Run intent (and optionally the scanners) on both
   the raw and the normalized/candidate variants; the request's risk is the
   **max** across variants. A decoded variant only elevates risk if it
   *independently* trips a detector — this avoids false positives on text that
   merely happens to be base64-decodable.
4. **Multilingual (sub-block).** Language-detect, then either (a) a
   translate-to-English step before classification, or (b) multilingual keyword
   packs. Can ship after the obfuscation core.
5. **Cleanup.** Remove the 6 `xfail` markers once passing.

## 4. Affected components

- New `pipeline/nodes/normalize.py`; wiring in
  [`graph.py`](../../apps/proxy-service/src/pipeline/graph.py)
- `pipeline/state.py` (new `normalized_message` field)
- `intent.py` / scanners consume the normalized variant
- `tests/test_scenario_deterministic.py` (drop `xfail`)

## 5. Acceptance criteria

- [ ] PLY-106, PLY-108, PLY-115, PLY-134, AGT-065, AGT-066 pass without `xfail`.
- [ ] FPR on the benign corpus is unchanged (no over-eager decoding blocks).
- [ ] Added latency is negligible (string ops only; target < 2 ms p50).
- [ ] The same normalization is reusable by B1 (tool/RAG content).

## 6. Out of scope

- The ML classifier itself (A1). A2 makes obfuscated text *legible* to whatever
  classifier runs next.

## 7. Risks / open questions

- Candidate-decode explosion (multiple ROT shifts × base64 × hex) — cap the
  number of variants and only escalate on an independent detector hit.
- Homoglyph tables and confusables data — pick a maintained source.
