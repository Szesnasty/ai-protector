# 03 — Auth Secret Handling

> **Layer:** Backend
> **Phase:** 2 (Custom Endpoints) — MVP
> **Depends on:** Persistence (Phase 0)

## Scope

Secure handling of auth credentials: encryption at rest, ephemeral storage, auto-deletion, never in logs/exports.

## Implementation Steps

### Step 1: Encryption service

- AES-256 encryption for auth secrets
- Encryption key from environment variable (`BENCHMARK_SECRET_KEY`)
- `encrypt(plaintext) → ciphertext`
- `decrypt(ciphertext) → plaintext`

### Step 2: Secret storage in target_config

- When creating a run with an auth header:
  - Encrypt the auth value
  - Store encrypted reference: `target_config.auth_secret_ref = "encrypted:{ciphertext}"`
  - Never store plaintext in DB
- When running a benchmark:
  - Decrypt `auth_secret_ref` → pass to HTTP Client in-memory
  - HTTP Client sends it as `Authorization` header

### Step 3: Auto-deletion

- After run completes (any terminal state): schedule secret deletion
- TTL: 24 hours after run completion
- Cleanup job: find `completed_at + 24h < now()` → null out `auth_secret_ref`
- If `auth_secret_ref` already null → skip

### Step 4: Logging policy enforcement

- `auth_secret_ref` masked in all log outputs: `"auth_secret_ref": "***"`
- HTTP Client never logs the `Authorization` header value
- Export never includes `auth_secret_ref`
- API response never includes `auth_secret_ref` (strip from target_config in response serialization)

### Step 5: Future: Vault/KMS integration point

- Define `SecretStore` interface for future providers:
  ```python
  class SecretStore(Protocol):
      async def store(self, key: str, value: str, ttl_hours: int) → str  # returns ref
      async def retrieve(self, ref: str) → str | None
      async def delete(self, ref: str) → None
  ```
- MVP: `EncryptedColumnSecretStore` (DB column)
- Future: `VaultSecretStore`, `KMSSecretStore`

## Tests

| Test | What it verifies |
|------|-----------------|
| `test_encrypt_decrypt_roundtrip` | encrypt → decrypt returns original |
| `test_encrypted_stored_in_db` | DB has ciphertext, not plaintext |
| `test_plaintext_never_in_logs` | Log output doesn't contain auth value |
| `test_auth_deleted_after_ttl` | Auth null after run + 24h |
| `test_auth_stripped_from_api_response` | GET /runs/:id doesn't return auth_secret_ref |
| `test_auth_stripped_from_export` | Export JSON doesn't contain auth |
| `test_http_client_receives_decrypted` | HTTP Client sends correct Authorization header |
| `test_secret_store_interface` | Both EncryptedColumn and future Vault implement same interface |

## Definition of Done

- [ ] Auth secrets encrypted at rest (AES-256)
- [ ] Auto-deleted 24h after run completion
- [ ] Never in logs, API responses, or exports
- [ ] HTTP Client receives decrypted auth for requests only
- [ ] `SecretStore` interface defined for future extensibility
- [ ] All tests pass
