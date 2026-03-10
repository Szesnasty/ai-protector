<template>
  <v-container fluid class="guide-page" style="max-width: 960px">
    <div class="d-flex align-center mb-6">
      <v-btn icon="mdi-arrow-left" variant="text" @click="navigateTo('/agents')" />
      <div class="ml-2">
        <h1 class="text-h5">Integration Guide</h1>
        <v-breadcrumbs :items="breadcrumbs" density="compact" class="pa-0" />
      </div>
    </div>

    <!-- Hosting requirement banner -->
    <v-alert type="info" variant="tonal" class="mb-6" icon="mdi-server-network">
      <v-alert-title>AI Protector must be running</v-alert-title>
      <p class="mt-1 mb-2">
        The generated integration kit connects to a running AI Protector instance.
        Your agent calls the proxy service at runtime for RBAC enforcement, limit checking,
        trace logging, and full security pipeline scans.
      </p>
      <p class="mb-0 text-body-2 text-medium-emphasis">
        AI Protector runs on a single machine via Docker Compose.
        Core stack (proxy + DB + cache) uses ~280 MB.
        With all ML scanners (LLM Guard, NeMo, Presidio) loaded: ~1.2 GB.
        No GPU needed unless you use local LLM inference via Ollama.
      </p>
    </v-alert>

    <!-- Section 1 -->
    <section class="mb-8">
      <h2 class="text-h6 mb-3 d-flex align-center ga-2">
        <v-icon icon="mdi-package-variant-closed" size="22" />
        1. What is included
      </h2>
      <v-table density="compact" class="guide-table">
        <thead>
          <tr>
            <th>File</th>
            <th>Purpose</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><code>rbac.yaml</code></td>
            <td>Role-to-tool access matrix — defines which roles can call which tools</td>
          </tr>
          <tr>
            <td><code>limits.yaml</code></td>
            <td>Token, cost, and tool usage limits per role and per tool</td>
          </tr>
          <tr>
            <td><code>policy.yaml</code></td>
            <td>Scanner thresholds, PII handling mode, output filtering rules</td>
          </tr>
          <tr>
            <td><code>protected_agent.py</code></td>
            <td>LangGraph integration wrapper — pre/post-tool gate nodes and RBAC/Limits services</td>
          </tr>
          <tr>
            <td><code>.env.protector</code></td>
            <td>Environment variables — proxy URL, agent ID, policy pack, rollout mode</td>
          </tr>
          <tr>
            <td><code>test_security.py</code></td>
            <td>Generated security validation tests (5 tests: RBAC, injection, PII, confirmation, authorized access)</td>
          </tr>
          <tr>
            <td><code>README.md</code></td>
            <td>Step-by-step integration instructions</td>
          </tr>
        </tbody>
      </v-table>
    </section>

    <!-- Section 2 -->
    <section class="mb-8">
      <h2 class="text-h6 mb-3 d-flex align-center ga-2">
        <v-icon icon="mdi-folder-move" size="22" />
        2. Copy the files into your project
      </h2>
      <p class="text-body-2 mb-3">
        Place the generated files inside your agent repository:
      </p>
      <v-sheet rounded class="pa-4 code-block mb-3">
        <pre class="text-body-2"><code>your-agent/
├─ app/
├─ graph.py
├─ tools.py
├─ protector/
│  ├─ rbac.yaml
│  ├─ limits.yaml
│  ├─ policy.yaml
│  ├─ protected_agent.py
│  ├─ .env.protector
│  └─ test_security.py</code></pre>
      </v-sheet>
    </section>

    <!-- Section 3 -->
    <section class="mb-8">
      <h2 class="text-h6 mb-3 d-flex align-center ga-2">
        <v-icon icon="mdi-key-variant" size="22" />
        3. Load environment variables
      </h2>
      <p class="text-body-2 mb-3">
        Load the values from <code>.env.protector</code> into your application environment:
      </p>
      <v-sheet rounded class="pa-4 code-block mb-3">
        <pre class="text-body-2"><code># .env.protector (generated)
