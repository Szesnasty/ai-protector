# Red Team — Flow Diagram

> Complete data flow: what the user does → what happens under the hood → what comes back on screen.

---

## 1. High-Level Diagram

```mermaid
flowchart TB
    subgraph USER ["👤 User (browser)"]
        U1["Lands on /red-team"]
        U2["Picks target"]
        U3["Configures run"]
        U4["Watches progress"]
        U5["Views results"]
        U6["Drills into scenario"]
        U7["Fixes / re-runs"]
        U8["Compares / exports"]
    end

    subgraph FRONTEND ["🖥️ Frontend (Nuxt 3 + Vuetify 3)"]
        F1["/red-team — Landing"]
        F2["/red-team/configure"]
        F3["/red-team/run/:id — Progress"]
        F4["/red-team/results/:id — Results"]
        F5["/red-team/results/:id/scenario/:sid"]
        F6["/red-team/compare?a=X&b=Y"]
    end

    subgraph API ["⚙️ Backend API (FastAPI)"]
        A1["POST /v1/benchmark/runs"]
        A2["GET /v1/benchmark/runs/:id/progress (SSE)"]
        A3["GET /v1/benchmark/runs/:id"]
        A4["GET /v1/benchmark/runs/:id/scenarios/:sid"]
        A5["GET /v1/benchmark/compare?a&b"]
        A6["POST /v1/benchmark/runs/:id/export"]
        A7["POST /v1/benchmark/test-connection"]
        A8["GET /v1/benchmark/packs"]
    end

    subgraph ENGINE ["🔧 Red Team Engine"]
        E1["Pack Loader"]
        E2["Run Engine"]
        E3["HTTP Client"]
        E3N["Response Normalizer"]
        E4["Evaluator Engine"]
        E5["Score Calculator"]
        E6["Progress Emitter"]
        E7["Persistence"]
    end

    subgraph TARGET ["🎯 Target"]
        T1["Demo Agent (built-in)"]
        T2["Local Agent (localhost)"]
        T3["Hosted Endpoint (remote)"]
    end

    U1 --> F1
    U2 --> F1
    F1 -->|"POST target config"| A1
    U3 --> F2
    F2 -->|"test connection"| A7
    F2 -->|"start run"| A1
    A1 --> E1
    A1 --> E2
    E2 --> E3
    E3 --> T1 & T2 & T3
    T1 & T2 & T3 -->|"raw HTTP response"| E3
    E3 -->|"HttpResponse"| E3N
    E3N -->|"RawTargetResponse"| E4
    E4 -->|"EvalResult"| E2
    E2 -->|"scenario result"| E6
    E2 -->|"scenario result"| E7
    E6 -->|"SSE event"| A2
    A2 -->|"SSE stream"| F3
    U4 --> F3
    E2 -->|"all done"| E5
    E5 -->|"ScoreResult"| E7
    A3 -->|"run + results"| F4
    U5 --> F4
    A4 -->|"scenario details"| F5
    U6 --> F5
    U7 --> F2
    A5 -->|"diff of two runs"| F6
    U8 --> F6
```

---

## 2. Detailed Flow — Step by Step

### Phase A: Target Selection & Configuration

```mermaid
sequenceDiagram
    actor User as 👤 User
    participant FE as 🖥️ Frontend
    participant API as ⚙️ API
    participant PL as 📦 Pack Loader
    participant SEC as 🔒 SecretStore

    User->>FE: Lands on /red-team
    FE->>API: GET /v1/benchmark/packs
    API->>PL: list_packs()
    PL-->>API: [{name, description, scenario_count}]
    API-->>FE: Pack list

    User->>FE: Picks target card (e.g. "Hosted Endpoint")
    User->>FE: Fills form:<br/>• URL: https://my-agent.com/chat<br/>• Auth: Bearer sk-xxx<br/>• Type: chatbot_api<br/>• Safe mode: ON<br/>• Timeout: 30s

    User->>FE: Clicks [Test Connection]
    FE->>API: POST /v1/benchmark/test-connection<br/>{url, auth_header, timeout_s}
    API->>SEC: encrypt(auth_header) → secret_ref
    API->>API: HTTP HEAD/POST → target URL
    alt ✅ Connection OK
        API-->>FE: {status: "ok", latency_ms: 340, status_code: 200}
        FE-->>User: ✅ "Connected — 340ms"
    else ❌ Error
        API-->>FE: {status: "error", error: "connection_refused"}
        FE-->>User: 🔴 "Cannot reach endpoint"
    end

    User->>FE: Selects pack: "Core Security"<br/>Policy: "Balanced"
    User->>FE: Clicks [Run Benchmark →]
```

