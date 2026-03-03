# 08a — Policies CRUD API

| | |
|---|---|
| **Parent** | [Step 08 — Policy Engine](SPEC.md) |
| **Next sub-step** | [08b — Policy Validation & Seed Update](08b-policy-validation.md) |
| **Estimated time** | 2–2.5 hours |

---

## Goal

Create a full REST CRUD router for firewall policies. Operators can list, read, create, update, and delete policies via the API.

---

## Tasks

### 1. Router (`src/routers/policies.py`)

- [x] `GET /v1/policies` — list all policies:
  ```python
  @router.get("/policies", response_model=list[PolicyRead])
  async def list_policies(
      active_only: bool = Query(True),
      db: AsyncSession = Depends(get_db),
  ) -> list[PolicyRead]:
      """List all policies. By default only active ones."""
      stmt = select(Policy).order_by(Policy.name)
      if active_only:
          stmt = stmt.where(Policy.is_active == True)  # noqa: E712
      result = await db.execute(stmt)
      return result.scalars().all()
  ```

- [x] `GET /v1/policies/{policy_id}` — get single policy:
  ```python
  @router.get("/policies/{policy_id}", response_model=PolicyRead)
  async def get_policy(
      policy_id: uuid.UUID,
      db: AsyncSession = Depends(get_db),
  ) -> PolicyRead:
      policy = await db.get(Policy, policy_id)
      if policy is None:
          raise HTTPException(status_code=404, detail="Policy not found")
      return policy
  ```

- [x] `POST /v1/policies` — create policy:
  ```python
  @router.post("/policies", response_model=PolicyRead, status_code=201)
  async def create_policy(
      body: PolicyCreate,
      db: AsyncSession = Depends(get_db),
  ) -> PolicyRead:
      # Check name uniqueness
      existing = await db.execute(
          select(Policy).where(Policy.name == body.name)
      )
      if existing.scalar_one_or_none():
          raise HTTPException(status_code=409, detail=f"Policy '{body.name}' already exists")

      policy = Policy(**body.model_dump())
      db.add(policy)
      await db.commit()
      await db.refresh(policy)
      return policy
  ```

- [x] `PATCH /v1/policies/{policy_id}` — update policy:
  ```python
  @router.patch("/policies/{policy_id}", response_model=PolicyRead)
  async def update_policy(
      policy_id: uuid.UUID,
      body: PolicyUpdate,
      db: AsyncSession = Depends(get_db),
  ) -> PolicyRead:
      policy = await db.get(Policy, policy_id)
      if policy is None:
          raise HTTPException(status_code=404, detail="Policy not found")

      update_data = body.model_dump(exclude_unset=True)
      for key, value in update_data.items():
          setattr(policy, key, value)
      policy.version += 1

      await db.commit()
      await db.refresh(policy)

      # Invalidate Redis cache
      await _invalidate_policy_cache(policy.name)
      return policy
  ```

- [x] `DELETE /v1/policies/{policy_id}` — soft-delete (set `is_active=False`):
  ```python
  @router.delete("/policies/{policy_id}", status_code=204)
  async def delete_policy(
      policy_id: uuid.UUID,
      db: AsyncSession = Depends(get_db),
  ) -> None:
      policy = await db.get(Policy, policy_id)
      if policy is None:
          raise HTTPException(status_code=404, detail="Policy not found")
      # Protect built-in policies
      if policy.name in ("fast", "balanced", "strict", "paranoid"):
          raise HTTPException(status_code=403, detail="Cannot delete built-in policy")
      policy.is_active = False
      await db.commit()
      await _invalidate_policy_cache(policy.name)
  ```

### 2. Redis cache invalidation helper

- [x] Add to `src/routers/policies.py`:
  ```python
  async def _invalidate_policy_cache(policy_name: str) -> None:
      """Remove cached policy config from Redis after CRUD mutation."""
      try:
          redis = await get_redis()
          await redis.delete(f"policy_config:{policy_name}")
      except Exception:
          logger.debug("policy_cache_invalidation_failed", policy=policy_name)
  ```

### 3. Register router in `src/main.py`

- [x] Add:
  ```python
  from src.routers.policies import router as policies_router
  app.include_router(policies_router, prefix="/v1")
  ```

### 4. Update schema (`src/schemas/policy.py`)

- [x] Ensure `PolicyRead` includes `updated_at`:
  ```python
  class PolicyRead(PolicyBase):
      model_config = ConfigDict(from_attributes=True)
      id: uuid.UUID
      version: int
      created_at: datetime
      updated_at: datetime | None = None
  ```

### 5. Tests (`tests/test_policies_crud.py`)

- [x] `GET /v1/policies` → returns list of policies
- [x] `GET /v1/policies?active_only=false` → includes inactive
- [x] `GET /v1/policies/{id}` → returns single policy
- [x] `GET /v1/policies/{id}` with bad UUID → 404
- [x] `POST /v1/policies` → creates, returns 201
- [x] `POST /v1/policies` duplicate name → 409
- [x] `PATCH /v1/policies/{id}` → updates, bumps version
- [x] `PATCH /v1/policies/{id}` with bad UUID → 404
- [x] `DELETE /v1/policies/{id}` → soft-deletes, 204
- [x] `DELETE /v1/policies/{id}` built-in policy → 403
- [x] Redis cache invalidated on update/delete

---

## Definition of Done

- [x] `src/routers/policies.py` — full CRUD (5 endpoints)
- [x] Router registered in `src/main.py` at `/v1`
- [x] `PolicyRead` schema includes `updated_at`
- [x] Redis cache invalidated on update and delete
- [x] Built-in policies (`fast`, `balanced`, `strict`, `paranoid`) protected from delete
- [x] All tests pass
- [x] `ruff check src/ tests/` → 0 errors

---

| **Prev** | **Next** |
|---|---|
| — | [08b — Policy Validation & Seed Update](08b-policy-validation.md) |
