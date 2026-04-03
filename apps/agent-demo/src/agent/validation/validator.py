"""Argument Validator — validates tool arguments against Pydantic schemas.

Spec: docs/archive/agents/04-agents-argument-validation/SPEC.md

Three possible outcomes:
  VALID      — args conform to schema, no injection detected
  INVALID    — type/format/injection error → BLOCK the tool call
  SANITIZED  — args were cleaned (trimmed/normalized) → MODIFY the tool call
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

import structlog
from pydantic import ValidationError

from src.agent.validation.schemas import (
    _sanitize_string,
    _scan_injection,
    get_schema,
)

logger = structlog.get_logger()


class ArgValidationResult(TypedDict):
    """Outcome of argument validation for a single tool call."""

    valid: bool
    decision: str  # "VALID", "INVALID", "SANITIZED"
    errors: list[str]
    injection_detected: bool
    injection_patterns: list[str]
    sanitized_args: dict[str, Any] | None
    original_args: dict[str, Any]


# Config: what to do when a tool has no schema
UNREGISTERED_TOOL_POLICY: Literal["allow", "deny"] = "allow"


def validate_tool_args(
    tool_name: str,
    args: dict[str, Any],
) -> ArgValidationResult:
    """Validate arguments for a tool call.

    1. Look up Pydantic schema for the tool.
    2. If no schema → policy-dependent (allow with warning, or deny).
    3. Try sanitization first (trim, normalize strings).
    4. Validate sanitized args against schema.
    5. Scan all string args for injection patterns.
    6. Return VALID / INVALID / SANITIZED.
    """
    schema_cls = get_schema(tool_name)

    base_result: ArgValidationResult = {
        "valid": True,
        "decision": "VALID",
        "errors": [],
        "injection_detected": False,
        "injection_patterns": [],
        "sanitized_args": None,
        "original_args": dict(args),
    }

    # ── No schema registered ──────────────────────────────────
    if schema_cls is None:
        if UNREGISTERED_TOOL_POLICY == "deny":
            logger.warning("arg_validation_no_schema_deny", tool=tool_name)
            return {
                **base_result,
                "valid": False,
                "decision": "INVALID",
                "errors": [f"No schema registered for tool '{tool_name}'"],
            }
        # Allow with warning — still scan for injection
        logger.info("arg_validation_no_schema_allow", tool=tool_name)
        injection_patterns = _scan_string_args(args)
        if injection_patterns:
            return {
                **base_result,
                "valid": False,
                "decision": "INVALID",
                "injection_detected": True,
                "injection_patterns": injection_patterns,
                "errors": [f"Injection pattern in args: {p}" for p in injection_patterns],
            }
        return base_result

    # ── Sanitize string args ──────────────────────────────────
    sanitized_args = _sanitize_args(args, schema_cls)
    was_sanitized = sanitized_args != args

    # ── Validate against Pydantic schema ──────────────────────
    try:
        validated = schema_cls.model_validate(sanitized_args)
        validated_dict = validated.model_dump()
    except ValidationError as e:
        errors = [err["msg"] for err in e.errors()]
        logger.info(
            "arg_validation_failed",
            tool=tool_name,
            errors=errors,
        )
        # Check if injection was the cause
        injection_patterns = _scan_string_args(args)
        return {
            **base_result,
            "valid": False,
            "decision": "INVALID",
            "errors": errors,
            "injection_detected": bool(injection_patterns),
            "injection_patterns": injection_patterns,
        }

    # ── Extra injection scan (catches patterns that Pydantic validators might miss) ──
    injection_patterns = _scan_string_args(sanitized_args)
    if injection_patterns:
        return {
            **base_result,
            "valid": False,
            "decision": "INVALID",
            "injection_detected": True,
            "injection_patterns": injection_patterns,
            "errors": [f"Injection pattern in args: {p}" for p in injection_patterns],
        }

    # ── Success ───────────────────────────────────────────────
    if was_sanitized:
        logger.info("arg_validation_sanitized", tool=tool_name)
        return {
            **base_result,
            "valid": True,
            "decision": "SANITIZED",
            "sanitized_args": validated_dict,
        }

    return base_result


def _sanitize_args(args: dict[str, Any], schema_cls: type) -> dict[str, Any]:
    """Sanitize string arguments: trim, normalize, strip control chars."""
    result = {}
    # Get max_length from schema fields if available
    field_limits: dict[str, int] = {}
    if hasattr(schema_cls, "model_fields"):
        for f_name, f_info in schema_cls.model_fields.items():
            metadata = f_info.metadata
            for m in metadata:
                if hasattr(m, "max_length"):
                    field_limits[f_name] = m.max_length
            # Also check Field's max_length directly
            if f_info.json_schema_extra and "maxLength" in f_info.json_schema_extra:
                field_limits[f_name] = f_info.json_schema_extra["maxLength"]

    for key, value in args.items():
        if isinstance(value, str):
            max_len = field_limits.get(key, 2000)
            result[key] = _sanitize_string(value, max_len)
        else:
            result[key] = value

    return result


def _scan_string_args(args: dict[str, Any]) -> list[str]:
    """Scan all string values in args dict for injection patterns."""
    all_patterns: list[str] = []
    for _key, value in args.items():
        if isinstance(value, str):
            matched = _scan_injection(value)
            all_patterns.extend(matched)
    return all_patterns
