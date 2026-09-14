export type Usage = {
  input_tokens: number
  cached_input_tokens: number
  uncached_input_tokens: number
  output_tokens: number
  reasoning_output_tokens: number
  total_tokens: number
}

export type Health = {
  score: number
  label: 'LEVE' | 'CRESCENDO' | 'CARA' | 'MUITO CARA'
  recommendation: string
}

export type Thread = {
  id: string
  title: string
  started_at: string | null
  last_activity: string | null
  model: string | null
  reasoning_effort: string | null
  usage: Usage
  cache_ratio: number | null
  wci: number
  tool_calls: number
  compactions: number
  context_pressure: number | null
  recent_growth_percent: number | null
  duration_seconds: number | null
  health: Health
  evolution?: Array<Usage & { timestamp: string; wci: number; cumulative_wci: number; cumulative_input_tokens: number; tool_calls: number; context_pressure: number | null }>
}

export type RateWindow = { used_percent: number; window_minutes: number; resets_at: number }
export type DashboardData = {
  generated_at: string
  poll_seconds: number
  rate_limits: { primary?: RateWindow; secondary?: RateWindow; observed_at?: string } | null
  active_thread: Thread | null
  threads: Thread[]
}
