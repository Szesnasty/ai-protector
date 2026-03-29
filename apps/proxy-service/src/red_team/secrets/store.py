"""SecretStore protocol and MVP implementation.

The ``SecretStore`` protocol defines a pluggable interface for credential
storage.  The MVP uses ``EncryptedColumnSecretStore`` which stores encrypted
values directly in the DB column.

Future implementations (``VaultSecretStore``, ``KMSSecretStore``) can be
swapped in via configuration.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.red_team.secrets.encryption import decrypt, encrypt

# Prefix for encrypted references stored in target_config
_ENCRYPTED_PREFIX = "encrypted:"


@runtime_checkable
class SecretStore(Protocol):
    """Interface for secret storage backends."""

    async def store(self, key: str, value: str, ttl_hours: int) -> str:
        """Store *value* under *key* with a TTL.  Returns an opaque ref."""
        ...

    async def retrieve(self, ref: str) -> str | None:
        """Retrieve the plaintext value for *ref*.  ``None`` if expired/deleted."""
        ...

    async def delete(self, ref: str) -> None:
        """Delete the secret identified by *ref*."""
        ...


class EncryptedColumnSecretStore:
    """MVP SecretStore: AES-256-GCM encrypted column values.

    The "ref" is ``encrypted:<base64_ciphertext>``.
    TTL enforcement is handled externally by the cleanup job.
    """

    async def store(self, key: str, value: str, ttl_hours: int = 24) -> str:  # noqa: ARG002
        """Encrypt *value* and return a ref string."""
        ciphertext = encrypt(value)
        return f"{_ENCRYPTED_PREFIX}{ciphertext}"

    async def retrieve(self, ref: str) -> str | None:
        """Decrypt the ref and return plaintext, or ``None`` if invalid."""
        if not ref.startswith(_ENCRYPTED_PREFIX):
            return None
        token = ref[len(_ENCRYPTED_PREFIX) :]
        try:
            return decrypt(token)
        except Exception:
            return None

    async def delete(self, ref: str) -> None:  # noqa: ARG002
        """No-op for column store — deletion happens via SQL update."""


def is_encrypted_ref(value: str) -> bool:
    """Check if a string is an encrypted secret reference."""
    return isinstance(value, str) and value.startswith(_ENCRYPTED_PREFIX)
