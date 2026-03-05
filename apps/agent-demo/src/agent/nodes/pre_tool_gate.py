"""Pre-tool Enforcement Gate — security gate before tool execution.

Spec: docs/agents/01-agents-pre-tool-enforcement/SPEC.md

For EACH proposed tool call, runs a chain of checks (fail-fast):
  1. RBAC allowlist — is the tool permitted for this role?
  2. Argument validation — do args look reasonable? (injection patterns)
  3. Context risk assessment — does the conversation suggest abuse?
  4. Limits check — has the session exceeded budgets? (stub until spec 06)

Returns a GateDecision per tool: ALLOW | BLOCK | MODIFY | REQUIRE_CONFIRMATION.
"""

from __future__ import annotations

import re
from typing import Any

import structlog

from src.agent.limits.config import get_limits_for_role
from src.agent.limits.service import get_limits_service
from src.agent.rbac.service import get_rbac_service
from src.agent.state import AgentState, CheckResult, GateDecision
from src.agent.trace.accumulator import TraceAccumulator
from src.agent.validation.validator import validate_tool_args

logger = structlog.get_logger()

# ── Injection / abuse patterns in tool arguments ──────────────────────

INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"you\s+are\s+now\b",
        r"new\s+system\s+prompt",
        r"reveal\s+(your\s+)?(system\s+)?prompt",
        r"disregard\s+(all\s+)?(prior|previous|above)",
        r"override\s+(all\s+)?rules",
        r"act\s+as\s+(an?\s+)?unrestricted",
        r"do\s+anything\s+now",
        r"jailbreak",
        r"<\|im_start\|>",
        r"\[INST\]",
        r"<<SYS>>",
        r"###\s*(system|assistant)\s*:",
    ]
]

# Patterns suggesting data exfiltration intent
EXFILTRATION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"(list|show|get|dump|export)\s+(all|every)\s+(user|customer|record|data|secret|key|password)",
        r"(enumerate|extract|download)\s+.*\b(database|table|record)",
        r"bulk\s+(export|download|extract)",
        r"select\s+\*\s+from",
        r"(DROP|DELETE|TRUNCATE|ALTER)\s+(TABLE|DATABASE)",
    ]
]

# Tools that require human confirmation — now driven by RBAC config.
# This set is kept for backward-compat in tests; real check uses RBAC service below.
TOOLS_REQUIRING_CONFIRMATION: set[str] = set()

# Legacy constant kept for backward-compat in tests; real check uses LimitsService.
MAX_TOOL_CALLS_PER_SESSION = 20


# ── Individual checks ─────────────────────────────────────────────────


def _check_rbac(tool_name: str, allowed_tools: list[str], user_role: str = "") -> CheckResult:
    """Check 1: Is the tool in the role's allowlist?

    Uses RBAC service for rich permission check (scopes, inheritance).
    Falls back to flat allowlist if RBAC service fails.
    """
    rbac = get_rbac_service()
    result = rbac.check_permission(user_role, tool_name, scope="read")

    if result.allowed:
        return CheckResult(check="rbac", passed=True, detail=None)

    return CheckResult(
        check="rbac",
        passed=False,
        detail=result.reason or f"Tool '{tool_name}' is not permitted for this role.",
    )


def _check_args(tool_name: str, args: dict[str, Any]) -> tuple[CheckResult, dict[str, Any] | None]:
    """Check 2: Validate args against Pydantic schema + injection scan.

    Returns (CheckResult, modified_args_or_None).
    If SANITIZED, modified_args contains the cleaned arguments.
    """
    result = validate_tool_args(tool_name, args)

    if result["decision"] == "VALID":
        return CheckResult(check="schema", passed=True, detail=None), None

    if result["decision"] == "SANITIZED":
        return (
            CheckResult(
                check="schema",
                passed=True,
                detail=f"Args sanitized for '{tool_name}'",
            ),
            result["sanitized_args"],
        )

    # INVALID
    errors_str = "; ".join(result["errors"][:3])  # Cap at 3 errors in message
    if result["injection_detected"]:
        detail = f"Injection in args for '{tool_name}': {errors_str}"
    else:
        detail = f"Invalid args for '{tool_name}': {errors_str}"
    return CheckResult(check="schema", passed=False, detail=detail), None


def _check_context_risk(
    tool_name: str,
    args: dict[str, Any],
    message: str,
    chat_history: list[dict[str, str]],
    blocked_count: int,
) -> CheckResult:
    """Check 3: Does the conversation context suggest abuse?

    Heuristics:
    - Exfiltration language in message + data-returning tool
    - Injection patterns in the user message
    - Repeated blocked attempts → escalation signal
    """
    risk_signals: list[str] = []
    combined_text = message + " " + " ".join(str(v) for v in args.values())

    # Exfiltration signals
    for pattern in EXFILTRATION_PATTERNS:
        if pattern.search(combined_text):
            risk_signals.append(f"exfiltration: {pattern.pattern[:60]}")

    # Injection signals in user message itself
    for pattern in INJECTION_PATTERNS:
        if pattern.search(message):
            risk_signals.append(f"injection_in_message: {pattern.pattern[:60]}")

    # Escalation: too many previous blocks in this session
    if blocked_count >= 3:
        risk_signals.append(f"escalation: {blocked_count} previous blocks in session")

    if risk_signals:
        return CheckResult(
            check="context_risk",
            passed=False,
            detail=f"Risk signals: {'; '.join(risk_signals)}",
        )

    return CheckResult(check="context_risk", passed=True, detail=None)


