import { ref, reactive, computed } from 'vue'
import type { AgentMessage, AgentTrace, FirewallDecision } from '~/types/agent'
import { agentService } from '~/services/agentService'

export function useAgentChat() {
  const messages = ref<AgentMessage[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  const config = reactive({
    role: 'customer' as 'customer' | 'admin',
    policy: null as string | null,
  })

  const sessionId = ref(generateSessionId())

  const lastTrace = computed<AgentTrace | null>(() => {
    for (let i = messages.value.length - 1; i >= 0; i--) {
      const msg = messages.value[i]
      if (msg?.agent_trace) return msg.agent_trace
    }
    return null
  })

  const lastFirewallDecision = computed<FirewallDecision | null>(() => {
    for (let i = messages.value.length - 1; i >= 0; i--) {
      const msg = messages.value[i]
      if (msg?.firewall_decision) return msg.firewall_decision
    }
    return null
  })

  function generateSessionId(): string {
    return `agent-${crypto.randomUUID()}`
  }

  function addSystemMessage(content: string) {
    messages.value.push({
      id: crypto.randomUUID(),
      role: 'system',
      content,
      timestamp: new Date(),
    })
  }

  async function sendMessage(text: string) {
    error.value = null

    // Add user message
    messages.value.push({
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
      timestamp: new Date(),
    })

    isLoading.value = true

    try {
      const response = await agentService.chat({
        message: text,
        user_role: config.role,
        session_id: sessionId.value,
        ...(config.policy ? { policy: config.policy } : {}),
      })

      messages.value.push({
        id: crypto.randomUUID(),
        role: 'assistant',
        content: response.response,
        tools_called: response.tools_called,
        agent_trace: response.agent_trace,
        firewall_decision: response.firewall_decision,
        timestamp: new Date(),
      })
    }
    catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to get response from agent'
      error.value = msg

      messages.value.push({
        id: crypto.randomUUID(),
        role: 'assistant',
        content: `⚠️ Error: ${msg}`,
        timestamp: new Date(),
      })
    }
    finally {
      isLoading.value = false
    }
  }

  function switchRole(newRole: 'customer' | 'admin') {
    if (newRole === config.role) return
    config.role = newRole
    sessionId.value = generateSessionId()
    messages.value = []
    addSystemMessage(`Switched to **${newRole}** role`)
  }

  function newConversation() {
    sessionId.value = generateSessionId()
    messages.value = []
    error.value = null
    addSystemMessage('New conversation started')
  }

  return {
    messages,
    isLoading,
    error,
    config,
    sessionId,
    lastTrace,
    lastFirewallDecision,
    sendMessage,
    switchRole,
    newConversation,
  }
}