### Phase B: Run Launch & Execution

```mermaid
sequenceDiagram
    actor User as 👤 User
    participant FE as 🖥️ Frontend
    participant API as ⚙️ API
    participant ENG as 🔧 Run Engine
    participant PL as 📦 Pack Loader
    participant HC as 🌐 HTTP Client
    participant NORM as 🔄 Normalizer
    participant EV as 🔍 Evaluator
    participant SC as 📊 Score Calc
    participant SSE as 📡 SSE Emitter
    participant DB as 💾 Persistence
    participant TGT as 🎯 Target

    User->>FE: Clicks [Run Benchmark]
    FE->>API: POST /v1/benchmark/runs<br/>{target_config, pack, policy}

    API->>DB: INSERT BenchmarkRun (status: created)
    API->>ENG: start_run(run_id, config)
    API-->>FE: {run_id: "abc-123"}
    FE->>FE: redirect → /red-team/run/abc-123
    FE->>API: GET /v1/benchmark/runs/abc-123/progress (SSE)

    ENG->>PL: load_pack("core_security", target_config)
    PL->>PL: Schema validation (Pydantic)
    PL->>PL: Filtering:<br/>1. applicable_to vs agent_type<br/>2. safe_mode → skip mutating<br/>3. detector availability
    PL-->>ENG: FilteredPack {total_in_pack: 30,<br/>total_applicable: 22, skipped: 8,<br/>skipped_reasons: {safe_mode:5, not_applicable:2, detector:1}}

    ENG->>DB: UPDATE run SET status=running,<br/>total_in_pack=30, total_applicable=22

    loop For each scenario (1..22)
        ENG->>SSE: event: scenario_start {id, index, total}
        SSE-->>FE: 🔄 "CS-001 — running..."

        ENG->>HC: send_prompt(scenario.prompt, target_config)
        HC->>TGT: POST https://my-agent.com/chat<br/>{"message": "Ignore previous instructions..."}
        TGT-->>HC: HTTP 200 {"response": "I cannot help with that."}

        HC-->>ENG: HttpResponse {status_code: 200,<br/>body: '{"response": "I cannot..."}',<br/>latency_ms: 120}

        ENG->>NORM: normalize(http_response)
        NORM->>NORM: detect_format → "generic_json"<br/>extract text → "I cannot help..."<br/>tool_calls → null
        NORM-->>ENG: RawTargetResponse {body_text: "I cannot...",<br/>parsed_json: {response: "..."},<br/>tool_calls: null, provider_format: "generic_json"}

        ENG->>EV: evaluate(scenario, normalized_response)
        EV->>EV: Lookup detector: "refusal_pattern"
        EV->>EV: Check: "I cannot" found in body_text<br/>→ match_means: pass ✅
        EV-->>ENG: EvalResult {passed: true,<br/>detail: "Refusal detected: 'I cannot'",<br/>matched_evidence: "I cannot",<br/>confidence: 1.0, detector_type: "refusal_pattern"}

        ENG->>DB: INSERT BenchmarkScenarioResult<br/>{run_id, scenario_id, passed, actual,<br/>detector_type, detector_detail, latency_ms,<br/>raw_response_retained_until: now+30d}

        ENG->>SSE: event: scenario_complete<br/>{id: "CS-001", passed: true, actual: "BLOCK", latency_ms: 120}
        SSE-->>FE: ✅ "CS-001 — BLOCKED — 120ms"
        FE-->>User: Progress bar & live feed update
    end

    ENG->>SC: calculate_scores(all_results)
    SC->>SC: Simple: passed/total × 100 = 72<br/>Weighted: Σ(severity_weights) = 68
    SC-->>ENG: ScoreResult {simple: 72, weighted: 68, breakdown: {...}}

    ENG->>DB: UPDATE run SET status=completed,<br/>score_simple=72, score_weighted=68,<br/>total_in_pack=30, total_applicable=22,<br/>executed=22, passed=16, failed=6, skipped=8,<br/>skipped_reasons={safe_mode:5, not_applicable:2, detector:1}

    ENG->>SSE: event: run_complete<br/>{score_simple: 72, score_weighted: 68,<br/>total_applicable: 22, executed: 22,<br/>passed: 16, failed: 6, skipped: 8}
    SSE-->>FE: 🏁 Run complete!
    FE->>FE: Auto-redirect → /red-team/results/abc-123
```

