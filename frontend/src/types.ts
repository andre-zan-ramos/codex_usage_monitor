export type Usage = {
  input_tokens: number | null
  cached_input_tokens: number | null
  uncached_input_tokens: number | null
  output_tokens: number | null
  reasoning_output_tokens: number | null
  total_tokens: number | null
}

export type Health = {
  score: number | null
  label: 'CARGA BAIXA' | 'CARGA MODERADA' | 'CARGA ALTA' | 'CARGA MUITO ALTA' | 'INDISPONÍVEL'
  heuristic: boolean
  recommendation: string
}

export type Thread = {
  turns?: TurnUsage[]
  unassigned_usage?: Array<{ timestamp: string | null; reason: string; usage: Usage }>
  id: string
  title: string
  started_at: string | null
  last_activity: string | null
  model: string | null
  reasoning_effort: string | null
  usage: Usage
  cache_ratio: number | null
  wci: number | null
  tool_calls: number
  compactions: number
  context_pressure: number | null
  recent_growth_percent: number | null
  duration_seconds: number | null
  health: Health
  evolution?: Array<Usage & { timestamp: string; wci: number | null; cumulative_wci: number | null; cumulative_input_tokens: number | null; tool_calls: number; context_pressure: number | null }>
}

export type TurnUsage = {
  id: string | null; started_at: string | null; ended_at: string | null
  state: string; models: string[]; efforts: string[]; confirmed: boolean; ambiguous: boolean
  metadata_changed: boolean; usage: Usage; intervals: number; incomplete_fields: string[]
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
