# 10c — Config Sidebar & Debug Panel

| | |
|---|---|
| **Parent** | [Step 10 — Playground](SPEC.md) |
| **Prev sub-step** | [10b — Chat UI](10b-chat-ui.md) |
| **Estimated time** | 2–2.5 hours |

---

## Goal

Build the right-side sidebar containing two sections:
1. **Config Sidebar** — lets the user pick a policy level, tweak model, temperature, and max tokens before sending a message.
2. **Debug Panel** — displays the pipeline decision metadata (decision chip, intent, risk score gauge, risk flags, latency) extracted after each request.

> **Convention:** `<script setup lang="ts">`. Kebab-case file names and template tags.
> Styles: `<style lang="scss" scoped>`.

---

## Tasks

### 1. Config sidebar (`app/components/playground/config-sidebar.vue`)

- [x] Props & injections:
  ```typescript
  interface Props {
    config: {
      policy: string
      model: string
      temperature: number
      maxTokens: number | null
    }
    disabled?: boolean // true while streaming
  }
  ```

- [x] Emits:
  ```typescript
  defineEmits<{
    'update:config': [config: Props['config']]
  }>()
  ```

- [x] **Policy selector** (`v-select`):
  - Items from `usePolicies()` composable → array of `{ title: policy.name, value: policy.level }`
  - Default: `balanced`
  - Each item shows short description in `v-select` subtitle slot (from `policy.description`)
  - Loading state via `isLoading` from `usePolicies`

- [x] **Model input** (`v-text-field`):
  - Default: `llama3.1:8b`
  - Hint: "Ollama model name"
  - `variant="outlined"`, `density="compact"`

- [x] **Temperature slider** (`v-slider`):
  - Range: `0` — `2`, step `0.1`
  - Default: `0.7`
  - Show thumb label
  - Label: "Temperature"

- [x] **Max tokens** (`v-text-field` type number):
  - Optional (nullable)
  - Placeholder: "Default (model limit)"
  - `variant="outlined"`, `density="compact"`

- [x] All controls disabled while `disabled` is true (streaming)

```vue
<template>
  <v-card variant="flat" class="config-sidebar">
    <v-card-title class="text-subtitle-1">
      <v-icon start>mdi-cog</v-icon>
      Configuration
    </v-card-title>

    <v-card-text>
      <v-select
        :model-value="config.policy"
        :items="policyItems"
        :loading="isLoading"
        :disabled="disabled"
        label="Policy level"
        variant="outlined"
        density="compact"
        class="mb-4"
        @update:model-value="updateField('policy', $event)"
      />

      <v-text-field
        :model-value="config.model"
        :disabled="disabled"
        label="Model"
        hint="Ollama model name"
        variant="outlined"
        density="compact"
        class="mb-4"
        @update:model-value="updateField('model', $event)"
      />

      <v-slider
        :model-value="config.temperature"
        :disabled="disabled"
        label="Temperature"
        :min="0"
        :max="2"
        :step="0.1"
        thumb-label
        class="mb-4"
        @update:model-value="updateField('temperature', $event)"
      />

      <v-text-field
        :model-value="config.maxTokens"
        :disabled="disabled"
        label="Max tokens"
        placeholder="Default (model limit)"
        type="number"
        variant="outlined"
        density="compact"
        @update:model-value="updateField('maxTokens', $event ? Number($event) : null)"
      />
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { usePolicies } from '~/composables/usePolicies'

interface Config {
  policy: string
  model: string
  temperature: number
  maxTokens: number | null
}

const props = defineProps<{
  config: Config
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:config': [config: Config]
}>()

const { policies, isLoading } = usePolicies()

const policyItems = computed(() =>
  (policies.value ?? []).map((p) => ({
    title: p.name,
    value: p.level,
    subtitle: p.description,
  })),
)

function updateField<K extends keyof Config>(key: K, value: Config[K]) {
  emit('update:config', { ...props.config, [key]: value })
}
</script>

<style lang="scss" scoped>
.config-sidebar {
  padding: 8px 0;
}
</style>
```

### 2. Debug panel (`app/components/playground/debug-panel.vue`)

- [x] Props:
  ```typescript
  interface Props {
    decision: PipelineDecision | null
  }
  ```

- [x] Show nothing (or "No data yet" placeholder) when `decision` is null

- [x] **Decision chip** — `v-chip` with color based on value:
  - `ALLOW` → `success` (green)
  - `MODIFY` → `warning` (orange)
  - `BLOCK` → `error` (red)

- [x] **Intent** — text label:
  ```
  Intent: qa
  ```

- [x] **Risk score gauge** — `v-progress-linear` with dynamic color:
  - `0.0–0.3` → `success`
  - `0.3–0.7` → `warning`
  - `0.7–1.0` → `error`
  - Display score as percentage label (`0.42 → 42%`)

- [x] **Risk flags** — list each flag as `v-chip` with score:
  ```
  injection: 0.95  |  toxicity: 0.1
  ```
  - Chips colored by severity: >0.7 red, >0.3 orange, else grey

- [x] **Blocked reason** — if `decision === 'BLOCK'`, show the reason in a `v-alert` type `error`

