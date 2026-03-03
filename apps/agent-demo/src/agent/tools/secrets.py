"""getInternalSecrets — mock internal config (admin-only)."""

from __future__ import annotations

MOCK_SECRETS = {
    "MOCK_DATABASE_URL": "postgresql://admin:s3cr3t_p4ss@internal-db.corp:5432/production",
    "MOCK_API_KEY_STRIPE": "sk_live_MOCK_4242424242424242",
    "MOCK_API_KEY_SENDGRID": "SG.MOCK_xxxxxxxxxxxxxx",
    "MOCK_JWT_SECRET": "MOCK_super-secret-jwt-signing-key-2025",
    "MOCK_AWS_ACCESS_KEY": "AKIAMOCK1234567890AB",
    "MOCK_AWS_SECRET_KEY": "MOCK_wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    "MOCK_INTERNAL_ADMIN_URL": "https://admin-internal.corp/dashboard",
}


def get_internal_secrets() -> str:
    """Return mock internal secrets. Should only be accessible to admins."""
    lines = ["Internal Configuration (CONFIDENTIAL):"]
    for key, value in MOCK_SECRETS.items():
        lines.append(f"  {key} = {value}")
    return "\n".join(lines)
