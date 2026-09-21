import { useEffect, useMemo, useState } from 'react'
import { ArrowRight, Database, Gauge, RefreshCw } from 'lucide-react'
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api'
import { Card, Empty, HealthBadge, Metric } from '../components'
import { compact, dateTimeFromEpoch, duration, number, time } from '../format'
import type { AllowanceWindow, DashboardData, Thread, TimelineData } from '../types'

type SortKey = 'last_activity' | 'health' | 'wci' | 'input' | 'tool_calls' | 'duration'
type Range = '1h' | '5h' | 'today' | '7d'

export function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [timeline, setTimeline] = useState<TimelineData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [sort, setSort] = useState<SortKey>('last_activity')
  const [range, setRange] = useState<Range>('5h')
  useEffect(() => {
    let active = true
    const load = () => Promise.all([api.dashboard(), api.timeline(range)]).then(([dashboard, history]) => {
      if (active) { setData(dashboard); setTimeline(history); setError(null) }
    }).catch(err => active && setError(String(err)))
    load(); const timer = window.setInterval(load, 3000)
    return () => { active = false; window.clearInterval(timer) }
  }, [range])
  const threads = useMemo(() => [...(data?.threads ?? [])].sort((a, b) => sortValue(b, sort) - sortValue(a, sort)), [data, sort])
  if (error && !data) return <Empty><h2>Backend indisponível</h2><p>{error}</p></Empty>
  if (!data) return <Empty><RefreshCw className="spin" /><p>Lendo sessões locais…</p></Empty>
  const active = data.active_thread
  return <>
    {!active ? <Empty><Database /><h2>Nenhuma sessão encontrada</h2><p>O monitor aguardará arquivos em .codex\sessions.</p></Empty> : <ThreadHealth active={active} />}
    <section className="table-section"><div className="section-heading"><div><p className="eyebrow">HOJE E RECENTES</p><h2>Threads monitoradas</h2></div><label>Ordenar por<select value={sort} onChange={event => setSort(event.target.value as SortKey)}><option value="last_activity">Horário</option><option value="health">Health Score</option><option value="wci">WCI</option><option value="input">Input</option><option value="tool_calls">Tool calls</option><option value="duration">Duração</option></select></label></div><div className="table-wrap"><table><thead><tr><th>Thread</th><th>Horário</th><th>Saúde</th><th>WCI</th><th>Input</th><th>Tools</th><th>Duração</th><th /></tr></thead><tbody>{threads.map(thread => <tr key={thread.id}><td><a href={`/threads/${thread.id}`}><strong>{thread.title}</strong></a><small>{thread.id.slice(0, 8)} · {thread.model ?? '—'}</small></td><td>{time(thread.last_activity)}</td><td><span className="score-small">{thread.health.score}</span><HealthBadge health={thread.health} /></td><td>{compact.format(thread.wci)}</td><td>{compact.format(thread.usage.input_tokens)}</td><td>{number.format(thread.tool_calls)}</td><td>{duration(thread.duration_seconds)}</td><td><a aria-label={`Abrir ${thread.title}`} href={`/threads/${thread.id}`}><ArrowRight size={16} /></a></td></tr>)}</tbody></table></div></section>
    <div className="page-heading"><div><p className="eyebrow">ALLOWANCE BURN</p><h1>Cota e velocidade de consumo</h1><p>Snapshots reais globais da conta. Thread Health continua sendo diagnóstico estrutural.</p></div><span className="updated">Atualizado às {time(data.generated_at)}</span></div>
    <div className="rate-grid"><AllowanceCard title="COTA 5H" window={data.allowance.primary} primary /><AllowanceCard title="COTA SEMANAL" window={data.allowance.secondary} /></div>
    {data.allowance.alerts.length > 0 ? <section className="alerts">{data.allowance.alerts.map((alert, index) => <div className={`alert alert-${alert.severity.toLowerCase().replace(' ', '-')}`} key={`${alert.severity}-${index}`}><strong>{alert.severity}</strong><span>{alert.message}</span></div>)}</section> : null}
    <Card className="timeline-card"><div className="section-heading"><div><p className="eyebrow">EVOLUÇÃO GLOBAL</p><h2>Franquia observada</h2></div><label>Período<select value={range} onChange={event => setRange(event.target.value as Range)}><option value="1h">Última 1h</option><option value="5h">Últimas 5h</option><option value="today">Hoje</option><option value="7d">7 dias</option></select></label></div><AllowanceChart timeline={timeline} /></Card>
    <Card className="models-card"><strong>Modelos ativos/recentes</strong><span>{data.allowance.models_recent.length ? data.allowance.models_recent.map(model => `${model.label}${model.relative_cost_factor ? ` · fator relativo ${model.relative_cost_factor.toFixed(1)}x` : ''}`).join('  |  ') : 'Indisponível'}</span><small>O fator relativo é comparativo; não calcula percentual de franquia.</small></Card>
  </>
}

