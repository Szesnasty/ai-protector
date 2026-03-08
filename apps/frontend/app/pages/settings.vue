<template>
  <v-container class="settings-page" style="max-width: 720px;">
    <v-row>
      <v-col cols="12">
        <div class="d-flex align-center ga-2 mb-1">
          <h1 class="text-h5">
            <v-icon start>mdi-cog</v-icon>
            Settings
          </h1>
          <v-chip size="x-small" variant="outlined" label prepend-icon="mdi-shield-check" class="ml-2 text-medium-emphasis">
            Keys handled locally
          </v-chip>
        </div>
        <p class="text-body-2 text-medium-emphasis mb-4">
          Your API keys let AI Protector call LLM providers on your behalf.
        </p>

        <!-- Security explainer -->
        <v-card variant="flat" class="mb-2 security-explainer">
          <v-card-text class="py-3 px-4">
            <div class="d-flex align-center mb-3">
              <v-icon icon="mdi-shield-lock" size="20" class="mr-2" />
              <span class="text-subtitle-2 font-weight-bold">How we protect your keys</span>
            </div>
            <div class="security-points">
              <div class="d-flex align-start ga-2 mb-3">
                <v-icon icon="mdi-database-off" size="14" class="mt-1 flex-shrink-0" />
                <span class="text-body-2"><strong>Never stored on our server</strong> — keys live only in your browser</span>
              </div>
              <div class="d-flex align-start ga-2 mb-3">
                <v-icon icon="mdi-file-hidden" size="14" class="mt-1 flex-shrink-0" />
                <span class="text-body-2"><strong>Never logged</strong> — server records model and latency, never your key</span>
              </div>
              <div class="d-flex align-start ga-2 mb-3">
                <v-icon icon="mdi-arrow-right-bold" size="14" class="mt-1 flex-shrink-0" />
                <span class="text-body-2"><strong>Pass-through only</strong> — forwarded once, then immediately discarded</span>
              </div>
              <div class="d-flex align-start ga-2">
                <v-icon icon="mdi-web-lock" size="14" class="mt-1 flex-shrink-0" />
                <span class="text-body-2"><strong>CSP-restricted</strong> — browser connects only to our proxy and LLM APIs</span>
              </div>
            </div>
          </v-card-text>
        </v-card>

        <!-- Local-only callout -->
        <p class="text-caption text-medium-emphasis mb-6 ml-1">
          <v-icon size="12" class="mr-1">mdi-information-outline</v-icon>
          All keys are stored only in this browser and never persisted on AI Protector servers.
          <a href="https://github.com/Szesnasty/ai-protector/blob/main/SECURITY.md" target="_blank" rel="noopener" class="text-primary text-decoration-none security-link">
            How key storage works
            <v-icon size="10" class="ml-0">mdi-open-in-new</v-icon>
          </a>
        </p>

        <!-- Provider cards -->
        <v-card
          v-for="provider in PROVIDERS"
          :key="provider.id"
          variant="outlined"
          class="mb-3 provider-card"
        >
          <v-card-text class="d-flex align-center">
            <v-icon :icon="provider.icon" class="mr-3" size="28" />
            <div class="flex-grow-1">
              <div class="d-flex align-center ga-2">
                <span class="text-subtitle-1 font-weight-medium">{{ provider.name }}</span>
                <v-chip
                  v-if="getStoredKey(provider.id)"
                  size="x-small"
                  color="success"
                  variant="tonal"
                  label
                  prepend-icon="mdi-check-circle"
                >
                  Configured
                </v-chip>
              </div>
              <div v-if="getStoredKey(provider.id)" class="text-body-2 text-medium-emphasis mt-1">
                <code>{{ getStoredKey(provider.id)!.maskedKey }}</code>
                <span class="text-caption text-medium-emphasis ml-2">
                  <v-icon size="11" class="mr-1" style="opacity: 0.6">mdi-content-save-outline</v-icon>
                  {{ getStoredKey(provider.id)!.remembered ? 'saved locally' : 'this session only' }}
                </span>
              </div>
              <div v-else class="text-caption text-medium-emphasis mt-1">
                No key added — enable {{ provider.name }} models
              </div>
            </div>

            <!-- Key exists: Remove button -->
            <v-btn
              v-if="getStoredKey(provider.id)"
              variant="text"
              size="small"
              class="remove-btn"
            >
              <v-icon start size="14">mdi-delete-outline</v-icon>
              <span @click="handleRemove(provider.id, provider.name)">Remove</span>
            </v-btn>

            <!-- No key: Add button -->
            <v-btn
              v-else
              variant="outlined"
              color="primary"
              size="small"
              @click="openAddDialog(provider)"
            >
              <v-icon start size="16">mdi-plus</v-icon>
              Add Key
            </v-btn>
          </v-card-text>
        </v-card>

        <!-- Ollama info -->
        <v-card variant="outlined" class="mt-4 provider-card">
          <v-card-text class="d-flex align-center">
            <v-icon icon="mdi-server" class="mr-3" size="28" />
            <div class="flex-grow-1">
              <div class="d-flex align-center ga-2">
                <span class="text-subtitle-1 font-weight-medium">Ollama</span>
                <v-chip size="x-small" variant="outlined" label prepend-icon="mdi-laptop" class="text-medium-emphasis">
                  Local
                </v-chip>
              </div>
              <span class="text-caption text-medium-emphasis">Always available — runs locally, no API key needed</span>
            </div>
          </v-card-text>
        </v-card>
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
          <p class="text-caption text-medium-emphasis mb-3">
            <v-icon size="12" class="mr-1">mdi-shield-check</v-icon>
            Stored locally in this browser — you can remove it at any time.
          </p>

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
            hint="Saved in this browser's local storage — survives restarts. Otherwise cleared when you close the tab."
            persistent-hint
            density="compact"
          />

          <v-alert
            type="info"
            variant="tonal"
            density="compact"
            class="mt-3"
          >
            Your key is sent to {{ addProvider?.name }} via our proxy, used for a single LLM call, then discarded. Never written to any database or log.
          </v-alert>
        </v-card-text>

        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="addDialog = false">Cancel</v-btn>
          <v-btn
            class="btn-action"
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

  const mode = addRemember.value ? 'saved locally' : 'this session only'
  snackbarText.value = `${addProvider.value.name} key saved (${mode})`
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

<style lang="scss" scoped>
.security-explainer {
  background: rgba(var(--v-theme-on-surface), 0.04) !important;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.08);
  border-radius: 12px !important;

  .security-points {
    padding-left: 28px;
  }

  code {
    font-size: 0.8em;
    padding: 1px 5px;
    border-radius: 3px;
    background: rgba(var(--v-theme-on-surface), 0.08);
  }
}

.security-link {
  &:hover {
    text-decoration: underline !important;
  }
}

.provider-card {
  transition: border-color 0.2s ease;
  border-color: rgba(var(--v-border-color), var(--v-border-opacity));

  code {
    font-size: 0.8em;
    padding: 1px 5px;
    border-radius: 3px;
    background: rgba(var(--v-theme-on-surface), 0.08);
  }
}

.remove-btn {
  color: rgba(var(--v-theme-on-surface), 0.4) !important;
  font-size: 0.8rem;

  &:hover {
    color: rgba(var(--v-theme-on-surface), 0.7) !important;
  }
}
</style>