AI_PROTECTOR_URL=http://localhost:8000
AI_PROTECTOR_POLICY=customer_support
AI_PROTECTOR_AGENT_ID=&lt;your-agent-uuid&gt;
AI_PROTECTOR_MODE=observe</code></pre>
      </v-sheet>
      <p class="text-body-2 text-medium-emphasis">
        The <code>AI_PROTECTOR_MODE</code> controls enforcement behavior:
        <strong>observe</strong> (log only) → <strong>warn</strong> (log + warn) → <strong>enforce</strong> (block violations).
      </p>
    </section>

    <!-- Section 4 -->
    <section class="mb-8">
      <h2 class="text-h6 mb-3 d-flex align-center ga-2">
        <v-icon icon="mdi-code-braces" size="22" />
        4. Integrate with your LangGraph agent
      </h2>
      <p class="text-body-2 mb-3">
        Import the generated protection module and wire it into your graph:
      </p>
      <v-sheet rounded class="pa-4 code-block mb-3">
        <pre class="text-body-2"><code>from langgraph.graph import StateGraph
from protector.protected_agent import (
    add_protection,
    PreToolGate,
    PostToolGate,
)

# Build your graph as usual
graph = StateGraph(AgentState)
graph.add_node("agent", agent_node)
graph.add_node("tools", tool_node)

# Add AI Protector security nodes
add_protection(graph)

# Wire the gates into your graph flow:
#   agent → pre_tool_gate → tools → post_tool_gate → agent
graph.add_edge("agent", "pre_tool_gate")
graph.add_edge("pre_tool_gate", "tools")
graph.add_edge("tools", "post_tool_gate")
graph.add_edge("post_tool_gate", "agent")

app = graph.compile()</code></pre>
      </v-sheet>
      <p class="text-body-2 mb-3">
        Or use the gate classes directly for finer control:
      </p>
      <v-sheet rounded class="pa-4 code-block">
        <pre class="text-body-2"><code># Manual pre-tool check
gate = PreToolGate()
result = gate.check(role="customer", tool="issueRefund")

if result["allowed"]:
    output = issueRefund(order_id="123")
    # Scan the output
    post = PostToolGate()
    scan = post.scan(str(output))
    if not scan["clean"]:
        print("Findings:", scan["findings"])</code></pre>
      </v-sheet>
    </section>

    <!-- Section 5 -->
    <section class="mb-8">
      <h2 class="text-h6 mb-3 d-flex align-center ga-2">
        <v-icon icon="mdi-shield-check" size="22" />
        5. What protection the agent gets
      </h2>

      <v-expansion-panels variant="accordion" class="mb-4">
        <v-expansion-panel>
          <v-expansion-panel-title>
            <v-icon icon="mdi-gate" class="mr-2" size="20" />
            Pre-tool gate
          </v-expansion-panel-title>
          <v-expansion-panel-text>
            <p class="mb-2">Checks whether a tool call is allowed <strong>before</strong> execution:</p>
            <ul class="ml-4 mb-3">
              <li><strong>RBAC</strong> — role must have permission for the tool (with inheritance)</li>
              <li><strong>Rate limits</strong> — per-role and per-tool session limits</li>
              <li><strong>Confirmation</strong> — high/critical sensitivity tools can require confirmation</li>
            </ul>
            <v-sheet rounded class="pa-3 code-block">
              <pre class="text-body-2"><code>role "customer" → issueRefund → ✅ allowed