function AllowanceCard({ title, window, primary = false }: { title: string; window: AllowanceWindow | null; primary?: boolean }) {
  const used = window?.used_percent ?? 0
  if (!window) return <Card className="rate-card"><span>{title}</span><strong>Indisponível</strong><small>Aguardando snapshot do Codex.</small></Card>
  return <Card className={`rate-card ${!window.fresh ? 'rate-stale' : ''}`}><div><span>{title}</span><strong>{used.toFixed(0)}% usado</strong></div><div className="progress"><i style={{ width: `${used}%` }} /></div><div className="rate-details"><span>Burn recente: <b>{rate(window.recent_rate_ppm)}</b></span>{primary ? <span className={`burn burn-${window.classification?.toLowerCase().replace(' ', '-')}`}>{window.classification ?? 'AGUARDANDO'}</span> : null}</div>{window.fresh && primary && window.estimated_minutes_to_limit !== null ? <p>Neste ritmo: <b>{humanMinutes(window.estimated_minutes_to_limit)} restantes</b></p> : <p>{window.fresh ? 'Estimativa indisponível' : `Dados de cota desatualizados — há ${humanAge(window.age_seconds)}`}</p>}<small>Reset: {dateTimeFromEpoch(window.resets_at ?? undefined)} · atualizado há {humanAge(window.age_seconds)}</small><small>{window.attribution.message}</small></Card>
}

function AllowanceChart({ timeline }: { timeline: TimelineData | null }) {
  const rows = new Map<string, { label: string; primary?: number; secondary?: number; reset?: boolean }>()
  for (const point of timeline?.windows['300'] ?? []) rows.set(point.observed_at, { label: time(point.observed_at), primary: point.used_percent, reset: point.reset })
  for (const point of timeline?.windows['10080'] ?? []) rows.set(point.observed_at, { ...(rows.get(point.observed_at) ?? { label: time(point.observed_at) }), secondary: point.used_percent })
  const points = [...rows.entries()].sort(([left], [right]) => left.localeCompare(right)).map(([, value]) => value)
  if (!points.length) return <Empty><p>Sem snapshots no período.</p></Empty>
  return <ResponsiveContainer width="100%" height={270}><LineChart data={points}><CartesianGrid strokeDasharray="3 3" stroke="#e2e8e3" /><XAxis dataKey="label" tick={{ fontSize: 10 }} minTickGap={35} /><YAxis domain={[0, 100]} tick={{ fontSize: 11 }} unit="%" /><Tooltip /><ReferenceLine y={80} stroke="#d99b54" strokeDasharray="3 3" /><ReferenceLine y={90} stroke="#bd4d45" strokeDasharray="3 3" /><Line type="monotone" dataKey="primary" name="5h" stroke="#19715f" dot={false} strokeWidth={2} /><Line type="monotone" dataKey="secondary" name="Semanal" stroke="#7256a3" dot={false} strokeWidth={2} /></LineChart></ResponsiveContainer>
}

function ThreadHealth({ active }: { active: Thread }) { return <Card className="active-card"><div className="active-top"><div><p className="eyebrow">THREAD ATUAL / MAIS RECENTE</p><h2>{active.title}</h2><p className="meta">{active.model ?? 'Modelo indisponível'} · {active.reasoning_effort ?? 'effort indisponível'} · {time(active.last_activity)}</p></div><div className="score"><strong>{active.health.score}</strong><span>/100</span><HealthBadge health={active.health} /></div></div><div className="recommendation"><Gauge size={18} /><span><strong>Thread Health — diagnóstico estrutural</strong>{active.health.recommendation}</span></div><div className="metrics-grid"><Metric label="WCI" value={compact.format(active.wci)} detail="índice relativo" /><Metric label="Input total" value={compact.format(active.usage.input_tokens)} /><Metric label="Cached input" value={compact.format(active.usage.cached_input_tokens)} detail={active.cache_ratio === null ? '—' : `${(active.cache_ratio * 100).toFixed(1)}% do input`} /><Metric label="Input novo" value={compact.format(active.usage.uncached_input_tokens)} /><Metric label="Output" value={compact.format(active.usage.output_tokens)} /><Metric label="Reasoning" value={compact.format(active.usage.reasoning_output_tokens)} detail="já incluído no output" /><Metric label="Tool calls" value={number.format(active.tool_calls)} /><Metric label="Pressão de contexto" value={active.context_pressure === null ? 'Indisponível' : `${active.context_pressure.toFixed(1)}%`} /><Metric label="Crescimento recente" value={active.recent_growth_percent === null ? 'Aguardando 6 chamadas' : `${active.recent_growth_percent.toFixed(1)}%`} /></div><a className="detail-link" href={`/threads/${active.id}`}>Ver evolução <ArrowRight size={15} /></a></Card> }
function rate(value: number | null) { return value === null ? 'indisponível' : `${value.toFixed(2)} pp/min` }
function humanAge(seconds: number) { return seconds < 60 ? `${seconds}s` : `${Math.round(seconds / 60)} min` }
function humanMinutes(value: number) { return value < 60 ? `~${value} min` : `~${Math.floor(value / 60)}h${String(value % 60).padStart(2, '0')}` }
function sortValue(thread: Thread, key: SortKey) { if (key === 'last_activity') return thread.last_activity ? new Date(thread.last_activity).getTime() : 0; if (key === 'health') return thread.health.score; if (key === 'wci') return thread.wci; if (key === 'input') return thread.usage.input_tokens; if (key === 'tool_calls') return thread.tool_calls; return thread.duration_seconds ?? 0 }