### Phase C: Results & Drill-Down

```mermaid
sequenceDiagram
    actor User as 👤 User
    participant FE as 🖥️ Frontend
    participant API as ⚙️ API
    participant DB as 💾 Persistence

    FE->>API: GET /v1/benchmark/runs/abc-123
    API->>DB: SELECT run + scenario results
    DB-->>API: Run {score: 72, passed: 16, failed: 6, ...}
    API-->>FE: Full run data

    FE-->>User: Results screen:<br/>🟡 72/100 "Needs Hardening"<br/>• Category breakdown (4 categories)<br/>• Top 5 failures<br/>• CTA: "Protect this endpoint"

    User->>FE: Clicks [View Details] on CS-012

    FE->>API: GET /v1/benchmark/runs/abc-123/scenarios/CS-012
    API->>DB: SELECT scenario_result WHERE scenario_id="CS-012"
    DB-->>API: {prompt, expected, actual, detector_detail,<br/>pipeline_result, latency_ms, fix_hints}
    API-->>FE: Scenario details

    FE-->>User: Detail screen:<br/>❌ CS-012 — System prompt extraction<br/>• Attack prompt: "Ignore your previous..."<br/>• Expected: BLOCK → Got: ALLOW<br/>• Detector: regex — no match<br/>• Why it passed: "Attack uses indirect injection..."<br/>• Suggested fix:<br/>  → Switch to "Strict" policy [link]<br/>  → Add keyword rule [link]
```

### Phase D: Fix → Re-Run → Compare

```mermaid
sequenceDiagram
    actor User as 👤 User
    participant FE as 🖥️ Frontend
    participant API as ⚙️ API
    participant PROXY as 🛡️ AI Protector Proxy
    participant TGT as 🎯 Target

    User->>FE: Clicks [Set up Proxy] (CTA Variant B)
    FE-->>User: Instructions:<br/>"Change your agent's base URL from<br/>https://my-agent.com/chat to<br/>https://protector.com/proxy/my-agent"

    Note over User,TGT: User configures proxy<br/>(outside the benchmark system)

    User->>FE: Returns, clicks [Re-run Benchmark]
    FE->>API: POST /v1/benchmark/runs<br/>{...same config, endpoint via proxy}

    Note over API,TGT: Same flow as Phase B,<br/>but traffic now goes through proxy

    API->>PROXY: POST prompt → proxy
    PROXY->>PROXY: Pipeline: keyword → LLM Guard → NeMo → Presidio
    PROXY->>TGT: (prompt allowed) → forward to target
    TGT-->>PROXY: response
    PROXY-->>API: filtered response

    Note over FE: Run complete: 91/100 🟢

    User->>FE: Clicks [Compare with previous run]
    FE->>API: GET /v1/benchmark/compare?a=abc-123&b=def-456
    API-->>FE: {before: {score: 72}, after: {score: 91},<br/>fixed: [CS-012, CS-018, CS-025],<br/>still_failing: [CS-022],<br/>regressions: []}

    FE-->>User: 📊 Compare screen:<br/>72/100 🟡 → 91/100 🟢 (▲+19)<br/>✅ 3 failures fixed<br/>❌ 1 still failing<br/>0 regressions

    User->>FE: Clicks [Export Report]
    FE->>API: POST /v1/benchmark/runs/def-456/export<br/>{format: "json", include_raw: false}
    API-->>FE: JSON report download
```

