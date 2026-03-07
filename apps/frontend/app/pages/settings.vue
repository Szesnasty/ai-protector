<template>
  <v-container class="settings-page" style="max-width: 720px;">
    <v-row>
      <v-col cols="12">
        <h1 class="text-h5 mb-1">
          <v-icon start>mdi-cog</v-icon>
          Settings
        </h1>
        <p class="text-body-2 text-medium-emphasis mb-6">
          API keys are stored in your browser only. We never send them to our server for storage.
        </p>

        <!-- Provider cards -->
        <v-card
          v-for="provider in PROVIDERS"
          :key="provider.id"
          variant="outlined"
          class="mb-3"
        >
          <v-card-text class="d-flex align-center">
            <v-icon :icon="provider.icon" class="mr-3" size="28" />
            <div class="flex-grow-1">
              <div class="text-subtitle-1 font-weight-medium">{{ provider.name }}</div>
              <div v-if="getStoredKey(provider.id)" class="text-body-2 text-medium-emphasis">
                <code>{{ getStoredKey(provider.id)!.maskedKey }}</code>
                <v-chip
                  v-if="getStoredKey(provider.id)!.remembered"
                  size="x-small"
                  class="ml-2"
                  color="info"
                  variant="tonal"
                >
                  remembered
                </v-chip>
                <v-chip
                  v-else
                  size="x-small"
                  class="ml-2"
                  variant="tonal"
                >
                  session only
                </v-chip>
              </div>
            </div>

            <!-- Key exists: Remove button -->
            <v-btn
              v-if="getStoredKey(provider.id)"
              variant="text"
              color="error"
              size="small"
              @click="handleRemove(provider.id, provider.name)"
            >
              <v-icon start>mdi-delete-outline</v-icon>
              Remove
            </v-btn>

            <!-- No key: Add button -->
            <v-btn
              v-else
              variant="tonal"
              color="primary"
              size="small"
              @click="openAddDialog(provider)"
            >
              <v-icon start>mdi-plus</v-icon>
              Add Key
            </v-btn>
          </v-card-text>
        </v-card>

        <!-- Ollama info -->
        <v-alert
          type="info"
          variant="tonal"
          class="mt-4"
          density="compact"
        >
          <strong>Ollama</strong> (local) is always available — no API key needed.
        </v-alert>
      </v-col>
    </v-row>

    <!-- Add Key Dialog -->
    <v-dialog v-model="addDialog" max-width="480" persistent>
      <v-card>
        <v-card-title class="d-flex align-center">
          <v-icon :icon="addProvider?.icon" class="mr-2" />
          Add {{ addProvider?.name }} API Key
        </v-card-title>

        <v-card-text>
          <v-text-field
            v-model="addKeyValue"
            label="API Key"
            :placeholder="addProvider?.placeholder"
            variant="outlined"
            type="password"
            density="compact"
            autofocus
            class="mb-2"
            :error-messages="addKeyValue && addKeyValue.length < 5 ? 'Key seems too short' : ''"
          />

          <v-checkbox
            v-model="addRemember"
            label="Remember on this device"
            hint="Uses localStorage instead of sessionStorage — persists across browser sessions"
            persistent-hint
            density="compact"
          />

          <v-alert
            type="info"
            variant="tonal"
            density="compact"
            class="mt-3"
          >
            <v-icon start size="small">mdi-lock</v-icon>
            Your key is stored in this browser only and never sent to our server for storage.
          </v-alert>
        </v-card-text>

        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="addDialog = false">Cancel</v-btn>
          <v-btn
            color="primary"
            variant="flat"
            :disabled="!addKeyValue || addKeyValue.length < 5"
            @click="handleSave"
          >
            Save
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Snackbar -->
    <v-snackbar v-model="snackbar" :timeout="3000" :color="snackbarColor">
      {{ snackbarText }}
    </v-snackbar>
  </v-container>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useApiKeys, PROVIDERS } from '~/composables/useApiKeys'
import type { ProviderDef, StoredKey } from '~/composables/useApiKeys'

definePageMeta({ title: 'Settings' })

const { keys, saveKey, removeKey } = useApiKeys()

// Dialog state
const addDialog = ref(false)
const addProvider = ref<ProviderDef | null>(null)
const addKeyValue = ref('')
const addRemember = ref(false)

// Snackbar
const snackbar = ref(false)
const snackbarText = ref('')
const snackbarColor = ref('success')

function getStoredKey(providerId: string): StoredKey | undefined {
  return keys.value.find((k) => k.provider === providerId)
}

function openAddDialog(provider: ProviderDef) {
  addProvider.value = provider
  addKeyValue.value = ''
  addRemember.value = false
  addDialog.value = true
}

function handleSave() {
  if (!addProvider.value || !addKeyValue.value) return

  saveKey(addProvider.value.id, addKeyValue.value, addRemember.value)
  addDialog.value = false

  const mode = addRemember.value ? 'remembered' : 'session only'
  snackbarText.value = `✓ ${addProvider.value.name} key saved (${mode})`
  snackbarColor.value = 'success'
  snackbar.value = true
}

function handleRemove(providerId: string, providerName: string) {
  removeKey(providerId)
  snackbarText.value = `${providerName} key removed`
  snackbarColor.value = 'info'
  snackbar.value = true
}
</script>
