# 04 — Safe Mode Filtering

> **Layer:** Backend
> **Phase:** 2 (Custom Endpoints) — MVP
> **Depends on:** Pack Loader (Phase 0)

## Scope

When safe mode is enabled, mutating scenarios (that could trigger real actions) are skipped. Score adjusts to reflect only executed scenarios.

## Implementation Steps

### Step 1: Ensure `mutating` flag on all scenarios

- Review all pack YAML files
- Every scenario must have `mutating: true | false`
- Core Security: most scenarios are `mutating: false` (read-only attacks)
- Agent Threats: many are `mutating: true` (delete, transfer, modify actions)

### Step 2: Pack Loader integration (already designed in Phase 0)

- When `safe_mode = true`: skip scenarios where `mutating = true`
- Skip reason: `safe_mode`
- This is already part of the filtering pipeline — verify it works

### Step 3: Score display with safe mode

- Results show: "Score: 72/100 (Safe mode — 5 mutating scenarios skipped)"
- Category breakdown computed from executed scenarios only
- `skipped_mutating` counter in run record

### Step 4: Frontend display

- On results page: if `skipped_mutating > 0`, show info banner:
  - "Safe mode was enabled. {N} mutating scenarios were skipped."
  - Small link: "What are mutating scenarios?" → tooltip or help text

### Step 5: Agent Threats safe mode variant

- Agent Threats in safe mode: reduced scenarios
  - Skip: "delete user", "modify permissions", "execute shell command"
  - Keep: "list users", "read config", "enumerate endpoints"
- This means Agent Threats in safe mode is a meaningful (if reduced) test

## Tests

| Test | What it verifies |
|------|-----------------|
| `test_safe_mode_skips_mutating` | mutating=true scenarios skipped when safe_mode=true |
| `test_safe_mode_off_runs_all` | All scenarios run when safe_mode=false |
| `test_skipped_mutating_count` | `skipped_mutating` = number of mutating scenarios skipped |
| `test_score_excludes_skipped` | Score computed from executed scenarios only |
| `test_safe_mode_banner_shown` | Frontend shows info banner when scenarios skipped |
| `test_core_security_mostly_safe` | Most Core Security scenarios are not mutating |
| `test_agent_threats_safe_variant` | Agent Threats in safe mode still has executable scenarios |

## Definition of Done

- [ ] All scenarios have correct `mutating` flag
- [ ] Safe mode filtering works end-to-end
- [ ] Score adjusts correctly (excludes skipped)
- [ ] Frontend displays safe mode info banner
- [ ] `skipped_mutating` counter persisted in run record
- [ ] All tests pass
