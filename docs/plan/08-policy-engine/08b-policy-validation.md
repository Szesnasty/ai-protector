# 08b — Policy Validation & Seed Update

| | |
|---|---|
| **Parent** | [Step 08 — Policy Engine](SPEC.md) |
| **Prev sub-step** | [08a — Policies CRUD API](08a-policies-crud.md) |
| **Next sub-step** | [08c — Policy-Aware Decision Node](08c-policy-decision.md) |
| **Estimated time** | 1.5–2 hours |

---

## Goal

Add a Pydantic validation model for the JSONB `config` field in policies. Ensure invalid configs are rejected at API time, not at pipeline runtime. Update seed data to align with current pipeline capabilities.

---

## Tasks

### 1. Policy config schema (`src/schemas/policy_config.py`)

- [x] Define the `PolicyConfigSchema`:
  ```python
  from pydantic import BaseModel, Field

  class ThresholdsSchema(BaseModel):
      max_risk: float = Field(0.7, ge=0.0, le=1.0)
      injection_threshold: float = Field(0.5, ge=0.0, le=1.0)
      toxicity_threshold: float = Field(0.7, ge=0.0, le=1.0)
      pii_action: Literal["flag", "mask", "block"] = "flag"
      enable_canary: bool = False

  VALID_NODES = {
      "parse", "intent", "rules",
      "llm_guard", "presidio", "ml_judge",
      "decision", "transform", "llm",
      "output_filter", "memory_hygiene", "logging",
      "canary",
  }

  class PolicyConfigSchema(BaseModel):
      nodes: list[str] = Field(default_factory=list)
      thresholds: ThresholdsSchema = Field(default_factory=ThresholdsSchema)

      @field_validator("nodes")
      @classmethod
      def validate_nodes(cls, v: list[str]) -> list[str]:
          invalid = set(v) - VALID_NODES
          if invalid:
              raise ValueError(f"Invalid node names: {invalid}")
          return v
  ```

### 2. Validate config on create/update

- [x] In `POST /v1/policies` and `PATCH /v1/policies/{id}`:
  ```python
  if "config" in update_data:
      try:
          PolicyConfigSchema(**update_data["config"])
      except ValidationError as e:
          raise HTTPException(status_code=422, detail=e.errors())
  ```

### 3. Update `PolicyCreate` / `PolicyUpdate` schemas

- [x] Change `config` type to use the validation:
  ```python
  class PolicyCreate(PolicyBase):
      config: dict  # Validated in router via PolicyConfigSchema

  class PolicyUpdate(BaseModel):
      config: dict | None = None  # Validated in router via PolicyConfigSchema
  ```

### 4. Version bumping rules

- [x] On `PATCH`: always increment `version += 1`
- [x] On `POST`: start at `version = 1` (default from model)
- [x] Store `updated_at` on every mutation:
  ```python
  # In Policy model — add updated_at if not present
  updated_at: Mapped[datetime | None] = mapped_column(
      DateTime(timezone=True),
      onupdate=func.now(),
      nullable=True,
  )
  ```

### 5. Update seed data (`src/db/seed.py`)

- [x] Align `nodes` lists with actual pipeline node names:
  ```python
  # fast — no scanners, just core pipeline
  "nodes": [],  # empty = skip scanners

  # balanced — LLM Guard only
  "nodes": ["llm_guard"],

  # strict — LLM Guard + Presidio
  "nodes": ["llm_guard", "presidio"],

  # paranoid — LLM Guard + Presidio (all future scanners too)
  "nodes": ["llm_guard", "presidio"],
  ```
  > Nodes like `parse`, `intent`, `rules`, `decision`, `transform`, `llm` always run (core pipeline). The `nodes` list in config only controls **optional** scanners/extensions.

- [x] Create a migration if `updated_at` column is added to `policies`

### 6. Tests

- [x] Valid config → accepted
- [x] Invalid `max_risk: 2.0` → 422
- [x] Invalid node name `"foobar"` → 422
- [x] Invalid `pii_action: "nuke"` → 422
- [x] Missing `thresholds` → defaults applied
- [x] Version bumps on update
- [x] `updated_at` changes on PATCH

---

## Definition of Done

- [x] `src/schemas/policy_config.py` — Pydantic model validates `nodes` + `thresholds`
- [x] Create and update endpoints validate config before saving
- [x] Invalid configs rejected with 422 + clear error messages
- [x] `updated_at` tracked on Policy model
- [x] Seed data `nodes` lists aligned with actual pipeline (only scanner/extension names)
- [x] All tests pass
- [x] `ruff check src/ tests/` → 0 errors

---

| **Prev** | **Next** |
|---|---|
| [08a — Policies CRUD API](08a-policies-crud.md) | [08c — Policy-Aware Decision Node](08c-policy-decision.md) |
