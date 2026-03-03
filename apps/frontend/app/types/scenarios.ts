export interface ScenarioItem {
  label: string
  prompt: string
  tags: string[]
  expectedDecision: 'BLOCK' | 'MODIFY' | 'ALLOW'
}

export interface ScenarioGroup {
  label: string
  color: string
  icon: string
  items: ScenarioItem[]
}
