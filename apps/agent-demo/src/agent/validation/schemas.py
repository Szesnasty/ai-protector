"""Tool argument schemas — Pydantic models per tool.

Spec: docs/agents/04-agents-argument-validation/SPEC.md

Each tool has a strict Pydantic model that defines:
  - required/optional fields with types
  - format patterns (regex)
  - length limits
  - custom validators (injection scanning)

Tools without a schema use a permissive fallback model.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

# ── Injection patterns checked inside field validators ────────────────

_INJECTION_RES: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"ignore\s+(previous|all|your)\s+(instructions|rules|constraints)",
        r"you\s+are\s+now\b",
        r"act\s+as\s+(if|a|an)\b",
        r"pretend\s+to\s+be\b",
        r"reveal\s+(your|the)\s+(system|secret|prompt)",
        r"(system|assistant)\s*:",
        r"\[INST\]",
        r"<\|im_start\|>",
        r"forget\s+(everything|what)",
        r"new\s+instructions?\s*:",
        r"disregard\s+(all\s+)?(prior|previous|above)",
        r"override\s+(all\s+)?rules",
        r"do\s+anything\s+now",
        r"\bjailbreak\b",
        r"<<SYS>>",
    ]
]


def _scan_injection(value: str) -> list[str]:
    """Return list of injection pattern names found in *value*."""
    matched: list[str] = []
    for pattern in _INJECTION_RES:
        if pattern.search(value):
            matched.append(pattern.pattern[:60])
    return matched


def _sanitize_string(value: str, max_length: int) -> str:
    """Normalize and trim a string value.

    - Strip leading/trailing whitespace
    - Normalize Unicode (NFKC)
    - Remove ASCII control characters (except \n, \t)
    - Truncate to *max_length*
    """
    value = value.strip()
    value = unicodedata.normalize("NFKC", value)
    # Remove control chars (keep \n \t)
    value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value)
    if len(value) > max_length:
        value = value[:max_length]
    return value


# ── Pydantic schemas per tool ─────────────────────────────────────────


class GetOrderStatusArgs(BaseModel):
    """Schema for getOrderStatus tool arguments."""

    model_config = {"extra": "forbid"}

    order_id: str = Field(
        ...,
        pattern=r"^ORD-\d{3,6}$",
        min_length=7,
        max_length=10,
        description="Order ID in format ORD-XXX (3-6 digits)",
        examples=["ORD-001", "ORD-1234"],
    )

    @field_validator("order_id")
    @classmethod
    def no_injection(cls, v: str) -> str:
        matches = _scan_injection(v)
        if matches:
            raise ValueError(f"Injection pattern detected: {matches[0]}")
        return v


class SearchKnowledgeBaseArgs(BaseModel):
    """Schema for searchKnowledgeBase tool arguments."""

    model_config = {"extra": "forbid"}

    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Search query for knowledge base",
    )

    @field_validator("query")
    @classmethod
    def no_injection(cls, v: str) -> str:
        matches = _scan_injection(v)
        if matches:
            raise ValueError(f"Injection pattern detected: {matches[0]}")
        return v


class GetInternalSecretsArgs(BaseModel):
    """Schema for getInternalSecrets — no args allowed."""

    model_config = {"extra": "forbid"}


class GetCustomerProfileArgs(BaseModel):
    """Schema for getCustomerProfile tool arguments."""

    model_config = {"extra": "forbid"}

    customer_id: str = Field(
        default="",
        max_length=50,
        description="Optional customer identifier",
    )

    @field_validator("customer_id")
    @classmethod
    def no_injection(cls, v: str) -> str:
        if v:
            matches = _scan_injection(v)
            if matches:
                raise ValueError(f"Injection pattern detected: {matches[0]}")
        return v


class IssueRefundArgs(BaseModel):
    """Schema for issueRefund tool arguments."""

    model_config = {"extra": "forbid"}

    order_id: str = Field(
        ...,
        pattern=r"^ORD-\d{3,6}$",
        min_length=7,
        max_length=10,
        description="Order ID to refund",
    )
    reason: str = Field(
        default="",
        max_length=500,
        description="Reason for refund",
    )

    @field_validator("order_id", "reason")
    @classmethod
    def no_injection(cls, v: str) -> str:
        if v:
            matches = _scan_injection(v)
            if matches:
                raise ValueError(f"Injection pattern detected: {matches[0]}")
        return v


# ── Schema registry ──────────────────────────────────────────────────

TOOL_SCHEMAS: dict[str, type[BaseModel]] = {
    "getOrderStatus": GetOrderStatusArgs,
    "searchKnowledgeBase": SearchKnowledgeBaseArgs,
    "getInternalSecrets": GetInternalSecretsArgs,
    "getCustomerProfile": GetCustomerProfileArgs,
    "issueRefund": IssueRefundArgs,
}


def get_schema(tool_name: str) -> type[BaseModel] | None:
    """Return the Pydantic schema for a tool, or None if unregistered."""
    return TOOL_SCHEMAS.get(tool_name)
