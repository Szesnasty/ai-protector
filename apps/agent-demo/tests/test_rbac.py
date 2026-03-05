"""Tests for RBAC Service (Spec 02).

Covers: permission resolution, role inheritance, scope checking,
requires_confirmation flag, default-deny, unknown roles.
"""

from __future__ import annotations

import textwrap
import tempfile
from pathlib import Path

import pytest

from src.agent.rbac.models import PermissionResult
from src.agent.rbac.service import RBACService, get_rbac_service, reset_rbac_service


# ── Helpers ───────────────────────────────────────────────────────────


def _write_config(yaml_text: str) -> Path:
    """Write YAML config to a temp file and return its path."""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    f.write(textwrap.dedent(yaml_text))
    f.close()
    return Path(f.name)


@pytest.fixture
def default_service() -> RBACService:
    """RBAC service loaded from the default config."""
    return RBACService()


@pytest.fixture
def custom_service() -> RBACService:
    """RBAC service loaded from a custom test config."""
    config = _write_config("""\
        roles:
          viewer:
            description: "Read-only viewer"
            tools:
              viewDashboard:
                scopes: [read]
                sensitivity: low

          editor:
            description: "Can view and edit"
            inherits: viewer
            tools:
              editDocument:
                scopes: [read, write]
                sensitivity: medium

          superadmin:
            description: "Full access"
            inherits: editor
            tools:
              deleteEverything:
                scopes: [read, write, execute]
                sensitivity: critical
                requires_confirmation: true
    """)
    return RBACService(config)


# ── Default config tests ─────────────────────────────────────────────


class TestDefaultConfig:
    def test_customer_allowed_tools(self, default_service: RBACService):
        tools = default_service.get_allowed_tools("customer")
        assert "searchKnowledgeBase" in tools
        assert "getOrderStatus" in tools
        assert "getInternalSecrets" not in tools

    def test_admin_inherits_all(self, default_service: RBACService):
        tools = default_service.get_allowed_tools("admin")
        assert "searchKnowledgeBase" in tools
        assert "getOrderStatus" in tools
        assert "getInternalSecrets" in tools
        assert "issueRefund" in tools

    def test_support_inherits_customer(self, default_service: RBACService):
        tools = default_service.get_allowed_tools("support")
        assert "searchKnowledgeBase" in tools
        assert "getOrderStatus" in tools
        assert "getCustomerProfile" in tools
        assert "getInternalSecrets" not in tools

    def test_unknown_role_no_tools(self, default_service: RBACService):
        tools = default_service.get_allowed_tools("hacker")
        assert tools == []


class TestCheckPermission:
    def test_customer_read_allowed(self, default_service: RBACService):
        result = default_service.check_permission("customer", "getOrderStatus", "read")
        assert result.allowed is True
        assert result.requires_confirmation is False
        assert "read" in result.scopes_granted

    def test_customer_secrets_denied(self, default_service: RBACService):
        result = default_service.check_permission("customer", "getInternalSecrets", "read")
        assert result.allowed is False
        assert "not in allowlist" in result.reason

    def test_customer_write_scope_denied(self, default_service: RBACService):
        result = default_service.check_permission("customer", "getOrderStatus", "write")
        assert result.allowed is False
        assert "Scope" in result.reason

    def test_admin_secrets_requires_confirmation(self, default_service: RBACService):
        result = default_service.check_permission("admin", "getInternalSecrets", "read")
        assert result.allowed is True
        assert result.requires_confirmation is True
        assert result.tool_sensitivity == "critical"

    def test_admin_refund_requires_confirmation(self, default_service: RBACService):
        result = default_service.check_permission("admin", "issueRefund", "write")
        assert result.allowed is True
        assert result.requires_confirmation is True
        assert result.tool_sensitivity == "high"

    def test_support_inherits_kb_from_customer(self, default_service: RBACService):
        result = default_service.check_permission("support", "searchKnowledgeBase", "read")
        assert result.allowed is True

    def test_support_own_tool(self, default_service: RBACService):
        result = default_service.check_permission("support", "getCustomerProfile", "read")
        assert result.allowed is True
        assert result.tool_sensitivity == "medium"

    def test_unknown_role_denied(self, default_service: RBACService):
        result = default_service.check_permission("hacker", "getOrderStatus", "read")
        assert result.allowed is False
        assert "Unknown role" in result.reason

    def test_unknown_tool_denied(self, default_service: RBACService):
        result = default_service.check_permission("customer", "nonExistentTool", "read")
        assert result.allowed is False


class TestRoleConfig:
    def test_get_existing_role(self, default_service: RBACService):
        config = default_service.get_role_config("customer")
        assert config is not None
        assert config.name == "customer"
        assert config.inherits is None

    def test_support_inherits_customer(self, default_service: RBACService):
        config = default_service.get_role_config("support")
        assert config is not None
        assert config.inherits == "customer"

    def test_admin_inherits_support(self, default_service: RBACService):
        config = default_service.get_role_config("admin")
        assert config is not None
        assert config.inherits == "support"

    def test_unknown_role_returns_none(self, default_service: RBACService):
        config = default_service.get_role_config("nobody")
        assert config is None


# ── Custom config / inheritance chain tests ──────────────────────────


class TestInheritanceChain:
    def test_viewer_has_one_tool(self, custom_service: RBACService):
        tools = custom_service.get_allowed_tools("viewer")
        assert tools == ["viewDashboard"]

    def test_editor_inherits_viewer(self, custom_service: RBACService):
        tools = custom_service.get_allowed_tools("editor")
        assert "viewDashboard" in tools
        assert "editDocument" in tools

    def test_superadmin_inherits_all(self, custom_service: RBACService):
        tools = custom_service.get_allowed_tools("superadmin")
        assert "viewDashboard" in tools
        assert "editDocument" in tools
        assert "deleteEverything" in tools

    def test_deep_inheritance_permission(self, custom_service: RBACService):
        """superadmin can use viewer's tool via editor."""
        result = custom_service.check_permission("superadmin", "viewDashboard", "read")
        assert result.allowed is True

    def test_viewer_cannot_edit(self, custom_service: RBACService):
        result = custom_service.check_permission("viewer", "editDocument", "read")
        assert result.allowed is False

    def test_confirmation_flag_inherited(self, custom_service: RBACService):
        result = custom_service.check_permission("superadmin", "deleteEverything", "execute")
        assert result.allowed is True
        assert result.requires_confirmation is True
        assert result.tool_sensitivity == "critical"


class TestToolDefinition:
    def test_get_existing_tool(self, default_service: RBACService):
        td = default_service.get_tool_definition("getInternalSecrets")
        assert td is not None
        assert td.sensitivity == "critical"
        assert td.requires_confirmation is True

    def test_get_unknown_tool(self, default_service: RBACService):
        td = default_service.get_tool_definition("nonExistent")
        assert td is None


# ── Singleton tests ──────────────────────────────────────────────────


class TestSingleton:
    def test_singleton_returns_same_instance(self):
        reset_rbac_service()
        s1 = get_rbac_service()
        s2 = get_rbac_service()
        assert s1 is s2
        reset_rbac_service()

    def test_reset_clears_singleton(self):
        reset_rbac_service()
        s1 = get_rbac_service()
        reset_rbac_service()
        s2 = get_rbac_service()
        assert s1 is not s2
        reset_rbac_service()
