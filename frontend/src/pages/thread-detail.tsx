import { useEffect, useState } from 'react'
import { ArrowLeft } from 'lucide-react'
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api'
import { Card, Empty, HealthBadge, Metric } from '../components'
import { compact, number, time } from '../format'
import type { Thread } from '../types'

export function ThreadDetail({ id }: { id: string }) {
  const [thread, setThread] = useState<Thread | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    let active = true
    const load = () => api.thread(id).then(value => active && setThread(value)).catch(err => active && setError(String(err)))
    load(); const timer = window.setInterval(load, 3000)
    return () => { active = false; window.clearInterval(timer) }
  }, [id])
  if (error && !thread) return <Empty><h2>Thread indisponível</h2><p>{error}</p><a href="/">Voltar</a></Empty>
  if (!thread) return <Empty><p>Carregando evolução…</p></Empty>
  const chart = (thread.evolution ?? []).map((point, index) => ({ ...point, call: index + 1 }))
  return <>
    <a className="back" href="/"><ArrowLeft size={15} /> Dashboard</a>
    <div className="detail-heading"><div><p className="eyebrow">EVOLUÇÃO DA THREAD</p><h1>{thread.title}</h1><p>{thread.id} · última atividade {time(thread.last_activity)}</p></div><div className="score"><strong>{thread.health.score}</strong><span>/100</span><HealthBadge health={thread.health} /></div></div>
    <Card><div className="metrics-grid detail-metrics"><Metric label="WCI atual" value={compact.format(thread.wci)} detail="índice relativo" /><Metric label="Input total" value={compact.format(thread.usage.input_tokens)} /><Metric label="Cached" value={compact.format(thread.usage.cached_input_tokens)} /><Metric label="Input novo" value={compact.format(thread.usage.uncached_input_tokens)} /><Metric label="Output" value={compact.format(thread.usage.output_tokens)} /><Metric label="Reasoning" value={compact.format(thread.usage.reasoning_output_tokens)} /><Metric label="Tool calls" value={number.format(thread.tool_calls)} /><Metric label="Compactações" value={thread.compactions} /></div></Card>
    <div className="charts-grid"><Chart title="Crescimento do WCI acumulado" data={chart} lines={[['cumulative_wci', '#19715f', 'WCI']]} /><Chart title="Input acumulado" data={chart} lines={[['cumulative_input_tokens', '#326e9c', 'Input']]} /><Chart title="Tool calls acumuladas" data={chart} lines={[['tool_calls', '#7256a3', 'Tools']]} />{thread.context_pressure !== null && <Chart title="Pressão de contexto" data={chart} lines={[['context_pressure', '#bd6b35', 'Contexto %']]} />}</div>
    <p className="method-note">Cada ponto usa `last_token_usage`, isto é, a chamada registrada no snapshot. Reasoning é exibido separadamente, mas não é somado ao output.</p>
  </>
}

function Chart({ title, data, lines }: { title: string; data: Array<Record<string, unknown>>; lines: Array<[string, string, string]> }) {
  return <Card className="chart-card"><h2>{title}</h2><ResponsiveContainer width="100%" height={260}><LineChart data={data}><CartesianGrid strokeDasharray="3 3" stroke="#e2e8e3" /><XAxis dataKey="call" tick={{ fontSize: 11 }} /><YAxis tick={{ fontSize: 11 }} width={55} /><Tooltip /><Legend />{lines.map(([key, color, name]) => <Line key={key} type="monotone" dataKey={key} name={name} stroke={color} dot={false} strokeWidth={2} />)}</LineChart></ResponsiveContainer></Card>
}
