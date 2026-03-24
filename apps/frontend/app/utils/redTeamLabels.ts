/**
 * Human-readable labels for Red Team categories, severities, packs, and scenario IDs.
 * Single source of truth — import from here in all Red Team pages.
 */

// ---------------------------------------------------------------------------
// Category labels
// ---------------------------------------------------------------------------

const CATEGORY_LABELS: Record<string, string> = {
  prompt_injection_jailbreak: 'Prompt Injection / Jailbreak',
  data_leakage_pii: 'Data Leakage / PII',
  tool_abuse: 'Tool Abuse',
  access_control: 'Access Control',
}

export function humanCategory(slug: string): string {
  return CATEGORY_LABELS[slug] ?? slug.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

// ---------------------------------------------------------------------------
// Severity labels + colors
// ---------------------------------------------------------------------------

const SEVERITY_META: Record<string, { label: string; color: string; icon: string }> = {
  critical: { label: 'Critical', color: 'error', icon: 'mdi-alert-circle' },
  high: { label: 'High', color: 'orange-darken-2', icon: 'mdi-alert' },
  medium: { label: 'Medium', color: 'warning', icon: 'mdi-alert-outline' },
  low: { label: 'Low', color: 'info', icon: 'mdi-information-outline' },
}

export function severityMeta(sev: string) {
  return SEVERITY_META[sev] ?? { label: sev, color: 'grey', icon: 'mdi-help-circle' }
}

// ---------------------------------------------------------------------------
// Pack labels
// ---------------------------------------------------------------------------

const PACK_LABELS: Record<string, string> = {
  core_security: 'Core Security',
  agent_threats: 'Agent Threats',
  full_suite: 'Full Suite',
  jailbreakbench: 'JailbreakBench',
}

export function humanPack(slug: string): string {
  return PACK_LABELS[slug] ?? slug.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

// ---------------------------------------------------------------------------
// Score status label
// ---------------------------------------------------------------------------

export interface ScoreLabel {
  label: string
  color: string
  vuetifyColor: string
}

export function scoreLabel(score: number): ScoreLabel {
  if (score >= 90) return { label: 'Strong', color: '#2e7d32', vuetifyColor: 'green-darken-2' }
  if (score >= 80) return { label: 'Good', color: '#4caf50', vuetifyColor: 'success' }
  if (score >= 60) return { label: 'Needs Hardening', color: '#fb8c00', vuetifyColor: 'warning' }
  if (score >= 40) return { label: 'Weak', color: '#ff9800', vuetifyColor: 'orange' }
  return { label: 'Critical', color: '#d32f2f', vuetifyColor: 'error' }
}
