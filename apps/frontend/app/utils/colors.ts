/**
 * Unified semantic color system for the entire product.
 *
 * Color semantics:
 *   BLOCK / danger     → error (red)
 *   MODIFY / caution   → warning (amber)
 *   ALLOW / safe       → success (green)
 *   TOTAL / neutral    → primary (blue) or info
 *   Brand / navigation → secondary (teal) — never used for security states
 *
 * Hex palette (dark theme reference):
 *   error:   #EF4444  — punchy red for BLOCK / high-risk / danger
 *   warning: #F59E0B  — amber for MODIFY / caution / medium-risk
 *   success: #22C55E  — green for ALLOW / safe / low-risk
 *   primary: #7C8FD4  — muted indigo-blue for totals / baseline
 *   info:    #38BDF8  — cyan-blue for neutral metrics
 */

// ─── Decision colors ───────────────────────────────────────
export type Decision = 'ALLOW' | 'MODIFY' | 'BLOCK' | 'REDACT' | string

/** Vuetify color name for a pipeline decision */
export function decisionColor(decision: Decision | undefined | null): string {
  switch (decision) {
    case 'BLOCK': return 'error'
    case 'MODIFY': return 'warning'
    case 'ALLOW': return 'success'
    case 'REDACT': return 'orange'
    default: return 'grey'
  }
}

/** MDI icon for a pipeline decision */
export function decisionIcon(decision: Decision | undefined | null): string {
  switch (decision) {
    case 'BLOCK': return 'mdi-shield-off'
    case 'MODIFY': return 'mdi-shield-edit'
    case 'ALLOW': return 'mdi-shield-check'
    default: return 'mdi-shield-outline'
  }
}

/** Human-readable label: "BLOCKED — reason" */
export function decisionLabel(decision: Decision | undefined | null, reason?: string | null): string {
  const base = decision === 'BLOCK' ? 'Blocked'
    : decision === 'MODIFY' ? 'Modified'
    : decision === 'ALLOW' ? 'Allowed'
    : String(decision ?? 'Unknown')
  return reason ? `${base} — ${reason}` : base
}

// ─── Risk score colors ─────────────────────────────────────
// 4-tier scale: green → amber → orange → red
export function riskColor(score: number | null | undefined): string {
  if (score == null) return 'grey'
  if (score < 0.25) return 'success'
  if (score < 0.50) return 'warning'
  if (score < 0.75) return 'orange'
  return 'error'
}

/** CSS class variant for inline text coloring */
export function riskTextColor(score: number | null | undefined): string {
  if (score == null) return 'text-grey'
  if (score < 0.25) return 'text-success'
  if (score < 0.50) return 'text-warning'
  if (score < 0.75) return 'text-orange'
  return 'text-error'
}

// ─── Risk flag colors ──────────────────────────────────────
/** Vuetify color for a risk flag chip — accent only, not screaming */
export function flagColor(key: string, val?: unknown): string {
  // High-severity security flags → red accent
  if (key.includes('injection') || key === 'promptinjection') return 'error'
  if (key.includes('denylist') || key.includes('custom')) return 'error'
  if (key.includes('jailbreak')) return 'error'

  // Medium-severity → amber/orange accent
  if (key.includes('pii')) return 'orange'
  if (key.includes('toxicity') || key.includes('harm')) return 'amber'
  if (key.includes('suspicious')) return 'warning'
  if (key.includes('secrets')) return 'purple'

  // Numeric score-based
  if (typeof val === 'number') {
    if (val >= 0.7) return 'error'
    if (val >= 0.3) return 'warning'
  }
  if (val === true) return 'warning'

  return 'grey'
}

/** Flag color for analytics flag list */
export const FLAG_COLORS: Record<string, string> = {
  denylist_hit: 'error',
  denylist: 'error',
  promptinjection: 'error',
  injection: 'error',
  jailbreak: 'error',
  pii_detected: 'orange',
  pii: 'orange',
  pii_count: 'orange',
  toxicity: 'amber',
  secrets: 'purple',
  suspicious_intent: 'warning',
  score_boost: 'warning',
}

export function analyticsFlagColor(flag: string): string {
  return FLAG_COLORS[flag] ?? 'grey'
}

// ─── Rule action/severity colors ───────────────────────────
export function actionColor(action: string): string {
  const map: Record<string, string> = { block: 'error', flag: 'warning', score_boost: 'info' }
  return map[action] ?? 'default'
}

export function severityColor(severity: string): string {
  const map: Record<string, string> = { critical: 'error', high: 'orange', medium: 'warning', low: 'grey' }
  return map[severity] ?? 'default'
}

// ─── Policy colors ─────────────────────────────────────────
export function policyColor(name: string): string {
  const map: Record<string, string> = {
    fast: 'success',
    balanced: 'primary',
    strict: 'warning',
    paranoid: 'error',
  }
  return map[name] ?? 'grey'
}

// ─── Chart hex colors ──────────────────────────────────────
// These match the Vuetify theme but as hex values for ECharts
export const CHART = {
  // Decision series
  total:    '#5B8DEF',  // muted blue — baseline
  blocked:  '#EF4444',  // red — danger
  modified: '#F59E0B',  // amber — caution
  allowed:  '#22C55E',  // green — safe

  // Grid / axis
  gridLine:  'rgba(255, 255, 255, 0.06)',
  axisLine:  'rgba(255, 255, 255, 0.15)',
  axisLabel: 'rgba(255, 255, 255, 0.45)',

  // Policy-specific (chart bars)
  policyFast:      '#22C55E',
  policyBalanced:  '#F59E0B',
  policyStrict:    '#FB923C',
  policyParanoid:  '#EF4444',
  policyDefault:   '#6B7280',

  // Intents donut — muted varied palette
  intents: [
    '#5B8DEF', // blue
    '#22C55E', // green
    '#EF4444', // red
    '#F59E0B', // amber
    '#A855F7', // purple
    '#06B6D4', // cyan
    '#8B5CF6', // violet
    '#64748B', // slate
    '#EC4899', // pink
    '#3B82F6', // blue-500
  ],
} as const

// ─── Slider / threshold color ──────────────────────────────
export function sliderColor(val: number): string {
  if (val < 0.4) return 'success'
  if (val < 0.7) return 'warning'
  return 'error'
}

// ─── Health status colors ──────────────────────────────────
export function healthStatusColor(status: string): string {
  switch (status) {
    case 'ok': return 'success'
    case 'degraded': return 'warning'
    case 'error': return 'error'
    default: return 'grey'
  }
}

export function resourceBarColor(percent: number): string {
  if (percent >= 90) return 'error'
  if (percent >= 70) return 'warning'
  return 'success'
}

// ─── Intent label ──────────────────────────────────────────
const INTENT_LABELS: Record<string, string> = {
  prompt_injection: 'prompt injection attempt',
  jailbreak: 'jailbreak attempt',
  agent_exfiltration: 'attempted data exfiltration',
  data_leak: 'data leak attempt',
  social_engineering: 'social engineering attempt',
  system_sabotage: 'system sabotage attempt',
  pii_leak: 'PII exposure detected',
  harmful_content: 'harmful content detected',
  off_topic: 'off-topic request blocked',
  suspicious_intent: 'suspicious intent detected',
  order_query: 'order query',
  excessive_agency: 'excessive agency attempt',
}

export function intentLabel(intent: string | null | undefined): string {
  if (!intent) return 'unknown'
  return INTENT_LABELS[intent] ?? intent.replace(/_/g, ' ')
}
