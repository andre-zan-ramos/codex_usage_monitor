import type { Thread, Usage } from './types'
import { Card } from './components'
import { number, time } from './format'

function Consumption({ usage }: { usage: Usage }) {
  const fields = [['input_tokens', 'Entrada'], ['cached_input_tokens', 'Cache'], ['uncached_input_tokens', 'Sem cache'], ['output_tokens', 'Saída'], ['reasoning_output_tokens', 'Raciocínio']] as const
  return <p>{fields.map(([key, label]) => <span key={key}>{label}: {usage[key] == null ? 'Não informado' : number.format(usage[key])} · </span>)}</p>
}

export function Turns({ thread }: { thread: Pick<Thread, 'turns' | 'unassigned_usage'> }) {
  return <Card><h2>Consumo observado por turno</h2>
    <p>Diferenças derivadas de acumulados adjacentes com associação segura. Cobertura parcial: referências iniciais e limites inseguros ficam não atribuídos. Raciocínio integra a saída e não é somado novamente. Encerramento observado não indica sucesso da tarefa.</p>
    {!thread.turns?.length && <p>Sem turnos identificados neste log.</p>}
    {thread.turns?.map((turn, index) => <article key={index}>
      <h3>Turno {index + 1} · {turn.id ?? 'Identificador ausente'}</h3>
      <p>{time(turn.started_at)} → {time(turn.ended_at)} · {turn.state === 'encerramento_observado' ? 'Encerramento observado' : turn.state === 'limite_ambiguo' ? 'Limite ambíguo' : 'Início observado, sem encerramento'} · {turn.intervals} intervalos atribuídos</p>
      <p>Modelo: {turn.models.join(' → ') || 'Não informado'} · Esforço: {turn.efforts.join(' → ') || 'Não informado'}{turn.metadata_changed && ' · Mudança de metadados observada'}{(turn.ambiguous || !turn.confirmed) && ' · Associação ambígua ou não confirmada'}</p>
      <Consumption usage={turn.usage} />
      {!!turn.incomplete_fields.length && <p>Campos com intervalos incompletos permanecem indisponíveis.</p>}
    </article>)}
    <h3>Consumo não atribuído / referências</h3>
    {!thread.unassigned_usage?.length && <p>Nenhuma observação não atribuída.</p>}
    {thread.unassigned_usage?.map((item, index) => <article key={index}><p>{time(item.timestamp)} · {({ primeira_referencia: 'Referência inicial, diferença desconhecida', regressao: 'Regressão de acumulados', sem_acumulado: 'Sem acumulado válido', limite_ou_associacao_insegura: 'Limite entre turnos ou associação insegura' } as Record<string, string>)[item.reason] ?? item.reason}</p><Consumption usage={item.usage} /></article>)}
  </Card>
}
