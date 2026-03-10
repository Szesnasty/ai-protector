<template>
  <v-card flat>
    <v-card-title class="text-h6">Describe your agent</v-card-title>
    <v-card-subtitle>Basic information about the agent you want to protect</v-card-subtitle>

    <v-card-text>
      <v-form ref="formRef" v-model="formValid">
        <v-row>
          <v-col cols="12" md="6">
            <v-text-field
              v-model="form.name"
              label="Agent name"
              :rules="[rules.required, rules.minLength]"
              variant="outlined"
              prepend-inner-icon="mdi-tag-outline"
              hint="Unique name for your agent"
              persistent-hint
            />
          </v-col>
          <v-col cols="12" md="6">
            <v-select
              v-model="form.framework"
              :items="frameworkOptions"
              label="Framework"
              variant="outlined"
              prepend-inner-icon="mdi-puzzle-outline"
            />
          </v-col>
          <v-col cols="12">
            <v-textarea
              v-model="form.description"
              label="Description"
              :rules="[rules.required]"
              variant="outlined"
              rows="3"
              hint="What does this agent do?"
              persistent-hint
            />
          </v-col>
          <v-col cols="12" md="6">
            <v-select
              v-model="form.environment"
              :items="envOptions"
              label="Environment"
              variant="outlined"
              prepend-inner-icon="mdi-server"
            />
          </v-col>
          <v-col cols="12" md="6">
            <v-text-field
              v-model="form.team"
              label="Team (optional)"
              variant="outlined"
              prepend-inner-icon="mdi-account-group-outline"
            />
          </v-col>
        </v-row>

        <v-divider class="my-4" />
        <p class="text-subtitle-2 mb-3">Risk factors</p>
        <v-row>
          <v-col cols="12" sm="6" md="4">
            <v-checkbox v-model="form.is_public_facing" label="Public facing" density="compact" hide-details />
          </v-col>
          <v-col cols="12" sm="6" md="4">
            <v-checkbox v-model="form.has_write_actions" label="Has write actions" density="compact" hide-details />
          </v-col>
          <v-col cols="12" sm="6" md="4">
            <v-checkbox v-model="form.touches_pii" label="Touches PII" density="compact" hide-details />
          </v-col>
          <v-col cols="12" sm="6" md="4">
            <v-checkbox v-model="form.handles_secrets" label="Handles secrets" density="compact" hide-details />
          </v-col>
          <v-col cols="12" sm="6" md="4">
            <v-checkbox v-model="form.calls_external_apis" label="Calls external APIs" density="compact" hide-details />
          </v-col>
        </v-row>
      </v-form>

      <v-alert v-if="errorMsg" type="error" variant="tonal" class="mt-4" closable @click:close="errorMsg = ''">
        {{ errorMsg }}
      </v-alert>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import type { AgentCreate, AgentFramework, AgentEnvironment } from '~/types/wizard'

const props = defineProps<{
  initialData?: Partial<AgentCreate>
}>()

const emit = defineEmits<{
  valid: [valid: boolean]
  submit: [data: AgentCreate]
}>()

const formRef = ref<InstanceType<typeof import('vuetify/components').VForm> | null>(null)
const formValid = ref(false)
const errorMsg = ref('')

const frameworkOptions = [
  { title: 'LangGraph', value: 'langgraph' as AgentFramework },
  { title: 'Raw Python', value: 'raw_python' as AgentFramework },
  { title: 'Proxy Only', value: 'proxy_only' as AgentFramework },
]

const envOptions = [
  { title: 'Development', value: 'dev' as AgentEnvironment },
  { title: 'Staging', value: 'staging' as AgentEnvironment },
  { title: 'Production', value: 'production' as AgentEnvironment },
]

const rules = {
  required: (v: string) => !!v?.trim() || 'Required',
  minLength: (v: string) => (v && v.length >= 3) || 'At least 3 characters',
}

const form = reactive<AgentCreate>({
  name: props.initialData?.name ?? '',
  description: props.initialData?.description ?? '',
  framework: props.initialData?.framework ?? 'langgraph',
  environment: props.initialData?.environment ?? 'dev',
  team: props.initialData?.team ?? null,
  is_public_facing: props.initialData?.is_public_facing ?? false,
  has_tools: true,
  has_write_actions: props.initialData?.has_write_actions ?? false,
  touches_pii: props.initialData?.touches_pii ?? false,
  handles_secrets: props.initialData?.handles_secrets ?? false,
  calls_external_apis: props.initialData?.calls_external_apis ?? false,
})

watch(formValid, (v) => emit('valid', v))

const getData = (): AgentCreate => ({ ...form })

const setError = (msg: string) => { errorMsg.value = msg }

defineExpose({ getData, setError })
</script>
