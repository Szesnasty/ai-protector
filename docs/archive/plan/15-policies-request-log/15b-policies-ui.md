# 15b — Policies CRUD UI

| | |
|---|---|
| **Parent** | [Step 15 — Policies & Request Log](SPEC.md) |
| **Estimated time** | 3–4 hours |
| **Depends on** | Step 08 (policies CRUD API), Step 05 (Nuxt + Vuetify shell) |

---

## Goal

Replace the placeholder `policies.vue` page with a full **Policies management UI**: card grid showing all 4 policy levels, a create/edit dialog with a rich config editor (threshold sliders, scanner node toggles), and soft-delete for custom policies. The backend CRUD API already exists — this sub-step is pure frontend.

---

## Page Layout

```
┌──────────────────────────────────────────────────────────────┐
│  Policies                                            [+ New] │
│  Manage firewall policy levels with custom thresholds        │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────┐│
│  │ 🟢 fast     │  │ 🟡 balanced │  │ 🟠 strict   │  │ 🔴  ││
│  │             │  │             │  │             │  │para ││
│  │ v3          │  │ v5          │  │ v2          │  │noid ││
│  │ Active      │  │ Active      │  │ Active      │  │     ││
│  │             │  │             │  │             │  │     ││
│  │ Scanners: 2 │  │ Scanners: 4 │  │ Scanners: 5 │  │S: 6 ││
│  │ Max risk:0.9│  │ Max risk:0.7│  │ Max risk:0.5│  │0.3  ││
│  │             │  │             │  │             │  │     ││
│  │ [Edit]      │  │ [Edit]      │  │ [Edit]      │  │[Ed] ││
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────┘│
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## Components

### `policies/card.vue` — Policy summary card

Props: `policy: Policy`

Display:
- Color-coded icon based on policy name (fast=green, balanced=yellow, strict=orange, paranoid=red)
- Policy name, description (truncated), version badge
- Active/Inactive chip
- Quick stats: number of enabled scanner nodes, max_risk threshold
- Edit button → emits `edit` event
- Delete button (only for non-builtin policies) → emits `delete` event

### `policies/dialog.vue` — Create / Edit dialog

Props: `modelValue: boolean`, `policy: Policy | null` (null = create mode)

Features:
- Name field (disabled for builtin policies: fast, balanced, strict, paranoid)
- Description textarea
- Active toggle switch
- Embedded `<policies-config-editor>` for the JSONB config
- Save / Cancel buttons
- Validation: name required, unique (handled by API 409)

### `policies/config-editor.vue` — Thresholds & nodes editor

Props: `modelValue: PolicyConfig`

The config JSONB has this structure (from `PolicyConfigSchema`):
```json
{
  "nodes": ["llm_guard", "presidio", "output_filter", "logging"],
  "thresholds": {
    "max_risk": 0.7,
    "injection_threshold": 0.5,
    "toxicity_threshold": 0.7,
    "pii_action": "flag",
    "enable_canary": false,
    "injection_weight": 0.8,
    "toxicity_weight": 0.5,
    "secrets_weight": 0.6,
    "invisible_weight": 0.4,
    "pii_per_entity_weight": 0.1,
    "pii_max_weight": 0.5
  }
}
```

UI sections:

**1. Scanner Nodes** (checkboxes / chips)
- Available nodes: `llm_guard`, `presidio`, `ml_judge`, `output_filter`, `memory_hygiene`, `logging`, `canary`
- Each node has icon + label + short description
- Toggle on/off → updates `config.nodes` array

**2. Risk Thresholds** (sliders)
- `max_risk` — Main risk threshold (0.0–1.0, step 0.05)
- `injection_threshold` — Injection detection threshold
- `toxicity_threshold` — Toxicity threshold
- Each slider shows current value + color indicator (green < 0.5 < orange < 0.8 < red)

**3. Risk Weights** (sliders)
- `injection_weight`, `toxicity_weight`, `secrets_weight`, `invisible_weight`
- `pii_per_entity_weight`, `pii_max_weight`
- Labeled sliders with 0.0–1.0 range

**4. PII Settings**
- `pii_action` — radio/select: flag | mask | block
- `enable_canary` — toggle switch

---

## Composable Updates

### `usePolicies.ts` — Add mutations

```typescript
// Existing: useQuery for list
// ADD:
const createMutation = useMutation({
  mutationFn: (body: PolicyCreate) => api.post('/v1/policies', body),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['policies'] }),
})

const updateMutation = useMutation({
  mutationFn: ({ id, body }: { id: string; body: PolicyUpdate }) =>
    api.patch(`/v1/policies/${id}`, body),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['policies'] }),
})

const deleteMutation = useMutation({
  mutationFn: (id: string) => api.delete(`/v1/policies/${id}`),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['policies'] }),
})
```

---

## Type additions (`types/api.ts`)

```typescript
export interface PolicyCreate {
  name: string
  description?: string
  config?: Record<string, unknown>
  is_active?: boolean
}

export interface PolicyUpdate {
  name?: string
  description?: string
  config?: Record<string, unknown>
  is_active?: boolean
}

export interface PolicyConfig {
  nodes: string[]
  thresholds: {
    max_risk: number
    injection_threshold: number
    toxicity_threshold: number
    pii_action: 'flag' | 'mask' | 'block'
    enable_canary: boolean
    injection_weight: number
    toxicity_weight: number
    secrets_weight: number
    invisible_weight: number
    pii_per_entity_weight: number
    pii_max_weight: number
  }
}
```

---

## File Tree

```
apps/frontend/app/
├── pages/
│   └── policies.vue                     # REWRITE
├── components/
│   └── policies/
│       ├── card.vue                     # NEW
│       ├── dialog.vue                   # NEW
│       └── config-editor.vue            # NEW
├── composables/
│   └── usePolicies.ts                   # MODIFIED — add mutations
└── types/
    └── api.ts                           # MODIFIED — add PolicyCreate, PolicyUpdate, PolicyConfig
```

---

## Definition of Done

### UI verification
- [ ] Policies page shows 4 policy cards (fast, balanced, strict, paranoid) with status indicators
- [ ] Each card shows: name, description, version, active status, scanner count, max_risk
- [ ] Click Edit → dialog opens pre-filled with current policy data
- [ ] Config editor: node toggles work, threshold sliders update values
- [ ] Save → API PATCH → card updates, version increments
- [ ] Create new policy → API POST → new card appears
- [ ] Delete non-builtin policy → API DELETE → card removed
- [ ] Cannot delete builtin policies (fast, balanced, strict, paranoid) — button hidden
- [ ] Loading state while fetching policies
- [ ] Error handling: 409 (duplicate name), 403 (cannot delete builtin), 422 (invalid config)

### Checklist
- [ ] `policies/card.vue` — color-coded card with quick stats and edit/delete actions
- [ ] `policies/dialog.vue` — create/edit dialog with validation
- [ ] `policies/config-editor.vue` — threshold sliders, node toggles, PII settings
- [ ] `usePolicies.ts` — create, update, delete mutations with cache invalidation
- [ ] `PolicyCreate`, `PolicyUpdate`, `PolicyConfig` types added
- [ ] `policies.vue` rewritten with card grid and dialog integration
- [ ] Proper empty state, loading state, error handling

---

| **Prev** | **Next** |
|---|---|
| [15a — Request Log API](15a-request-log-api.md) | [15c — Request Log UI](15c-request-log-ui.md) |