role "customer" → getInternalSecrets → ❌ blocked (RBAC)
tool call 11/10 limit → ❌ blocked (rate limit)</code></pre>
            </v-sheet>
          </v-expansion-panel-text>
        </v-expansion-panel>

        <v-expansion-panel>
          <v-expansion-panel-title>
            <v-icon icon="mdi-eye-check" class="mr-2" size="20" />
            Post-tool gate
          </v-expansion-panel-title>
          <v-expansion-panel-text>
            <p class="mb-2">Scans tool outputs <strong>before</strong> they reach the LLM:</p>
            <ul class="ml-4 mb-3">
              <li><strong>PII detection</strong> — emails, phone numbers, SSNs</li>
              <li><strong>Secrets scanning</strong> — API keys, tokens</li>
              <li><strong>Injection detection</strong> — SQL injection, prompt injection patterns in output</li>
            </ul>
            <p class="text-body-2 text-medium-emphasis">
              The LLM receives sanitized output — never the raw tool result.
            </p>
          </v-expansion-panel-text>
        </v-expansion-panel>

        <v-expansion-panel>
          <v-expansion-panel-title>
            <v-icon icon="mdi-wall-fire" class="mr-2" size="20" />
            Proxy firewall (AI Protector pipeline)
          </v-expansion-panel-title>
          <v-expansion-panel-text>
            <p class="mb-2">
              When your agent calls the LLM through the AI Protector proxy,
              the full message set is scanned by the security pipeline:
            </p>
            <ul class="ml-4 mb-3">
              <li>
                <strong>NeMo Guardrails</strong> — semantic intent classification
                (role bypass, tool abuse, exfiltration, social engineering)
              </li>
              <li>
                <strong>LLM Guard</strong> — prompt injection detection with ML model
              </li>
              <li>
                <strong>Presidio PII</strong> — named entity recognition for personal data
              </li>
              <li>
                <strong>Secrets scanner</strong> — regex-based API key and credential detection
              </li>
              <li>
                <strong>Toxicity detection</strong> — content safety classification
              </li>
              <li>
                <strong>Custom rules</strong> — pattern-based allow/block rules
              </li>
            </ul>
            <p class="text-body-2 text-medium-emphasis">
              Policy decision: <strong>ALLOW</strong>, <strong>MODIFY</strong> (redact), or <strong>BLOCK</strong>.
            </p>
          </v-expansion-panel-text>
        </v-expansion-panel>
      </v-expansion-panels>
    </section>

    <!-- Section 6 -->
    <section class="mb-8">
      <h2 class="text-h6 mb-3 d-flex align-center ga-2">
        <v-icon icon="mdi-test-tube" size="22" />
        6. Run the generated security tests
      </h2>
      <v-sheet rounded class="pa-4 code-block mb-3">
        <pre class="text-body-2"><code>pytest protector/test_security.py -v</code></pre>
      </v-sheet>
      <p class="text-body-2 mb-3">The generated tests validate:</p>
      <v-table density="compact" class="guide-table">
        <thead>
          <tr>
            <th>Test</th>
            <th>What it checks</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><code>test_rbac_block_unknown_role</code></td>
            <td>Unknown roles are denied access to all tools</td>
          </tr>
          <tr>
            <td><code>test_rbac_allow_authorized</code></td>
            <td>Defined roles can access their assigned tools</td>
          </tr>
          <tr>
            <td><code>test_injection_blocked</code></td>
            <td>Injection detection is enabled with a valid threshold</td>
          </tr>
          <tr>
            <td><code>test_pii_redaction</code></td>
            <td>PII handling mode is configured correctly</td>
          </tr>
          <tr>
            <td><code>test_confirmation_required</code></td>
            <td>High/critical sensitivity tools require confirmation</td>
          </tr>
        </tbody>
      </v-table>
    </section>

    <!-- Section 7 -->
    <section class="mb-8">
      <h2 class="text-h6 mb-3 d-flex align-center ga-2">
        <v-icon icon="mdi-chart-timeline-variant" size="22" />
        7. Observability
      </h2>
      <p class="text-body-2 mb-3">
        Every request through the AI Protector proxy is recorded as a trace, including:
      </p>
      <v-row>
        <v-col v-for="item in observabilityItems" :key="item.label" cols="12" sm="6" md="4">
          <v-card variant="tonal" class="pa-3 h-100">
            <div class="d-flex align-center ga-2 mb-1">
              <v-icon :icon="item.icon" size="18" />
              <span class="text-subtitle-2">{{ item.label }}</span>
            </div>
            <p class="text-body-2 text-medium-emphasis mb-0">{{ item.description }}</p>
          </v-card>
        </v-col>
      </v-row>
    </section>

    <!-- Section 8 — Hosting -->
    <section class="mb-8">
      <h2 class="text-h6 mb-3 d-flex align-center ga-2">
        <v-icon icon="mdi-server" size="22" />
        8. Hosting AI Protector
      </h2>

      <v-alert type="info" variant="tonal" class="mb-4" density="compact" icon="mdi-information">
        AI Protector runs as a Docker Compose stack. No cloud-specific dependencies.
      </v-alert>

      <p class="text-body-2 mb-3">Minimum deployment:</p>

      <v-sheet rounded class="pa-4 code-block mb-4">
        <pre class="text-body-2"><code># Clone the repo
git clone https://github.com/Szesnasty/ai-protector.git
cd ai-protector/infra

# Start the full stack
docker compose --profile full up -d

