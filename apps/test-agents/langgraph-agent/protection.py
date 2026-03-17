"""Dynamic security layer matching wizard's LangGraph kit interface."""

from __future__ import annotations

import os
import re
from typing import Any

import yaml

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "config")


# ── Shared config singleton ─────────────────────────────────────


class SecurityConfig:
    """Holds RBAC, limits and policy data loaded from wizard kit."""

    def __init__(self) -> None:
        self.rbac: dict = {}
        self.limits: dict = {}
        self.policy: dict = {}
        self.loaded: bool = False

    # -- loaders ----------------------------------------------------------

    def load_from_kit(self, kit: dict) -> None:
        """Load from integration-kit JSON (proxy-service response)."""
        files = kit.get("files", {})
        for name in ("rbac", "limits", "policy"):
            raw = files.get(f"{name}.yaml", "")
            if raw:
                setattr(self, name, yaml.safe_load(raw) or {})
        self.loaded = True

    def load_from_dicts(
        self,
        rbac: dict | None = None,
        limits: dict | None = None,
        policy: dict | None = None,
    ) -> None:
        """Load directly from dicts (for testing)."""
        if rbac is not None:
            self.rbac = rbac
        if limits is not None:
            self.limits = limits
        if policy is not None:
            self.policy = policy
        self.loaded = True

    def load_from_files(self) -> None:
        """Load from YAML files stored in config/ directory."""
        for name in ("rbac", "limits", "policy"):
            path = os.path.join(CONFIG_DIR, f"{name}.yaml")
            if os.path.isfile(path):
                with open(path) as f:
                    setattr(self, name, yaml.safe_load(f) or {})
        self.loaded = True

    def reset(self) -> None:
        self.rbac = {}
        self.limits = {}
        self.policy = {}
        self.loaded = False


_config = SecurityConfig()


def get_config() -> SecurityConfig:
    return _config


def reset_config() -> None:
    _config.reset()


# ── RBACService ─────────────────────────────────────────────────


class RBACService:
    """Role-based access control (same interface as wizard-generated kit)."""

    def check_permission(self, role: str, tool: str) -> dict[str, Any]:
        roles = _config.rbac.get("roles", {})
        visited: set[str] = set()
        current: str | None = role
        while current and current not in visited:
            visited.add(current)
            role_cfg = roles.get(current, {})
            tools_cfg = role_cfg.get("tools", {})
            if tool in tools_cfg:
                t = tools_cfg[tool]
                return {
                    "allowed": True,
                    "scopes": t.get("scopes", ["read"]),
                    "requires_confirmation": t.get("requires_confirmation", False),
                    "sensitivity": t.get("sensitivity", "low"),
                }
            current = role_cfg.get("inherits")
        return {
            "allowed": False,
            "scopes": [],
            "requires_confirmation": False,
            "sensitivity": None,
        }


# ── LimitsService ──────────────────────────────────────────────


class LimitsService:
    """Budget and rate-limit enforcement."""

    def __init__(self) -> None:
        self._call_counts: dict[str, int] = {}

    def check_limits(self, role: str, tool: str) -> dict[str, Any]:
        role_limits = _config.limits.get("roles", {}).get(role, {})
        max_calls = role_limits.get("max_tool_calls_per_session", 20)
        key = f"{role}:{tool}"
        current = self._call_counts.get(key, 0)
        return {
            "within_limits": current < max_calls,
            "current_calls": current,
            "max_calls": max_calls,
        }

    def record_call(self, role: str, tool: str) -> None:
        key = f"{role}:{tool}"
        self._call_counts[key] = self._call_counts.get(key, 0) + 1

    def reset(self) -> None:
        self._call_counts.clear()


# ── PreToolGate ─────────────────────────────────────────────────


class PreToolGate:
    """Pre-tool enforcement gate (RBAC + limits)."""

    def __init__(self) -> None:
        self.rbac = RBACService()
        self.limits = LimitsService()

    def check(self, role: str, tool: str, args: dict | None = None) -> dict[str, Any]:
        perm = self.rbac.check_permission(role, tool)
        if not perm["allowed"]:
            return {
                "allowed": False,
                "decision": "block",
                "reason": f"Role '{role}' does not have access to '{tool}'",
            }
        limit = self.limits.check_limits(role, tool)
        if not limit["within_limits"]:
            return {
                "allowed": False,
                "decision": "block",
                "reason": f"Rate limit exceeded for '{tool}'",
            }
        self.limits.record_call(role, tool)
        return {
            "allowed": True,
            "decision": ("confirm" if perm["requires_confirmation"] else "allow"),
            "requires_confirmation": perm.get("requires_confirmation", False),
            "reason": (
                "Confirmation required" if perm["requires_confirmation"] else None
            ),
        }


# ── PostToolGate ────────────────────────────────────────────────


class PostToolGate:
    """Post-tool enforcement gate — scans output for PII and injection."""

    def scan(self, output: str) -> dict[str, Any]:
        findings: list[dict] = []
        scanners = _config.policy.get("scanners", {})

        if scanners.get("pii_redaction", True):
            if re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", output):
                findings.append(
                    {"type": "pii", "subtype": "email", "detail": "Email detected"}
                )
            if re.search(r"\+?\d[\d\-\s]{7,}\d", output):
                findings.append(
                    {"type": "pii", "subtype": "phone", "detail": "Phone detected"}
                )

        if scanners.get("injection_detection", True):
            for pat in [
                "DROP TABLE",
                "DELETE FROM",
                "'; --",
                "UNION SELECT",
                "ignore all previous",
                "you are now",
                "reveal your system",
            ]:
                if pat.lower() in output.lower():
                    findings.append({"type": "injection", "detail": f"Pattern: {pat}"})

        return {"clean": len(findings) == 0, "findings": findings}
