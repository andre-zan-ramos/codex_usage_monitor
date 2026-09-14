import { useEffect, useMemo, useState } from 'react'
import { ArrowRight, Database, Gauge, RefreshCw } from 'lucide-react'
import { api } from '../api'
import { Card, Empty, HealthBadge, Metric } from '../components'
import { compact, dateTimeFromEpoch, duration, number, time } from '../format'
import type { DashboardData, Thread } from '../types'

type SortKey = 'last_activity' | 'health' | 'wci' | 'input' | 'tool_calls' | 'duration'

export function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [sort, setSort] = useState<SortKey>('last_activity')
  useEffect(() => {
    let active = true
    const load = () => api.dashboard().then(value => { if (active) { setData(value); setError(null) } }).catch(err => active && setError(String(err)))
    load(); const timer = window.setInterval(load, 3000)
    return () => { active = false; window.clearInterval(timer) }
  }, [])
  const threads = useMemo(() => [...(data?.threads ?? [])].sort((a, b) => sortValue(b, sort) - sortValue(a, sort)), [data, sort])
  if (error && !data) return <Empty><h2>Backend indisponível</h2><p>{error}</p></Empty>
  if (!data) return <Empty><RefreshCw className="spin" /><p>Lendo sessões locais…</p></Empty>
  const active = data.active_thread
  const primary = data.rate_limits?.primary
  const secondary = data.rate_limits?.secondary
  return <>
    <div className="page-heading"><div><p className="eyebrow">VISÃO GERAL</p><h1>Saúde das suas threads</h1><p>Custos relativos, contexto e atividade em tempo quase real.</p></div><span className="updated">Atualizado às {time(data.generated_at)}</span></div>
    <div className="rate-grid">
      <RateCard title="Janela de 5 horas" window={primary} />
      <RateCard title="Uso semanal" window={secondary} />
    </div>
    {!active ? <Empty><Database /><h2>Nenhuma sessão encontrada</h2><p>O monitor aguardará arquivos em .codex\sessions.</p></Empty> : <>
      <Card className="active-card">
        <div className="active-top"><div><p className="eyebrow">THREAD MAIS RECENTE</p><h2>{active.title}</h2><p className="meta">{active.model ?? 'Modelo indisponível'} · {active.reasoning_effort ?? 'effort indisponível'} · {time(active.last_activity)}</p></div><div className="score"><strong>{active.health.score}</strong><span>/100</span><HealthBadge health={active.health} /></div></div>
        <div className="recommendation"><Gauge size={18} /><span><strong>Recomendação</strong>{active.health.recommendation}</span></div>
        <div className="metrics-grid">
          <Metric label="WCI" value={compact.format(active.wci)} detail="índice relativo" />
          <Metric label="Input total" value={compact.format(active.usage.input_tokens)} />
          <Metric label="Cached input" value={compact.format(active.usage.cached_input_tokens)} detail={active.cache_ratio === null ? '—' : `${(active.cache_ratio * 100).toFixed(1)}% do input`} />
          <Metric label="Input novo" value={compact.format(active.usage.uncached_input_tokens)} />
          <Metric label="Output" value={compact.format(active.usage.output_tokens)} />
          <Metric label="Reasoning" value={compact.format(active.usage.reasoning_output_tokens)} detail="já incluído no output" />
          <Metric label="Tool calls" value={number.format(active.tool_calls)} />
          <Metric label="Pressão de contexto" value={active.context_pressure === null ? 'Indisponível' : `${active.context_pressure.toFixed(1)}%`} />
          <Metric label="Crescimento recente" value={active.recent_growth_percent === null ? 'Aguardando 6 chamadas' : `${active.recent_growth_percent.toFixed(1)}%`} />
        </div>
        <a className="detail-link" href={`/threads/${active.id}`}>Ver evolução <ArrowRight size={15} /></a>
      </Card>
    </>}
    <section className="table-section"><div className="section-heading"><div><p className="eyebrow">HOJE E RECENTES</p><h2>Threads monitoradas</h2></div><label>Ordenar por<select value={sort} onChange={event => setSort(event.target.value as SortKey)}><option value="last_activity">Horário</option><option value="health">Health Score</option><option value="wci">WCI</option><option value="input">Input</option><option value="tool_calls">Tool calls</option><option value="duration">Duração</option></select></label></div>
      <div className="table-wrap"><table><thead><tr><th>Thread</th><th>Horário</th><th>Saúde</th><th>WCI</th><th>Input</th><th>Tools</th><th>Duração</th><th /></tr></thead><tbody>{threads.map(thread => <tr key={thread.id}><td><a href={`/threads/${thread.id}`}><strong>{thread.title}</strong></a><small>{thread.id.slice(0, 8)} · {thread.model ?? '—'}</small></td><td>{time(thread.last_activity)}</td><td><span className="score-small">{thread.health.score}</span><HealthBadge health={thread.health} /></td><td>{compact.format(thread.wci)}</td><td>{compact.format(thread.usage.input_tokens)}</td><td>{number.format(thread.tool_calls)}</td><td>{duration(thread.duration_seconds)}</td><td><a aria-label={`Abrir ${thread.title}`} href={`/threads/${thread.id}`}><ArrowRight size={16} /></a></td></tr>)}</tbody></table></div>
    </section>
  </>
}

function RateCard({ title, window }: { title: string; window?: { used_percent: number; resets_at: number } }) {
  const percent = Math.min(100, Math.max(0, window?.used_percent ?? 0))
  return <Card className="rate-card"><div><span>{title}</span><strong>{window ? `${percent.toFixed(0)}%` : 'Indisponível'}</strong></div><div className="progress"><i style={{ width: `${percent}%` }} /></div><small>Reset: {dateTimeFromEpoch(window?.resets_at)}</small><p>Uso global da conta</p></Card>
}

function sortValue(thread: Thread, key: SortKey) {
  if (key === 'last_activity') return thread.last_activity ? new Date(thread.last_activity).getTime() : 0
  if (key === 'health') return thread.health.score
  if (key === 'wci') return thread.wci
  if (key === 'input') return thread.usage.input_tokens
  if (key === 'tool_calls') return thread.tool_calls
  return thread.duration_seconds ?? 0
}