# Services:
#   proxy-service  → :8000  (security proxy + API)
#   frontend       → :3000  (management UI)
#   db             → :5432  (PostgreSQL)
#   redis          → :6379  (cache)
#   langfuse       → :3001  (tracing, optional)
#   ollama         → :11434 (local LLM, optional)</code></pre>
      </v-sheet>

      <v-table density="compact" class="guide-table mb-4">
        <thead>
          <tr>
            <th>Service</th>
            <th>RAM</th>
            <th>Required</th>
            <th>Notes</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="svc in services" :key="svc.name">
            <td><code>{{ svc.name }}</code></td>
            <td>{{ svc.ram }}</td>
            <td>
              <v-icon
                :icon="svc.required ? 'mdi-check-circle' : 'mdi-circle-outline'"
                :color="svc.required ? 'success' : 'grey'"
                size="18"
              />
            </td>
            <td class="text-body-2 text-medium-emphasis">{{ svc.notes }}</td>
          </tr>
        </tbody>
      </v-table>

      <p class="text-body-2 text-medium-emphasis mb-2">
        <strong>Minimal (no ML scanners):</strong> ~280 MB — proxy base + PostgreSQL + Redis.
        Suitable for RBAC-only enforcement or proxy_only framework.
      </p>
      <p class="text-body-2 text-medium-emphasis mb-2">
        <strong>With all scanners:</strong> ~1.2 GB — adds LLM Guard, NeMo, and Presidio
        (models lazy-loaded on first request, not at startup).
      </p>
      <p class="text-body-2 text-medium-emphasis">
        Runs on a $6–12/month VPS (Hetzner, DigitalOcean) or any machine with Docker.
        2 GB RAM recommended for full scanner stack.
      </p>
    </section>

    <!-- CTA -->
    <v-card variant="tonal" color="primary" class="pa-6 text-center">
      <h3 class="text-h6 mb-2">Ready to protect your agent?</h3>
      <p class="text-body-2 mb-4">
        Use the Agent Wizard to register your agent, define tools and roles,
        and generate your integration kit.
      </p>
      <v-btn color="primary" size="large" prepend-icon="mdi-magic-staff" to="/agents/new">
        Open Agent Wizard
      </v-btn>
    </v-card>
  </v-container>
</template>

<script setup lang="ts">
definePageMeta({ title: 'Integration Guide' })

const breadcrumbs = [
  { title: 'Agents', to: '/agents' },
  { title: 'Integration Guide' },
]

const observabilityItems = [
  { icon: 'mdi-account-circle', label: 'Role', description: 'Which role made the request' },
  { icon: 'mdi-wrench', label: 'Tool calls', description: 'Which tools were attempted and their arguments' },
  { icon: 'mdi-shield-check', label: 'Decisions', description: 'Allowed vs blocked with reason' },
  { icon: 'mdi-file-document', label: 'Policy applied', description: 'Which policy pack and scanners ran' },
  { icon: 'mdi-speedometer', label: 'Limit checks', description: 'Current usage vs budget limits' },
  { icon: 'mdi-test-tube', label: 'Security results', description: 'Scanner findings and risk scores' },
]

const services = [
  { name: 'proxy-service (base)', ram: '~150 MB', required: true, notes: 'Core proxy + API (without ML models)' },
  { name: '  + LLM Guard', ram: '~500 MB', required: false, notes: 'PromptInjection (DeBERTa) + Toxicity (RoBERTa) + Secrets — lazy-loaded on first scan' },
  { name: '  + NeMo Guardrails', ram: '~200 MB', required: false, notes: 'FastEmbed all-MiniLM-L6-v2 (ONNX) — lazy-loaded on first scan' },
  { name: '  + Presidio PII', ram: '~200 MB', required: false, notes: 'spaCy NER model — lazy-loaded on first scan' },
  { name: 'PostgreSQL', ram: '~100 MB', required: true, notes: 'Database for agents, traces, policies' },
  { name: 'Redis', ram: '~30 MB', required: true, notes: 'Cache and rate limiting' },
  { name: 'frontend', ram: '~150 MB', required: false, notes: 'Management UI (optional for headless use)' },
  { name: 'Langfuse', ram: '~200 MB', required: false, notes: 'Request tracing and observability' },
  { name: 'Ollama', ram: '2–4 GB', required: false, notes: 'Only if using local LLM inference' },
]
</script>

<style lang="scss" scoped>
.code-block {
  background: rgba(var(--v-theme-surface), 0.6);
  border: 1px solid rgba(var(--v-theme-primary), 0.15);
  overflow-x: auto;
  font-family: monospace;

  pre {
    margin: 0;
    white-space: pre;
  }

  code {
    font-size: 13px;
    line-height: 1.6;
  }
}

.guide-table {
  background: transparent !important;

  th {
    font-weight: 600 !important;
  }
}
</style>
