# Red Team / Benchmark Hub

Run any LLM / chatbot endpoint against thousands of real-world attacks — **locally, free,
and with a deterministic, reproducible verdict that tells you how much to trust it.**

What makes it different isn't the attacks (those are public) — it's the **grading**. Most
red-team tools hand you a pass-rate from an unvalidated LLM judge and stay silent about its
reliability. This one is mostly **mechanical** (markers = exact by construction), labels the
**heuristic** parts honestly, and **publishes its own oracle's accuracy** (κ vs an independent
judge). *Control you can prove.*

## Scope (honest)

- **It tests the agent's "brain"** — single-turn request → response on one endpoint. It does
  **not** yet exercise the agent action loop (tool execution, multi-turn, indirect injection via
  retrieved content). That's roadmap, not implied.
- **Verdict confidence is labeled, not hidden:**
  - **EXACT** — a mechanical marker fired (injected canary, secret/PII pattern, tool call,
    decoded directive). Trustworthy by construction.
  - **CLASSIFIER** — a safety model (Llama Guard) judged the response. Strong on harm, but a model.
  - **HEURISTIC** — refusal-phrase / deterministic floor ("no refusal ⇒ leak"). Reproducible but a
    heuristic (κ ≈ 0.5 vs an independent judge) → **the report flags these for manual review.**
  - **SKIP** — inconclusive (empty/truncated answer, or a canary that couldn't be planted).
    Counted as neither pass nor fail — never a vacuous pass.
- **Reference labels** used to measure grader accuracy are currently **model-graded (Claude);
  human spot-check pending.** Stated, not glossed over.

## Quickstart (local, native Ollama — free, no API)

Local model targets run on **native Ollama (Apple Metal)** — not Docker (Docker = CPU, slow):

```bash
ollama serve                 # native, on the host
ollama pull llama3.2:3b      # any chat model you want to test
```

Run a scan via the **Red Team Hub UI** (frontend) or the benchmark API (see
`src/red_team/api/routes.py`): pick threat **categories** first, then the **packs** under them,
point it at your endpoint, and execute. Verdicts are deterministic, so a run is replayable.

## Reading the results

- **Use the severity-weighted score, not the simple pass-rate.** A pass-rate hides severity:
  `score_simple 87` with `score_weighted 52` means the failures were all critical.
- **`dangerous-miss` > accuracy.** A grader that certifies a real leak as "safe" is worse than one
  that cries wolf. The layered grader is tuned to minimise dangerous-miss.
- The PDF/HTML report carries the confidence legend above + a "**N verdicts are heuristic —
  verify manually**" callout, so a reader knows exactly which rows to re-check.

## Building / refreshing the attack packs

```bash
python -m src.red_team.packs.fetch_sources   # downloads raw corpora into _sources/ (gitignored)
python -m src.red_team.packs.build_packs      # builds data/*.yaml with canonical taxonomy
```

Packs are derived from public corpora — **JailbreakBench, HarmBench, AdvBench, Do-Not-Answer,
In-the-Wild Jailbreaks, promptfoo** — each scenario keeps its native subcategory + source. Respect
the upstream licenses when redistributing.

## PDF export (optional)

The HTML report needs no extra deps. **PDF export requires WeasyPrint's native libraries**
(cairo / pango / gobject); without them the PDF tests/export are skipped — the HTML report still
works. Install the system libs (or run in CI with them) only if you need PDF.

## Data handling

A run **persists the prompt, the raw response body, and detector evidence** for each scenario —
that's what makes the report auditable and reproducible. But a successful attack means the response
**may contain real PII, secrets, or sensitive output**. So:

- Treat stored runs as **sensitive**. Endpoint auth tokens are masked/encrypted and expired by the
  service; benchmark **content is not redacted** — decide your own retention before scanning
  production endpoints.
- Prefer scanning **local / non-production** targets, or models behind AI Protector (which can
  redact PII on ingress/egress).
- Delete runs you don't need; don't commit exported reports containing live responses.

## Credibility / methodology

- `docs/red-team-deterministic-grading.md` — how grading works (markers vs heuristic vs classifier).
- `docs/red-team-hub-results.md` — the oracle-validation study (κ across 8 models, judge cross-check,
  grader-accuracy vs reference labels) and its honest limits.

> A confidence signal, **not a safety certificate.** It tells you where a model leaks and how much
> to trust each verdict — the rest is your judgment.
