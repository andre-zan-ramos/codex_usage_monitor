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

export type AllowanceWindow = {
  window_minutes: number; used_percent: number; remaining_percent: number; resets_at: number | null
  observed_at: string; age_seconds: number; fresh: boolean; cycle: number
  short_rate_ppm: number | null; recent_rate_ppm: number | null; session_rate_ppm: number | null
  trend: string; classification: 'NORMAL' | 'ELEVADO' | 'MUITO ALTO' | 'CRÍTICO' | null
  estimated_minutes_to_limit: number | null
  attribution: { confidence: 'HIGH' | 'MEDIUM' | 'LOW' | 'NONE'; active_threads: number; message: string }
  models: string[]
}
export type TimelinePoint = { observed_at: string; used_percent: number; resets_at: number | null; cycle: number; reset: boolean }
export type DashboardData = {
  generated_at: string
  poll_seconds: number
  allowance: { primary: AllowanceWindow | null; secondary: AllowanceWindow | null; models_recent: Array<{ id: string; label: string; relative_cost_factor: number | null }>; alerts: Array<{ severity: string; message: string }> }
  active_thread: Thread | null
  threads: Thread[]
}
export type TimelineData = { range: string; generated_at: string; windows: Record<string, TimelinePoint[]> }