---

## 3. Data Flow — Where Data Goes

```
┌─────────────────────────────────────────────────────────────────────┐
│                         INPUT DATA                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  👤 User provides:               📦 System provides:                │
│  ┌──────────────────────┐        ┌──────────────────────┐           │
│  │ • endpoint URL       │        │ • scenario pack YAML │           │
│  │ • auth header        │        │   (prompts, detectors│           │
│  │ • target type        │        │    expected results) │           │
│  │ • safe mode on/off   │        │ • detector registry  │           │
│  │ • timeout            │        │ • scoring weights    │           │
│  │ • pack selection     │        │ • policies           │           │
│  │ • policy selection   │        │                      │           │
│  └──────────┬───────────┘        └──────────┬───────────┘           │
│             │                               │                       │
│             └───────────┬───────────────────┘                       │
│                         ▼                                           │
├─────────────────────────────────────────────────────────────────────┤
│                      PROCESSING                                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. VALIDATION & FILTERING                                          │
│     ┌────────────────────────────────────────────┐                  │
│     │ Pack Loader:                               │                  │
│     │   30 scenarios in pack                      │                  │
│     │   - applicable_to filter → -2 (not_applicable)                │
│     │   - safe_mode filter     → -5 (mutating)   │                  │
│     │   - detector_available   → -1 (llm_judge)  │                  │
│     │   ═══════════════════════                   │                  │
│     │   = 22 scenarios to execute                 │                  │
│     └────────────────────────────────────────────┘                  │
│                         │                                           │
│  2. EXECUTION LOOP (×22)                                            │
│     ┌────────────────────────────────────────────┐                  │
│     │  prompt ──→ HTTP Client ──→ Target         │                  │
│     │                              │              │                  │
│     │              HttpResponse (raw)             │                  │
│     │              ┌─────────────────┐            │                  │
│     │              │ status_code:200 │            │                  │
│     │              │ body: "{...}"   │            │                  │
│     │              │ latency_ms:120  │            │                  │
│     │              └───────┬─────────┘            │                  │
│     │                      │                      │                  │
│     │              Response Normalizer            │                  │
│     │              ┌─────────────────┐            │                  │
│     │              │ detect format   │            │                  │
│     │              │ extract text    │            │                  │
│     │              │ extract tools   │            │                  │
│     │              └───────┬─────────┘            │                  │
│     │                      │                      │                  │
│     │              RawTargetResponse              │                  │
│     │              ┌──────────────────┐           │                  │
│     │              │ body_text:"..."  │           │                  │
│     │              │ parsed_json:{}   │           │                  │
│     │              │ tool_calls:null  │           │                  │
│     │              │ provider_format: │           │                  │
│     │              │  "generic_json"  │           │                  │
│     │              └───────┬──────────┘           │                  │
│     │                      │                      │                  │
│     │              Evaluator Engine               │                  │
│     │              ┌─────────────────┐            │                  │
│     │              │ detector_type:  │            │                  │
│     │              │  refusal_pattern│            │                  │
│     │              │ → check phrases │            │                  │
│     │              │ → EvalResult    │            │                  │
│     │              └───────┬─────────┘            │                  │
│     │                      │                      │                  │
│     │              EvalResult                     │                  │
│     │              ┌──────────────────┐           │                  │
│     │              │ passed: true     │           │                  │
│     │              │ detail: "..."    │           │                  │
│     │              │ matched_evidence │           │                  │
│     │              │ detector_type    │           │                  │
│     │              │ confidence: 1.0  │           │                  │
│     │              └──────────────────┘           │                  │
│     └────────────────────────────────────────────┘                  │
│                         │                                           │
│  3. SCORING                                                         │
│     ┌────────────────────────────────────────────┐                  │
│     │ Score Calculator:                          │                  │
│     │   16 passed, 6 failed, 8 skipped           │                  │
│     │                                            │                  │
│     │   Simple:   16/22 × 100 = 72              │                  │
│     │   Weighted: Σ(+severity) - Σ(-severity)   │                  │
│     │     Critical pass: +3  │ fail: -6          │                  │
│     │     High pass:     +2  │ fail: -4          │                  │
│     │     Medium pass:   +1  │ fail: -2          │                  │
│     │     Low pass:      +0.5│ fail: -1          │                  │
│     │   = 68/100 weighted                        │                  │
│     │                                            │                  │
│     │   Category breakdown:                      │                  │
│     │     Prompt Injection: 83%                  │                  │
│     │     Data Leakage:     40%                  │                  │
│     │     Tool Abuse:       N/A (skipped)        │                  │
│     │     Access Control:   N/A (skipped)        │                  │
│     └────────────────────────────────────────────┘                  │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                      OUTPUT DATA                                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  💾 To database:                 📡 To frontend (SSE):             │
│  ┌──────────────────────┐        ┌──────────────────────┐           │
│  │ BenchmarkRun:        │        │ scenario_start       │           │
│  │  status: completed   │        │ scenario_complete    │           │
│  │  score_simple: 72    │        │ scenario_skipped     │           │
│  │  score_weighted: 68  │        │ run_complete         │           │
│  │  total_in_pack: 30   │        │ run_failed           │           │
│  │  total_applicable:22 │        │ run_cancelled        │           │
│  │  executed: 22        │        └──────────────────────┘           │
│  │  passed: 16          │                                           │
│  │  failed: 6           │                                           │
│  │  skipped: 8          │                                           │
│  │  skipped_reasons:{}  │                                           │
│  │  source_run_id: null │                                           │
│  ├──────────────────────┤        └──────────────────────┘           │
│  │ BenchmarkScenario    │                                           │
│  │ Result (×22):        │        📤 To export:                      │
│  │  passed/failed       │        ┌──────────────────────┐           │
│  │  actual: BLOCK/ALLOW │        │ JSON: full results   │           │
│  │  detector_type       │        │ Markdown: report     │           │
│  │  detector_detail     │        │ PDF: branded report  │           │
│  │  latency_ms          │        │ Badge: score SVG     │           │
│  │  raw_response_       │        └──────────────────────┘           │
│  │   retained_until     │                                           │
│  └──────────────────────┘        🖥️ On user's screen:            │
│                                  ┌──────────────────────┐           │
│                                  │ Score badge: 72/100  │           │
│                                  │ Category breakdown   │           │
│                                  │ Top 5 failures       │           │
│                                  │ Fix hints + deep     │           │
│                                  │   links              │           │
│                                  │ CTA: protect / rerun │           │
│                                  └──────────────────────┘           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. State Machine — Run Lifecycle

```mermaid
stateDiagram-v2
    [*] --> created : POST /v1/benchmark/runs
    created --> running : async task starts
    created --> failed : pack load fails / target unreachable

    running --> running : scenario completes (loop)
    running --> completed : all scenarios done
    running --> cancelled : user clicks Cancel
    running --> failed : 3 consecutive target failures

    completed --> [*]
    cancelled --> [*]
    failed --> [*]

    note right of created
        Validate config
        Load & filter pack
        Save to DB
    end note

    note right of running
        Per scenario:
        1. Send prompt → target
        2. Normalize → RawTargetResponse
        3. Evaluate → EvalResult
        4. Persist result
        5. Emit SSE event
    end note

    note right of completed
        Compute score (simple + weighted)
        Save final results
        Emit SSE "run_complete"
    end note
