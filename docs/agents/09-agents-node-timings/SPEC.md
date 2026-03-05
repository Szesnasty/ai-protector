# 09 — Node Timings / Performance Attribution

> **Priority:** 9
> **Depends on:** 07-Agent Trace (timing data stored in trace)
> **Consumed by:** analytics dashboard, policy tuning decisions

---

## 1. Goal

Understand the cost of each protection layer and agent loop step to make informed policy choices (fast vs strict).

**Current state:** `AgentState` has a `node_timings: dict[str, float]` field, but it's only partially populated and not persisted or aggregated. This spec makes timing a first-class feature with persistence, aggregation, and alerting.

---

## 2. How It Works

### 2.1. What Gets Measured

Every node in the agent graph is timed:

| Node | Typical Time | What Drives Cost |
|------|-------------|------------------|
| `input_node` | 1–5 ms | Input sanitization |
| `intent_node` | 2–10 ms | Intent classification (keyword/regex) |
| `policy_check_node` | 1–3 ms | RBAC lookup |
| `tool_router_node` | 1–5 ms | Tool selection logic |
| `pre_tool_gate` | 2–15 ms | RBAC + schema + intent analysis |
| `tool_executor_node` | 5–500 ms | Actual tool execution (network/DB) |
| `post_tool_gate` | 10–50 ms | Presidio PII scan + injection scan |
| `llm_call_node` | 200–5000 ms | LLM inference (dominates total) |
| `response_node` | 1–3 ms | Response formatting |
| `memory_node` | 1–5 ms | History management |

### 2.2. Measurement Method

Each node is wrapped with a timing decorator or explicit start/stop:

```python
import time

def timed_node(node_name: str):
    """Decorator that measures node execution time."""
    def decorator(func):
        def wrapper(state: AgentState) -> AgentState:
            start = time.perf_counter()
            result = func(state)
            duration_ms = (time.perf_counter() - start) * 1000

            # Update timings in state
            timings = dict(result.get("node_timings", {}))
            timings[node_name] = round(duration_ms, 2)
            result["node_timings"] = timings

            return result
        return wrapper
    return decorator

# Usage:
@timed_node("pre_tool_gate")
def pre_tool_gate_node(state: AgentState) -> AgentState:
    ...
```

### 2.3. Timing Breakdown in Response

The agent `/agent/chat` response includes timing data:

```json
{
  "response": "Your order ORD-001 has been shipped...",
  "timings": {
    "total_ms": 1250,
    "breakdown": {
      "input": 3,
      "intent": 5,
      "policy_check": 2,
      "tool_router": 1,
      "pre_tool_gate": 8,
      "tool_executor": 45,
      "post_tool_gate": 22,
      "llm_call": 1150,
      "response": 2,
      "memory": 3
    },
    "overhead_ms": 91,
    "overhead_pct": 7.3
  }
}
```

`overhead_ms` = total - llm_call - tool_executor (the "security tax").

---

## 3. Aggregation

### 3.1. Per-Request Metrics

Stored in agent trace (point 7) and optionally in a dedicated metrics table:

```python
class RequestTimingRecord(BaseModel):
    """Timing data for a single request."""
    session_id: str
    request_id: str
    total_ms: float
    llm_ms: float
    tool_ms: float
    overhead_ms: float          # Security pipeline overhead
    overhead_pct: float
    node_timings: dict[str, float]
    created_at: datetime
```

### 3.2. Aggregate Metrics

Periodic aggregation (every minute or on-demand) computes:

```python
class TimingAggregates(BaseModel):
    """Aggregated timing statistics."""
    period: str                          # "1h", "24h", "7d"
    request_count: int
    total_ms: PercentileStats            # p50, p95, p99
    llm_ms: PercentileStats
    overhead_ms: PercentileStats
    overhead_pct: PercentileStats
    per_node: dict[str, PercentileStats] # Per-node breakdown

class PercentileStats(BaseModel):
    p50: float
    p95: float
    p99: float
    avg: float
    max: float
```

---

## 4. Alerting

### 4.1. Threshold Alerts

```python
class TimingAlertConfig(BaseModel):
    """Alert thresholds for node timings."""
    max_total_ms: int = 5000              # Alert if total > 5s
    max_overhead_pct: float = 20.0        # Alert if overhead > 20%
    per_node_max_ms: dict[str, int] = {
        "pre_tool_gate": 50,
        "post_tool_gate": 100,
        "llm_call": 10000,
    }
```

### 4.2. Alert Logging

When a threshold is exceeded:

```json
{
  "event": "timing_alert",
  "alert_type": "node_slow",
  "node": "post_tool_gate",
  "duration_ms": 150,
  "threshold_ms": 100,
  "session_id": "sess-123",
  "severity": "warning"
}
```

---

## 5. API

### 5.1. Per-Request Timings

Included in agent chat response (see section 2.3).

### 5.2. Aggregate Endpoint

```
GET /agent/analytics/timings?period=24h
```

Response:
```json
{
  "period": "24h",
  "request_count": 1250,
  "total_ms": {"p50": 950, "p95": 2500, "p99": 4200, "avg": 1100, "max": 8500},
  "overhead_ms": {"p50": 45, "p95": 120, "p99": 250, "avg": 65, "max": 400},
  "overhead_pct": {"p50": 4.5, "p95": 12.0, "p99": 18.0, "avg": 6.2, "max": 25.0},
  "per_node": {
    "pre_tool_gate": {"p50": 5, "p95": 15, "p99": 30, "avg": 7, "max": 45},
    "post_tool_gate": {"p50": 18, "p95": 50, "p99": 85, "avg": 22, "max": 150},
    "llm_call": {"p50": 850, "p95": 2200, "p99": 3800, "avg": 980, "max": 8000}
  }
}
```

---

## 6. Integration Points

| Integration | How |
|-------------|-----|
| **Agent trace** (07) | `node_timings` included in every trace entry |
| **Deterministic tests** (08) | Timing data helps identify slow test scenarios |
| **Limits** (06) | Timeout limit per node could be enforced (future) |
| **Analytics dashboard** | Frontend displays timing heatmap and percentile charts |
| **Langfuse** | Span duration already tracked; this adds structured agent-level data |

---

## 7. Overhead Analysis

The "security overhead" metric is key for policy decisions:

```
Security Overhead = total_ms - llm_call_ms - tool_executor_ms

Example (strict policy):
  Total:          1250 ms
  LLM call:       1050 ms
  Tool execution:   45 ms
  ─────────────────────
  Overhead:        155 ms (12.4%)
    pre_tool_gate:    8 ms
    post_tool_gate:  22 ms
    input_sanitize:   3 ms
    intent:           5 ms
    other nodes:    117 ms
```

This allows comparing policies: "strict adds 155ms overhead vs fast's 15ms — is the extra PII scanning worth it for this use case?"

---

## 8. Definition of Done

- [ ] `timed_node` decorator for automatic node timing
- [ ] All agent nodes wrapped with timing measurement
- [ ] `node_timings` populated in `AgentState` for every request
- [ ] Timing breakdown included in `/agent/chat` response
- [ ] `overhead_ms` and `overhead_pct` calculated
- [ ] `RequestTimingRecord` persisted (in trace or dedicated table)
- [ ] Aggregate computation (p50/p95/p99 per node)
- [ ] `GET /agent/analytics/timings` endpoint
- [ ] Alerting: log warnings when thresholds exceeded
- [ ] Structured logging for all timing events
- [ ] Unit tests: timing decorator works correctly
- [ ] Integration test: full flow produces valid timing breakdown
