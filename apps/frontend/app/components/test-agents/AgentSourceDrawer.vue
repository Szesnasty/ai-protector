<template>
  <v-navigation-drawer
    :model-value="modelValue"
    location="right"
    :width="720"
    temporary
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div class="d-flex align-center pa-3 border-b">
      <v-icon class="mr-2">mdi-code-braces</v-icon>
      <span class="text-subtitle-1 font-weight-bold flex-grow-1">Agent Source &amp; Config</span>
      <v-btn icon="mdi-close" variant="text" size="small" @click="emit('update:modelValue', false)" />
    </div>

    <v-tabs v-model="activeTab" density="compact" class="border-b">
      <v-tab value="tree">
        <v-icon start size="16">mdi-file-tree</v-icon>
        Files
      </v-tab>
      <v-tab value="source">
        <v-icon start size="16">mdi-code-tags</v-icon>
        Source Code
      </v-tab>
      <v-tab value="config">
        <v-icon start size="16">mdi-shield-lock-outline</v-icon>
        Loaded Config
      </v-tab>
    </v-tabs>

    <!-- Loading state -->
    <div v-if="loading" class="text-center pa-12">
      <v-progress-circular indeterminate size="32" />
      <p class="text-body-2 text-medium-emphasis mt-2">Loading source files...</p>
    </div>

    <!-- File Tree Tab -->
    <div v-else-if="activeTab === 'tree'" class="pa-3">
      <p class="text-caption text-medium-emphasis mb-3">
        Agent project structure — files marked with
        <v-icon size="12" color="warning">mdi-shield</v-icon>
        are AI Protector security integration.
      </p>
      <div class="file-tree font-mono text-body-2">
        <div
          v-for="node in treeNodes"
          :key="node.path"
          class="tree-node d-flex align-center ga-1 py-1 px-1 rounded"
          :class="{
            'tree-dir': node.type === 'dir',
            'tree-clickable': node.type !== 'dir',
            'tree-config': node.type === 'config',
          }"
          :style="{ paddingLeft: `${(node.depth ?? 0) * 16 + 4}px` }"
          @click="handleTreeClick(node)"
        >
          <v-icon :size="14" :color="treeIconColor(node)">{{ treeIcon(node) }}</v-icon>
          <span :class="{ 'font-weight-bold': node.type === 'dir', 'text-warning': node.icon === 'security' }">
            {{ treeName(node) }}
          </span>
          <v-chip
            v-if="node.icon === 'security'"
            size="x-small"
            color="warning"
            variant="tonal"
            class="ml-1"
          >
            AI Protector
          </v-chip>
          <v-chip
            v-if="node.icon === 'config'"
            size="x-small"
            color="info"
            variant="tonal"
            class="ml-1"
          >
            wizard generated
          </v-chip>
        </div>
      </div>

      <!-- Legend -->
      <v-divider class="my-3" />
      <div class="d-flex flex-wrap ga-2">
        <v-chip size="x-small" variant="tonal" color="warning" prepend-icon="mdi-shield">Security Gate</v-chip>
        <v-chip size="x-small" variant="tonal" color="info" prepend-icon="mdi-cog">Wizard Config</v-chip>
        <v-chip size="x-small" variant="tonal" prepend-icon="mdi-wrench">Tool Implementation</v-chip>
        <v-chip size="x-small" variant="tonal" prepend-icon="mdi-database">Mock Data</v-chip>
      </div>
    </div>

    <!-- Source Code Tab -->
    <div v-else-if="activeTab === 'source'" class="d-flex flex-column" style="height: calc(100vh - 100px)">
      <!-- File selector -->
      <div class="pa-2 border-b">
        <v-select
          v-model="selectedFile"
          :items="sourceFileItems"
          item-title="label"
          item-value="path"
          variant="outlined"
          density="compact"
          hide-details
          prepend-inner-icon="mdi-file-code-outline"
        >
          <template #item="{ props: itemProps, item }">
            <v-list-item v-bind="itemProps">
              <template #prepend>
                <v-icon size="16" :color="item.raw.iconColor">{{ item.raw.icon }}</v-icon>
              </template>
              <v-list-item-subtitle>{{ item.raw.desc }}</v-list-item-subtitle>
            </v-list-item>
          </template>
        </v-select>
      </div>

      <!-- File description -->
      <div v-if="selectedFileMeta" class="pa-2 border-b bg-surface-light">
        <div class="d-flex align-center ga-1">
          <v-icon size="14" color="primary">mdi-information-outline</v-icon>
          <span class="text-caption">{{ selectedFileMeta.description }}</span>
        </div>
        <!-- Color-coded legend -->
        <div v-if="fileCategories.length" class="mt-2">
          <div class="d-flex align-center ga-1 mb-1">
            <v-icon size="12" color="warning">mdi-palette</v-icon>
            <span class="text-caption text-medium-emphasis font-weight-medium">AI Protector integration:</span>
          </div>
          <div class="d-flex flex-wrap ga-1">
            <v-chip
              v-for="cat in fileCategories"
              :key="cat.key"
              size="x-small"
              variant="flat"
              :style="{ background: cat.bg, color: cat.color, border: `1px solid ${cat.color}40` }"
            >
              <v-icon start size="10">{{ cat.icon }}</v-icon>
              {{ cat.label }}
            </v-chip>
          </div>
        </div>
      </div>

      <!-- Code viewer -->
      <div class="flex-grow-1 overflow-y-auto">
        <!-- eslint-disable-next-line vue/no-v-html -- AI Protector lines highlighted -->
        <pre v-if="selectedFileContent" class="source-code pa-3"><code v-html="highlightedSource" /></pre>
        <div v-else class="text-center text-medium-emphasis pa-12">
          <v-icon size="48" class="mb-2">mdi-file-code-outline</v-icon>
          <p class="text-body-2">Select a file to view its source code</p>
        </div>
      </div>
    </div>

    <!-- Loaded Config Tab -->
    <div v-else-if="activeTab === 'config'" class="d-flex flex-column" style="height: calc(100vh - 100px)">
      <div v-if="!configLoaded" class="text-center text-medium-emphasis pa-12">
        <v-icon size="48" class="mb-2">mdi-shield-off-outline</v-icon>
        <p class="text-body-2">No config loaded yet.</p>
        <p class="text-caption">Select an agent and click "Load Config" first.</p>
      </div>

      <template v-else>
        <!-- Config file selector -->
        <div class="pa-2 border-b">
          <v-select
            v-model="selectedConfig"
            :items="configFileItems"
            item-title="label"
            item-value="key"
            variant="outlined"
            density="compact"
            hide-details
            prepend-inner-icon="mdi-shield-lock-outline"
          >
            <template #item="{ props: itemProps, item }">
              <v-list-item v-bind="itemProps">
                <template #prepend>
                  <v-icon size="16" color="info">{{ item.raw.icon }}</v-icon>
                </template>
                <v-list-item-subtitle>{{ item.raw.desc }}</v-list-item-subtitle>
              </v-list-item>
            </template>
          </v-select>
        </div>

        <!-- Config description -->
        <div class="pa-2 border-b bg-surface-light">
          <div class="d-flex align-center ga-1">
            <v-icon size="14" color="info">mdi-information-outline</v-icon>
            <span class="text-caption">{{ configDescription }}</span>
          </div>
        </div>

        <!-- Config YAML viewer -->
        <div class="flex-grow-1 overflow-y-auto">
          <pre v-if="selectedConfigContent" class="source-code pa-3"><code>{{ selectedConfigContent }}</code></pre>
          <div v-else class="text-center text-medium-emphasis pa-12">
            <v-icon size="48" class="mb-2">mdi-file-document-outline</v-icon>
            <p class="text-body-2">Select a config file to view</p>
          </div>
        </div>
      </template>
    </div>
  </v-navigation-drawer>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'