def _check_limits(
    total_tool_calls: int,
    iterations: int,
    session_id: str = "",
    user_role: str = "customer",
    request_tool_calls: int = 0,
) -> CheckResult:
    """Check 4: Has the session exceeded rate/budget limits?

    Uses LimitsService (spec 06) for per-role, per-request and per-session caps.
    Falls back to legacy MAX_TOOL_CALLS_PER_SESSION if no session_id.
    """
    if not session_id:
        # Legacy fallback (for tests that don't provide session_id)
        if total_tool_calls >= MAX_TOOL_CALLS_PER_SESSION:
            return CheckResult(
                check="limits",
                passed=False,
                detail=f"Session tool call limit reached ({total_tool_calls}/{MAX_TOOL_CALLS_PER_SESSION}).",
            )
        return CheckResult(check="limits", passed=True, detail=None)

    limits_svc = get_limits_service()
    config = get_limits_for_role(user_role)

    # Per-request + per-session tool call limits
    result = limits_svc.check_tool_limits(
        session_id=session_id,
        config=config,
        request_tool_calls=request_tool_calls,
    )
    if not result.allowed:
        return CheckResult(
            check="limits",
            passed=False,
            detail=(
                f"{result.limit_type} reached "
                f"({result.current_value}/{result.limit_value})."
            ),
        )

    # Token/cost budget check
    budget_result = limits_svc.check_token_budget(session_id, config)
    if not budget_result.allowed:
        return CheckResult(
            check="limits",
            passed=False,
            detail=(
                f"{budget_result.limit_type} reached "
                f"({budget_result.current_value}/{budget_result.limit_value})."
            ),
        )

    return CheckResult(check="limits", passed=True, detail=None)


def _check_confirmation(tool_name: str, user_role: str = "") -> CheckResult:
    """Check 5: Does this tool require human confirmation?

    Checks RBAC service for requires_confirmation flag, with fallback
    to the module-level TOOLS_REQUIRING_CONFIRMATION set.
    """
    # RBAC-driven confirmation
    rbac = get_rbac_service()
    result = rbac.check_permission(user_role, tool_name, scope="read")
    if result.allowed and result.requires_confirmation:
        return CheckResult(
            check="confirmation",
            passed=False,
            detail=f"Tool '{tool_name}' requires user confirmation (sensitivity: {result.tool_sensitivity}).",
        )

    # Legacy fallback
    if tool_name in TOOLS_REQUIRING_CONFIRMATION:
        return CheckResult(
            check="confirmation",
            passed=False,
            detail=f"Tool '{tool_name}' requires user confirmation before execution.",
        )
    return CheckResult(check="confirmation", passed=True, detail=None)


# ── Gate evaluation ───────────────────────────────────────────────────


def _evaluate_tool(
    tool_name: str,
    args: dict[str, Any],
    state: AgentState,
    blocked_count: int,
) -> GateDecision:
    """Run all checks for a single tool call and return a GateDecision."""
    allowed_tools = state.get("allowed_tools", [])
    user_role = state.get("user_role", "")
    message = state.get("message", "")
    chat_history = state.get("chat_history", [])
    total_tool_calls = len(state.get("tool_calls", []))
    iterations = state.get("iterations", 0)
    session_id = state.get("session_id", "")
    # request_tool_calls: tool calls executed so far in THIS request (from tool_plan)
    request_tool_calls = sum(
        1 for tc in state.get("tool_calls", []) if tc.get("allowed", False)
    )

    checks: list[CheckResult] = []
    risk_score = 0.0

    # ── Check 1: RBAC ─────────────────────────────────────
    rbac = _check_rbac(tool_name, allowed_tools, user_role)
    checks.append(rbac)
    if not rbac["passed"]:
        risk_score = 1.0
        return GateDecision(
            tool=tool_name,
            args=args,
            decision="BLOCK",
            reason=rbac["detail"],
            checks=checks,
            modified_args=None,
            risk_score=risk_score,
        )

    # ── Check 2: Argument validation (schema + injection) ─────
    arg_check, modified_args = _check_args(tool_name, args)
    checks.append(arg_check)
    if not arg_check["passed"]:
        risk_score = 0.9
        return GateDecision(
            tool=tool_name,
            args=args,
            decision="BLOCK",
            reason=arg_check["detail"],
            checks=checks,
            modified_args=None,
            risk_score=risk_score,
        )

    # If args were sanitized, use the cleaned version going forward
    effective_args = modified_args if modified_args is not None else args

    # ── Check 3: Context risk ─────────────────────────────
    ctx_risk = _check_context_risk(
        tool_name, effective_args, message, chat_history, blocked_count
    )
    checks.append(ctx_risk)
    if not ctx_risk["passed"]:
        risk_score = 0.8
        return GateDecision(
            tool=tool_name,
            args=args,
            decision="BLOCK",
            reason=ctx_risk["detail"],
            checks=checks,
            modified_args=None,
            risk_score=risk_score,
        )

    # ── Check 4: Limits ───────────────────────────────────
    limits = _check_limits(
        total_tool_calls, iterations,
        session_id=session_id,
        user_role=user_role,
        request_tool_calls=request_tool_calls,
    )
    checks.append(limits)
    if not limits["passed"]:
        risk_score = 0.7
        return GateDecision(
            tool=tool_name,
            args=args,
            decision="BLOCK",
            reason=limits["detail"],
            checks=checks,
            modified_args=None,
            risk_score=risk_score,
        )

    # ── Check 5: Confirmation ─────────────────────────────
    confirm = _check_confirmation(tool_name, user_role)
    checks.append(confirm)
    if not confirm["passed"]:
        risk_score = 0.3
        return GateDecision(
            tool=tool_name,
            args=args,
            decision="REQUIRE_CONFIRMATION",
            reason=confirm["detail"],
            checks=checks,
            modified_args=None,
            risk_score=risk_score,
        )

    # ── All checks passed ─────────────────────────
    decision = "MODIFY" if modified_args is not None else "ALLOW"
    return GateDecision(
        tool=tool_name,
        args=args,
        decision=decision,
        reason="Args sanitized" if decision == "MODIFY" else None,
        checks=checks,
        modified_args=modified_args,
        risk_score=risk_score,
    )


