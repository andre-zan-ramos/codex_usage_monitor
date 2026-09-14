import type { ReactNode } from 'react'
import { Activity } from 'lucide-react'
import type { Health } from './types'

export function Shell({ children }: { children: ReactNode }) {
  return <div className="app-shell">
    <header className="app-header"><a className="brand" href="/"><span className="brand-mark"><Activity size={20} /></span><span><strong>Codex Usage Monitor</strong><small>Leitura local · sem telemetria</small></span></a><span className="live"><i /> Atualização automática</span></header>
    <main>{children}</main>
    <footer>Dados reconstruídos de JSONL locais <span>WCI é um índice relativo, não créditos OpenAI</span></footer>
  </div>
}

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={`card ${className}`}>{children}</section>
}

export function Metric({ label, value, detail }: { label: string; value: ReactNode; detail?: ReactNode }) {
  return <div className="metric"><span>{label}</span><strong>{value}</strong>{detail && <small>{detail}</small>}</div>
}

export function HealthBadge({ health }: { health: Health }) {
  return <span className={`health health-${health.label.toLowerCase().replace(' ', '-')}`}>{health.label}</span>
}

export function Empty({ children }: { children: ReactNode }) {
  return <Card className="empty">{children}</Card>
}