// ─── Props & Emits ───

const props = defineProps<{
  modelValue: boolean
  baseUrl: string
  configLoaded: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

// ─── State ───

const activeTab = ref('tree')
const loading = ref(false)
const selectedFile = ref<string | null>(null)
const selectedConfig = ref('rbac.yaml')

interface TreeNode {
  path: string
  type: 'dir' | 'file' | 'config'
  icon?: string
  label?: string
  depth?: number
}

interface SourceFile {
  content: string
  language: string
  description?: string
  highlight?: string[]
}

const sourceData = ref<{
  framework: string
  files: Record<string, SourceFile>
  tree: TreeNode[]
} | null>(null)

const loadedConfigs = ref<Record<string, string>>({})

// ─── Fetch source files when drawer opens ───

watch(() => props.modelValue, async (open) => {
  if (open && !sourceData.value) {
    await fetchSourceFiles()
  }
  if (open && props.configLoaded) {
    await fetchLoadedConfig()
  }
})

watch(() => props.configLoaded, async (loaded) => {
  if (loaded && props.modelValue) {
    await fetchLoadedConfig()
  }
})

async function fetchSourceFiles() {
  loading.value = true
  try {
    const res = await fetch(`${props.baseUrl}/source-files`)
    if (res.ok) {
      sourceData.value = await res.json()
      // Auto-select first source file
      const firstFile = Object.keys(sourceData.value?.files ?? {}).find(k => k.includes('graph.') || k.includes('protection.'))
        || Object.keys(sourceData.value?.files ?? {})[0]
      if (firstFile) selectedFile.value = firstFile
    }
  } catch { /* ignore */ }
  finally { loading.value = false }
}

async function fetchLoadedConfig() {
  try {
    const res = await fetch(`${props.baseUrl}/loaded-config`)
    if (res.ok) {
      const data = await res.json()
      if (data.loaded) loadedConfigs.value = data.configs
    }
  } catch { /* ignore */ }
}

// ─── Tree helpers ───

const treeNodes = computed(() => {
  const raw = sourceData.value?.tree ?? []
  return raw.map(node => ({
    ...node,
    depth: (node.path.match(/\//g) || []).length - (node.type === 'dir' ? 1 : 0),
  }))
})

function treeIcon(node: TreeNode): string {
  if (node.type === 'dir') return 'mdi-folder-outline'
  if (node.icon === 'security') return 'mdi-shield'
  if (node.icon === 'config') return 'mdi-cog'
  if (node.icon === 'entry') return 'mdi-play-circle-outline'
  if (node.icon === 'tool') return 'mdi-wrench'
  if (node.icon === 'data') return 'mdi-database'
  if (node.icon === 'schema') return 'mdi-code-json'
  return 'mdi-file-outline'
}

function treeIconColor(node: TreeNode): string {
  if (node.icon === 'security') return 'warning'
  if (node.icon === 'config') return 'info'
  if (node.icon === 'entry') return 'success'
  if (node.type === 'dir') return 'primary'
  return ''
}

function treeName(node: TreeNode): string {
  const parts = node.path.split('/')
  return parts[parts.length - 1] || parts[parts.length - 2] + '/'
}

function handleTreeClick(node: TreeNode) {
  if (node.type === 'dir') return
  const path = node.path
  if (node.type === 'config') {
    activeTab.value = 'config'
    const configName = path.split('/').pop() ?? ''
    if (configName in loadedConfigs.value) {
      selectedConfig.value = configName
    }
  } else if (path in (sourceData.value?.files ?? {})) {
    activeTab.value = 'source'
    selectedFile.value = path
  }
}

// ─── Source code helpers ───

const sourceFileItems = computed(() => {
  const files = sourceData.value?.files ?? {}
  return Object.entries(files).map(([path, file]) => ({
    path,
    label: path,
    desc: file.description ?? '',
    icon: path.includes('protection') || path.includes('graph')
      ? 'mdi-shield' : path.includes('tools') ? 'mdi-wrench' : 'mdi-file-code-outline',
    iconColor: path.includes('protection') || path.includes('graph') ? 'warning' : '',
  }))
})

const selectedFileMeta = computed(() => {
  if (!selectedFile.value || !sourceData.value) return null
  return sourceData.value.files[selectedFile.value]
})

const selectedFileContent = computed(() => {
  return selectedFileMeta.value?.content ?? null
})

// ─── AI Protector highlight categories ───

interface HlCategory {
  key: string
  color: string
  bg: string
  label: string
  icon: string
}

const CATEGORIES: Record<string, HlCategory> = {
  config:   { key: 'config',   color: '#42A5F5', bg: 'rgba(66,165,245,0.18)',  label: 'Config Loading',     icon: 'mdi-cog' },
  rbac:     { key: 'rbac',     color: '#FFA726', bg: 'rgba(255,167,38,0.18)',  label: 'RBAC Gate',          icon: 'mdi-account-key' },
  limits:   { key: 'limits',   color: '#66BB6A', bg: 'rgba(102,187,106,0.18)', label: 'Rate Limits',        icon: 'mdi-speedometer' },
  scan:     { key: 'scan',     color: '#AB47BC', bg: 'rgba(171,71,188,0.18)',  label: 'Output Scan',        icon: 'mdi-magnify-scan' },
  proxy:    { key: 'proxy',    color: '#EF5350', bg: 'rgba(239,83,80,0.18)',   label: 'Proxy Firewall',     icon: 'mdi-shield-lock' },
  pipeline: { key: 'pipeline', color: '#26C6DA', bg: 'rgba(38,198,218,0.18)',  label: 'Security Pipeline',  icon: 'mdi-pipe' },
}

/** Determine which category a block marker belongs to by its text. */
function categoryFromMarker(line: string): string | null {
  if (/check_rbac|RBAC|Role-Based/i.test(line)) return 'rbac'
  if (/check_limits|Rate Limit|Budget|LimitsService/i.test(line)) return 'limits'
  if (/scan_output|PII|Injection.*scan|Output scan|post.?tool|PostToolGate/i.test(line)) return 'scan'
  if (/proxy|Pre-scan|firewall/i.test(line)) return 'proxy'
  if (/SecurityConfig|Config|Import|Load Config|YAML loader/i.test(line)) return 'config'
  if (/Security gate|protected_tool_call|security pipeline|PreToolGate|Gate func|Conditional Rout|Graph Wir/i.test(line)) return 'pipeline'
  return null
}

/** Determine category for a single (non-block) line. */
function categoryFromLine(line: string): string | null {
  // Proxy firewall (most specific first)
  if (/_proxy_scan\(|_proxy_llm_call\(|PROXY_POLICY|_ATTACK_INTENTS|proxy_firewall|\/v1\/scan/.test(line)) return 'proxy'
  // RBAC
  if (/check_rbac\(|RBACService|check_permission\(/.test(line)) return 'rbac'
  // Limits
  if (/check_limits\(|LimitsService|record_call\(|max_tool_calls/.test(line)) return 'limits'
  // Output scan
  if (/scan_output\(|PostToolGate|post_tool_gate|pii_redaction|injection_detection|\.scan\(/.test(line)) return 'scan'
  // Security pipeline
  if (/protected_tool_call\(|PreToolGate|pre_tool_gate|after_pre_gate|build_graph|← AI Protector/.test(line)) return 'pipeline'
  // Config loading
  if (/SecurityConfig|load_from_kit|load_from_files|load_from_dicts|get_config\(|reset_config\(/.test(line)) return 'config'
  if (/^\s*(from\s+protection\s+import|from\s+graph\s+import)/.test(line)) return 'config'
  return null
}

/** Categories that actually appear in the current file. */
const fileCategories = computed(() => {
  const raw = selectedFileContent.value
  if (!raw) return []
  const found = new Set<string>()
  for (const line of raw.split('\n')) {
    const cat = categoryFromLine(line) ?? categoryFromMarker(line)
    if (cat) found.add(cat)
  }
  // Stable order matching CATEGORIES declaration
  return Object.values(CATEGORIES).filter(c => found.has(c.key))
})

/**
 * Highlight AI Protector code blocks with category-specific colors.
 * Each line gets a colored left-border + tinted background matching
 * its security category (config, rbac, limits, scan, proxy, pipeline).
 */
const highlightedSource = computed(() => {
  const raw = selectedFileContent.value
  if (!raw) return ''

  const lines = raw.split('\n')
  let inBlock = false
  let blockCat: string | null = null
  const result: string[] = []

  for (const line of lines) {
    const escaped = line
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')

    // Detect block markers: ═══ AI PROTECTOR / ╔═══ / ╚═══
    const isMarkerOpen = /[═╔╗]+.*AI PROTECTOR/.test(line)
    const isMarkerClose = /[═╚╝]+$/.test(line) && inBlock

    if (isMarkerOpen) {
      inBlock = true
      blockCat = categoryFromMarker(line)
    }

    // Determine this line's category
    let cat: string | null = null
    if (inBlock) {
      cat = blockCat
    } else {
      cat = categoryFromLine(line)
      // Also catch standalone marker comments: # ═══ AI PROTECTOR — ...
      if (!cat && /^\s*#\s*═══.*AI PROTECTOR/.test(line)) {
        cat = categoryFromMarker(line)
      }
    }

    if (cat && cat in CATEGORIES) {
      const c = CATEGORIES[cat]!
      result.push(
        `<span class="hl-line" style="border-left-color:${c.color};background:${c.bg}">${escaped}</span>`
      )
    } else {
      result.push(escaped)
    }

    if (isMarkerClose) { inBlock = false; blockCat = null }
    // Single-line ═══...═══ patterns
    if (isMarkerOpen && /═══\s*$/.test(line)) { inBlock = false; blockCat = null }
  }

  return result.join('\n')
})

// ─── Config helpers ───

const configFileItems = computed(() => [
  { key: 'rbac.yaml', label: 'rbac.yaml', desc: 'Role-based access control', icon: 'mdi-account-key' },
  { key: 'limits.yaml', label: 'limits.yaml', desc: 'Rate limits & budgets', icon: 'mdi-speedometer' },
  { key: 'policy.yaml', label: 'policy.yaml', desc: 'Security scanners & policy', icon: 'mdi-shield-check' },
])

const configDescription = computed(() => {
  const descs: Record<string, string> = {
    'rbac.yaml': 'Defines which roles can access which tools, with scopes and sensitivity levels. Generated by the Agent Wizard based on your tool registrations.',
    'limits.yaml': 'Rate limits and budget constraints per role. Controls max tool calls, tokens, and cost per session.',
    'policy.yaml': 'Security scanner configuration — PII detection, injection blocking, toxicity thresholds, and output filtering rules.',
  }
  return descs[selectedConfig.value] ?? ''
})

const selectedConfigContent = computed(() => {
  return loadedConfigs.value[selectedConfig.value] ?? null
})
</script>

<style lang="scss" scoped>
.file-tree {
  .tree-node {
    transition: background-color 0.1s;
  }
  .tree-clickable {
    cursor: pointer;
    &:hover {
      background-color: rgba(var(--v-theme-primary), 0.08);
    }
  }
  .tree-config {
    cursor: pointer;
    &:hover {
      background-color: rgba(var(--v-theme-info), 0.08);
    }
  }
}

.source-code {
  margin: 0;
  font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;
  font-size: 12px;
  line-height: 1.5;
  tab-size: 4;
  white-space: pre;
  overflow-x: auto;
  background: rgba(0, 0, 0, 0.15);
  border-radius: 4px;

  code {
    font-family: inherit;
  }

  // AI Protector highlighted lines — category-colored left border + tinted bg
  :deep(.hl-line) {
    display: inline-block;
    width: 100%;
    border-left: 3px solid currentColor;
    padding-left: 8px;
    margin-left: -11px;
    padding-right: 4px;
    border-radius: 2px;
  }
}
</style>