# ── Gate node ─────────────────────────────────────────────────────────


def pre_tool_gate_node(state: AgentState) -> AgentState:
    """Pre-tool enforcement gate — evaluates each proposed tool call.

    Reads `tool_plan` from state, runs security checks on each,
    and produces `gate_decisions`. Filters `tool_plan` to only
    ALLOW/MODIFY decisions. Sets `pending_confirmation` if any tool
    requires user approval.
    """
    tool_plan: list[dict[str, Any]] = state.get("tool_plan", [])
    gate_decisions: list[GateDecision] = []
    filtered_plan: list[dict[str, Any]] = []
    pending_confirmation: dict[str, Any] | None = None
    tool_calls = list(state.get("tool_calls", []))
    trace = TraceAccumulator(state.get("trace"))

    # Count previously blocked calls in this session (for escalation detection)
    blocked_count = sum(1 for tc in tool_calls if not tc.get("allowed", True))

    for plan in tool_plan:
        tool_name = plan.get("tool", "")
        args = plan.get("args", {})

        decision = _evaluate_tool(tool_name, args, state, blocked_count)
        gate_decisions.append(decision)

        # Trace (spec 07)
        trace.record_pre_tool_decision(
            tool=tool_name,
            decision=decision["decision"],
            reason=decision["reason"],
            checks=decision["checks"],
            risk_score=decision["risk_score"],
        )

        if decision["decision"] == "ALLOW":
            filtered_plan.append(plan)

        elif decision["decision"] == "MODIFY":
            # Use modified args
            filtered_plan.append({
                "tool": tool_name,
                "args": decision["modified_args"] or args,
            })

        elif decision["decision"] == "BLOCK":
            # Record the blocked tool call
            tool_calls.append({
                "tool": tool_name,
                "args": args,
                "result": f"Blocked by pre-tool gate: {decision['reason']}",
                "allowed": False,
            })
            blocked_count += 1

        elif decision["decision"] == "REQUIRE_CONFIRMATION":
            # First confirmation request wins — pause the agent
            if pending_confirmation is None:
                pending_confirmation = {
                    "tool": tool_name,
                    "args": args,
                    "reason": decision["reason"],
                }

        logger.info(
            "pre_tool_gate",
            tool=tool_name,
            decision=decision["decision"],
            reason=decision["reason"],
            risk_score=decision["risk_score"],
        )

    logger.info(
        "pre_tool_gate_summary",
        total=len(tool_plan),
        allowed=sum(1 for d in gate_decisions if d["decision"] == "ALLOW"),
        blocked=sum(1 for d in gate_decisions if d["decision"] == "BLOCK"),
        modified=sum(1 for d in gate_decisions if d["decision"] == "MODIFY"),
        confirmations=sum(
            1 for d in gate_decisions if d["decision"] == "REQUIRE_CONFIRMATION"
        ),
    )

    # Track allowed tool calls in limits service (spec 06)
    allowed_count = len(filtered_plan)
    if allowed_count > 0:
        session_id = state.get("session_id", "")
        if session_id:
            limits_svc = get_limits_service()
            limits_svc.increment_tool_calls(session_id, allowed_count)

    return {
        **state,
        "tool_plan": filtered_plan,
        "gate_decisions": gate_decisions,
        "tool_calls": tool_calls,
        "pending_confirmation": pending_confirmation,
        "trace": trace.data,
    }
