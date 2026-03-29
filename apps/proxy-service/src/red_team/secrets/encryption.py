"""AES-256-GCM encryption for auth secrets.

The encryption key is read from ``BENCHMARK_SECRET_KEY`` env var.
It must be a 64-character hex string (32 bytes = 256 bits).

Ciphertext format: ``base64(nonce ‖ ciphertext ‖ tag)``
"""

from __future__ import annotations

import base64
import os
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_KEY_ENV = "BENCHMARK_SECRET_KEY"
_NONCE_LENGTH = 12  # 96-bit nonce recommended for AES-GCM
_DEV_KEY: bytes | None = None  # lazily generated fallback for development


def _get_key() -> bytes:
    """Return the 32-byte AES key from the environment.

    In development, if the env var is not set, a random key is generated
    once per process and reused (secrets are ephemeral with 24 h TTL).
    """
    global _DEV_KEY  # noqa: PLW0603
    raw = os.environ.get(_KEY_ENV)
    if not raw:
        if _DEV_KEY is None:
            _DEV_KEY = secrets.token_bytes(32)
        return _DEV_KEY
    try:
        key = bytes.fromhex(raw)
    except ValueError as exc:
        raise RuntimeError(f"{_KEY_ENV} must be a hex string") from exc
    if len(key) != 32:
        raise RuntimeError(f"{_KEY_ENV} must be 64 hex chars (32 bytes), got {len(key)}")
    return key


def encrypt(plaintext: str) -> str:
    """Encrypt *plaintext* with AES-256-GCM → base64 string."""
    key = _get_key()
    nonce = secrets.token_bytes(_NONCE_LENGTH)
    aesgcm = AESGCM(key)
    ct = aesgcm.encrypt(nonce, plaintext.encode(), None)
    # nonce (12) + ciphertext+tag
    return base64.urlsafe_b64encode(nonce + ct).decode()


def decrypt(token: str) -> str:
    """Decrypt a base64 AES-256-GCM token → plaintext string."""
    key = _get_key()
    raw = base64.urlsafe_b64decode(token)
    nonce = raw[:_NONCE_LENGTH]
    ct = raw[_NONCE_LENGTH:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ct, None).decode()