```vue
<template>
  <v-card variant="flat" class="debug-panel">
    <v-card-title class="text-subtitle-1">
      <v-icon start>mdi-bug</v-icon>
      Pipeline Debug
    </v-card-title>

    <v-card-text v-if="!decision" class="text-grey text-body-2">
      Send a message to see pipeline results.
    </v-card-text>

    <v-card-text v-else>
      <!-- Decision badge -->
      <div class="debug-panel__row mb-3">
        <span class="text-caption text-grey">Decision</span>
        <v-chip
          :color="decisionColor"
          size="small"
          label
        >
          {{ decision.decision }}
        </v-chip>
      </div>

      <!-- Intent -->
      <div class="debug-panel__row mb-3">
        <span class="text-caption text-grey">Intent</span>
        <span class="text-body-2 font-weight-medium">{{ decision.intent }}</span>
      </div>

      <!-- Risk Score -->
      <div class="mb-3">
        <div class="d-flex justify-space-between mb-1">
          <span class="text-caption text-grey">Risk score</span>
          <span class="text-body-2 font-weight-medium">
            {{ (decision.riskScore * 100).toFixed(0) }}%
          </span>
        </div>
        <v-progress-linear
          :model-value="decision.riskScore * 100"
          :color="riskColor"
          height="8"
          rounded
        />
      </div>

      <!-- Risk Flags -->
      <div v-if="hasFlags" class="mb-3">
        <span class="text-caption text-grey d-block mb-1">Risk flags</span>
        <div class="d-flex flex-wrap ga-1">
          <v-chip
            v-for="(score, flag) in decision.riskFlags"
            :key="String(flag)"
            :color="flagColor(Number(score))"
            size="x-small"
            label
          >
            {{ flag }}: {{ Number(score).toFixed(2) }}
          </v-chip>
        </div>
      </div>

      <!-- Blocked reason -->
      <v-alert
        v-if="decision.decision === 'BLOCK' && decision.blockedReason"
        type="error"
        density="compact"
        variant="tonal"
        class="mt-2"
      >
        {{ decision.blockedReason }}
      </v-alert>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { PipelineDecision } from '~/types/api'

const props = defineProps<{
  decision: PipelineDecision | null
}>()

const decisionColor = computed(() => {
  switch (props.decision?.decision) {
    case 'ALLOW': return 'success'
    case 'MODIFY': return 'warning'
    case 'BLOCK': return 'error'
    default: return 'grey'
  }
})

const riskColor = computed(() => {
  const score = props.decision?.riskScore ?? 0
  if (score >= 0.7) return 'error'
  if (score >= 0.3) return 'warning'
  return 'success'
})

const hasFlags = computed(() =>
  props.decision?.riskFlags && Object.keys(props.decision.riskFlags).length > 0,
)

function flagColor(score: number): string {
  if (score >= 0.7) return 'error'
  if (score >= 0.3) return 'warning'
  return 'grey'
}
</script>

<style lang="scss" scoped>
.debug-panel {
  padding: 8px 0;

  &__row {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
}
</style>
```

### 3. Wire sidebar into Playground page

- [x] Update `playground.vue` (from 10b) to include both components in the sidebar column:
  ```vue
  <v-col cols="12" md="4" lg="3" class="playground-page__sidebar">
    <config-sidebar
      :config="config"
      :disabled="isStreaming"
      @update:config="Object.assign(config, $event)"
    />
    <v-divider class="my-2" />
    <debug-panel :decision="lastDecision" />
  </v-col>
  ```

- [x] `useChat()` now provides `config` (reactive) and `lastDecision`:
  ```typescript
  const { messages, isStreaming, lastDecision, error, config, send, clear, abort } = useChat()
  ```

### 4. Navigation link

- [x] Add "Playground" item to the nav drawer (from Step 05a) pointing to `/playground`
  - Icon: `mdi-flask` or `mdi-chat-processing`

---

## File tree (after this sub-step)

```
app/
  pages/
    playground.vue          ← updated with sidebar
  components/
    playground/
      chat-message-list.vue
      chat-message.vue
      chat-input.vue
      config-sidebar.vue    ← NEW
      debug-panel.vue       ← NEW
```

---

## Definition of Done

- [x] Config sidebar renders with policy selector, model, temperature, max tokens
- [x] Policy selector loads items from `usePolicies()` (Vue Query), shows loading state
- [x] Temperature slider controls range 0–2 with 0.1 step, shows thumb label
- [x] All config changes propagate reactively to `useChat` config
- [x] All sidebar controls disabled during streaming
- [x] Debug panel shows "Send a message…" placeholder when no decision exists
- [x] After first message: decision chip appears (ALLOW green / MODIFY orange / BLOCK red)
- [x] Intent label updates per request
- [x] Risk score progress bar shows 0–100% with color coded thresholds
- [x] Risk flags render as labeled chips with severity colors
- [x] BLOCK responses show red alert with blocked reason text
- [x] Config sidebar + debug panel are visually separated by divider
- [x] Navigation drawer has a "Playground" link
- [x] All `.vue` files use `<script setup lang="ts">`
- [x] All component files are kebab-case
- [x] All styles use `<style lang="scss" scoped>`
- [x] `npx nuxi typecheck` passes

---

| **Prev** | **Parent** |
|---|---|
| [10b — Chat UI](10b-chat-ui.md) | [Step 10 — Playground](SPEC.md) |