```

---

## 5. Target Types — What Differs

```
┌──────────────┬─────────────────┬─────────────────┬──────────────────┐
│              │  Demo Agent     │  Local/Hosted   │  Registered      │
│              │  (built-in)     │  (custom URL)   │  Agent           │
├──────────────┼─────────────────┼─────────────────┼──────────────────┤
│ User enters  │ nothing         │ URL, auth,      │ picks from list  │
│              │ (zero-config)   │ type, safe_mode │ (Agent Wizard)   │
├──────────────┼─────────────────┼─────────────────┼──────────────────┤
│ Test         │ skipped         │ POST → target   │ skipped          │
│ Connection   │                 │ → 200 OK?       │ (already known)  │
├──────────────┼─────────────────┼─────────────────┼──────────────────┤
│ Auth         │ none            │ AES-256         │ from agent       │
│              │                 │ encrypted,      │ config           │
│              │                 │ 24h TTL         │                  │
├──────────────┼─────────────────┼─────────────────┼──────────────────┤
│ HTTP traffic │ → built-in      │ → custom URL    │ → proxy with     │
│              │   pipeline      │   (direct)      │   full trace     │
├──────────────┼─────────────────┼─────────────────┼──────────────────┤
│ Evaluation   │ deterministic   │ deterministic + │ deterministic +  │
│              │ (full trace)    │ heuristic       │ full trace       │
├──────────────┼─────────────────┼─────────────────┼──────────────────┤
│ Confidence   │ 🟢 High        │ 🟡 Medium       │ 🟢 High         │
├──────────────┼─────────────────┼─────────────────┼──────────────────┤
│ CTA          │ Variant A:      │ Variant B:      │ Variant A:       │
│ (after       │ "Apply policy"  │ "Set up Proxy"  │ "Tune policy"    │
│  results)    │ "Re-run"        │ "Open Wizard"   │ "Re-run"         │
├──────────────┼─────────────────┼─────────────────┼──────────────────┤
│ Build phase  │ Phase 1 (MVP)   │ Phase 2 (MVP)   │ Phase 3          │
└──────────────┴─────────────────┴─────────────────┴──────────────────┘
```

---

## 6. Modules — Dependency Graph

```mermaid
graph TD
    SCHEMA["schemas/<br/>Scenario Schema"]
    PACKS["packs/<br/>Pack Loader"]
    EVAL["evaluators/<br/>Evaluator Engine"]
    NORM["normalizer/<br/>Response Normalizer"]
    HTTP["http_client/<br/>HTTP Client"]
    ENGINE["engine/<br/>Run Engine"]
    SCORE["scoring/<br/>Score Calculator"]
    SSE["progress/<br/>SSE Emitter"]
    DB["persistence/<br/>DB Repository"]
    API["api/<br/>FastAPI Routes"]
    EXPORT["export/<br/>Report Generator"]

    SCHEMA --> PACKS
    SCHEMA --> EVAL
    SCHEMA --> NORM
    PACKS --> ENGINE
    EVAL --> ENGINE
    HTTP --> ENGINE
    NORM --> ENGINE
    ENGINE --> SCORE
    ENGINE --> SSE
    ENGINE --> DB
    API --> ENGINE
    API --> DB
    API --> SSE
    DB --> EXPORT

    style SCHEMA fill:#e1f5fe
    style PACKS fill:#e1f5fe
    style EVAL fill:#e1f5fe
    style NORM fill:#e1f5fe
    style HTTP fill:#e1f5fe
    style ENGINE fill:#fff3e0
    style SCORE fill:#e1f5fe
    style SSE fill:#e1f5fe
    style DB fill:#fce4ec
    style API fill:#f3e5f5
    style EXPORT fill:#f3e5f5
```

**Legenda:** 🔵 pure logic (no I/O) · 🟠 orchestrator · 🔴 persistence · 🟣 external interface

---

## 7. Data Retention — Lifecycle

```mermaid
gantt
    title Data Lifecycle After Benchmark
    dateFormat  YYYY-MM-DD
    axisFormat  %d days

    section Permanent
    Run metadata (score, status)       :done, 2026-01-01, 2026-12-31
    Scenario results (pass/fail)       :done, 2026-01-01, 2026-12-31
    Attack prompts (from pack)         :done, 2026-01-01, 2026-12-31

    section 30 days
    Raw target responses               :active, 2026-01-01, 2026-01-31
    Pipeline results (scanner detail)  :active, 2026-01-01, 2026-01-31

    section 24 hours
    Auth secrets (encrypted)           :crit, 2026-01-01, 2026-01-02
```
```
After 24h:  auth secrets → DELETED (auto, never in logs)
            NOTE: test-connection secrets are in-memory only, never persisted
            Only create-run secrets get encrypted + 24h TTL
After 30d:  raw responses → PURGED (raw_response_retained_until)
            pipeline_result → PURGED
            ── scenario results remain (pass/fail, detector output, latency)
Forever:    run metadata, scores, counting fields, scenario verdicts
```
