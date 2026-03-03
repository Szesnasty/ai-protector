<template>
  <v-card variant="flat" class="agent-config">
    <v-card-title class="text-subtitle-1">
      <v-icon start>mdi-cog</v-icon>
      Agent Config
    </v-card-title>

    <v-card-text>
      <v-select
        :model-value="role"
        :items="roleItems"
        :disabled="disabled"
        label="User Role"
        variant="outlined"
        density="compact"
        class="mb-4"
        @update:model-value="$emit('update:role', $event)"
      />

      <v-select
        :model-value="policy"
        :items="policyItems"
        :loading="isPoliciesLoading"
        :disabled="disabled"
        label="Policy"
        variant="outlined"
        density="compact"
        clearable
        class="mb-4"
        @update:model-value="$emit('update:policy', $event)"
      />

      <v-btn
        block
        variant="outlined"
        color="secondary"
        :disabled="disabled"
        prepend-icon="mdi-refresh"
        @click="$emit('new-conversation')"
      >
        New Conversation
      </v-btn>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { usePolicies } from '~/composables/usePolicies'

defineProps<{
  role: 'customer' | 'admin'
  policy: string | null
  disabled?: boolean
}>()

defineEmits<{
  'update:role': [value: 'customer' | 'admin']
  'update:policy': [value: string | null]
  'new-conversation': []
}>()

const { policies, isLoading: isPoliciesLoading } = usePolicies()

const roleItems = [
  { title: 'Customer', value: 'customer' },
  { title: 'Admin', value: 'admin' },
]

const policyItems = computed(() =>
  (policies.value ?? []).map((p) => ({
    title: p.name,
    value: p.name,
  })),
)
</script>

<style lang="scss" scoped>
.agent-config {
  padding: 8px 0;
}
</style>
