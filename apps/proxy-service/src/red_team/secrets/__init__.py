"""Red Team — Secret handling for auth credentials.

Provides AES-256-GCM encryption and a ``SecretStore`` protocol
for future extensibility (Vault, KMS, etc.).
"""

from src.red_team.secrets.encryption import decrypt, encrypt
from src.red_team.secrets.store import EncryptedColumnSecretStore, SecretStore

__all__ = [
    "SecretStore",
    "EncryptedColumnSecretStore",
    "encrypt",
    "decrypt",
]
