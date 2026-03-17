"""Dynamic security wrapper that loads wizard-generated configs at runtime.

Implements the same ``protected_tool_call()`` pattern as the wizard-generated
``raw_python_protection.py``, but loads config dynamically (from YAML files
or from the wizard API) instead of being generated with inline values.
"""

from __future__ import annotations

import os
import re
from typing import Any

import yaml

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "config")


# ── SecurityConfig ────────────────────────────────────────────────────


class SecurityConfig:
    """Loads and holds wizard-generated YAML configs."""

    def __init__(self) -> None:
        self.rbac: dict = {}
        self.limits: dict = {}
        self.policy: dict = {}
        self.loaded = False

    def load_from_files(self, config_dir: str = CONFIG_DIR) -> None:
        """Load RBAC, limits, policy from YAML files in *config_dir*."""
        for name in ("rbac", "limits", "policy"):
            path = os.path.join(config_dir, f"{name}.yaml")
            if os.path.exists(path):
                with open(path) as f:
                    setattr(self, name, yaml.safe_load(f) or {})
        self.loaded = True

    def load_from_kit(self, kit: dict) -> None:
        """Load configs from wizard integration-kit API response."""
        files = kit.get("files", {})
        for name in ("rbac", "limits", "policy"):
            raw = files.get(f"{name}.yaml", "")
            if raw:
                setattr(self, name, yaml.safe_load(raw) or {})
        self.loaded = True

    def load_from_dicts(
        self,
        *,
        rbac: dict | None = None,
        limits: dict | None = None,
        policy: dict | None = None,
    ) -> None:
        """Load configs from plain dicts (useful for tests)."""
        if rbac is not None:
            self.rbac = rbac
        if limits is not None:
            self.limits = limits
        if policy is not None:
            self.policy = policy
        self.loaded = True


_config = SecurityConfig()


def get_config() -> SecurityConfig:
    """Return the singleton config instance."""
    return _config


def reset_config() -> None:
    """Reset config to default (for tests)."""
    global _config  # noqa: PLW0603
    _config = SecurityConfig()


# ── Gate functions ────────────────────────────────────────────────────


def check_rbac(role: str, tool: str) -> dict[str, Any]:
    """RBAC permission check with inheritance walking."""
    roles = _config.rbac.get("roles", {})
    visited: set[str] = set()
    current: str | None = role
    while current and current not in visited:
        visited.add(current)
        role_cfg = roles.get(current, {})
        tools = role_cfg.get("tools", {})
        if tool in tools:
            t = tools[tool]
            return {
                "allowed": True,
                "scopes": t.get("scopes", ["read"]),
                "requires_confirmation": t.get("requires_confirmation", False),
            }
        current = role_cfg.get("inherits")
    return {"allowed": False, "scopes": [], "requires_confirmation": False}


def check_limits(role: str, tool: str) -> dict[str, Any]:
    """Rate limit check (simplified — no server-side counter yet)."""
    role_limits = _config.limits.get("roles", {}).get(role, {})
    max_calls = role_limits.get("max_tool_calls_per_session", 20)
    return {"within_limits": True, "max_calls": max_calls}


def scan_output(output: str) -> dict[str, Any]:
    """Post-tool output scanning: PII detection + injection detection."""
    findings: list[dict] = []
    scanners = _config.policy.get("scanners", {})

    if scanners.get("pii_redaction", True):
        email_re = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
        phone_re = re.compile(r"\+?\d[\d\-\s]{7,}\d")
        if email_re.search(output):
            findings.append(
                {"type": "pii", "subtype": "email", "detail": "Email address detected"}
            )
        if phone_re.search(output):
            findings.append(
                {"type": "pii", "subtype": "phone", "detail": "Phone number detected"}
            )

    if scanners.get("injection_detection", True):
        for pattern in [
            "DROP TABLE",
            "DELETE FROM",
            "'; --",
            "UNION SELECT",
            "ignore all previous",
            "you are now",
            "reveal your system",
        ]:
            if pattern.lower() in output.lower():
                findings.append({"type": "injection", "detail": f"Pattern: {pattern}"})

    return {"clean": len(findings) == 0, "findings": findings}


def protected_tool_call(
    role: str,
    tool: str,
    args: dict | None,
    execute_fn: Any,
) -> dict:
    """Full protection wrapper: RBAC → limits → execute → scan output."""
    # 1. RBAC check
    perm = check_rbac(role, tool)
    if not perm["allowed"]:
        return {
            "allowed": False,
            "result": None,
            "gate": "pre_tool",
            "decision": "block",
            "reason": f"Role '{role}' cannot use '{tool}'",
            "scan_result": None,
        }

    # 2. Confirmation check
    if perm["requires_confirmation"]:
        return {
            "allowed": True,
            "result": None,
            "gate": "pre_tool",
            "decision": "confirm",
            "reason": f"Tool '{tool}' requires confirmation (write, high sensitivity)",
            "requires_confirmation": True,
            "scan_result": None,
        }

    # 3. Limits check
    limit = check_limits(role, tool)
    if not limit["within_limits"]:
        return {
            "allowed": False,
            "result": None,
            "gate": "pre_tool",
            "decision": "block",
            "reason": "Rate limit exceeded",
            "scan_result": None,
        }

    # 4. Execute tool
    result = execute_fn(tool, args or {})

    # 5. Post-tool scan
    scan = scan_output(str(result))

    return {
        "allowed": True,
        "result": result,
        "gate": "post_tool",
        "decision": "allow" if scan["clean"] else "flagged",
        "reason": None if scan["clean"] else "Output contains flagged content",
        "scan_result": scan,
    }
