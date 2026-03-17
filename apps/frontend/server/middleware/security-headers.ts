export default defineEventHandler((event) => {
  const config = useRuntimeConfig()

  const apiBase: string = (config.public.apiBase as string) || 'http://localhost:8000'
  const agentBase: string = (config.public.agentApiBase as string) || 'http://localhost:8002'
  const testAgentPython: string = (config.public.testAgentPythonUrl as string) || 'http://localhost:8003'
  const testAgentGraph: string = (config.public.testAgentGraphUrl as string) || 'http://localhost:8004'

  // Known external LLM provider APIs (for compare page direct calls)
  const providerApis = [
    'https://api.openai.com',
    'https://api.anthropic.com',
    'https://api.mistral.ai',
    'https://generativelanguage.googleapis.com',
  ].join(' ')

  // Dev mode: allow HMR WebSocket
  const isDev = import.meta.dev
  const devSources = isDev ? ' ws://localhost:3000 ws://localhost:24678' : ''

  const connectSrc = `'self' ${apiBase} ${agentBase} ${testAgentPython} ${testAgentGraph} ${providerApis}${devSources}`

  const csp = [
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline'",
    "style-src 'self' 'unsafe-inline'",
    "font-src 'self' data:",
    "img-src 'self' data: blob:",
    `connect-src ${connectSrc}`,
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
  ].join('; ')

  setHeaders(event, {
    'Content-Security-Policy': csp,
    'X-Frame-Options': 'DENY',
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'Permissions-Policy': 'camera=(), microphone=(), geolocation=(), payment=()',
    'X-XSS-Protection': '0',
  })
})
