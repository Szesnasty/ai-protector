# A1 — ML Intent Classifier

> **Track:** A (detection credibility)
> **Tracks issue:** ISS-005
> **Priority:** High
> **Effort:** M–L
> **Status:** ✅ Implemented — `src/pipeline/nodes/jailbreak_ml.py`

---

## Implementation note

Shipped as a `jailbreak_ml` scanner node using `madhurjindal/Jailbreak-Detector`
(DistilBERT, public, ~270 MB, CPU-friendly). It runs on `scan_text` (so it also
benefits from A2), labels the prompt `jailbreak`/`benign`, and contributes
`score × jailbreak_ml_weight` (0.8) to the risk score. Enabled in
balanced/strict/paranoid policies; lazy-loaded + preloaded at startup.

**Result (JailbreakBench): 81.2% → 99.1%** — PAIR (roleplay) **53.6% → 97.9%**,
GCG 77% → 99%. The model itself produced **0 false positives** across 24
benign + dual-use prompts (security questions, benign roleplay). Chosen after an
empirical bake-off: it caught 59/60 real PAIR prompts with 0 benign FPs.

**Follow-up:** 3 *pre-existing* keyword-classifier false positives surfaced
("malware"/"ransomware"/"pretend you are" — flagged `suspicious_intent`, not the
ML model). Now that A1 is a high-precision backstop, those brittle keyword
patterns can be relaxed; see the FPR-suppression note in the body.

---

## 1. Goal

Replace the brittle substring-based intent classifier with a lightweight,
on-prem ML classifier so that paraphrased and roleplay-framed attacks are
caught. Today these slip through with `intent=qa, risk=0.00`.

## 2. Current state

[`intent.py`](../../apps/proxy-service/src/pipeline/nodes/intent.py) classifies
via `classify_intent()` — pure `if pattern in text` substring matching over
~15 hand-written pattern lists. Consequences:

- Any paraphrase bypasses it ("reveal your system prompt" vs "show me your
  instructions").
- JailbreakBench PAIR attacks (sophisticated roleplay) land at 88.8% precisely
  because they evade keyword + shallow detection.
- NeMo embeddings only partially compensate, and only for their predefined
  rails.

## 3. Approach (big blocks)

1. **Model selection.** Evaluate candidates against constraints: CPU inference
   < ~80 ms, footprint ~50–250 MB, ONNX-exportable, on-prem (no external
   calls). Candidates: Llama Guard 3 / Prompt Guard 2, a distilled DeBERTa
   injection classifier, or a SetFit few-shot head over a small encoder.
2. **New scanner.** Add an `intent_ml` scanner (new node or extension of the
   intent node) that outputs `{intent_label, confidence, injection_prob}` and
   merges into `risk_flags`. Lazy-load + background preload, mirroring the
   pattern in [`llm_guard.py`](../../apps/proxy-service/src/pipeline/nodes/llm_guard.py)
   and the preload task in [`main.py`](../../apps/proxy-service/src/main.py).
3. **Ensemble, don't rip out.** Keep the keyword layer as a cheap, high-recall
   pre-filter and combine signals (max / weighted) in
   [`decision.py`](../../apps/proxy-service/src/pipeline/nodes/decision.py).
   Keywords stay valuable for explicit, auditable matches.
4. **Policy wiring.** `fast` skips the ML scanner; `balanced`/`strict`/
   `paranoid` enable it via the `nodes` list and per-policy thresholds
   (`injection_weight` already exists in the decision formula).
5. **Eval set.** Assemble train/eval from the internal scenario suite,
   JailbreakBench, and a benign corpus (for FPR). Feeds directly into A3.

## 4. Affected components

- `pipeline/nodes/intent.py`, new `pipeline/nodes/intent_ml.py`
- `pipeline/nodes/scanners.py` (dispatch), `decision.py` (signal fusion)
- `config.py` (kill switch, model path), policy `nodes` lists, `main.py` preload

## 5. Acceptance criteria

- [ ] JailbreakBench PAIR detection improves materially over the 88.8% baseline.
- [ ] The paraphrase cases that currently score `risk=0.00` are caught.
- [ ] Added latency stays within the pipeline budget (target: balanced p50
      stays in the tens of ms, not hundreds).
- [ ] False-positive rate on the benign corpus does **not** regress (measured
      via A3).
- [ ] Model loads via background preload; no cold-start regression.

## 6. Out of scope

- The full comparative/continuous benchmark harness (that's A3).
- Multilingual coverage (A2 handles the obfuscation/language angle).

## 7. Risks / open questions

- Model licensing for redistribution in an Apache-2.0 repo.
- Memory budget: current all-scanners footprint is ~1.1 GB; keep the addition
  modest and quantized/ONNX where possible.
