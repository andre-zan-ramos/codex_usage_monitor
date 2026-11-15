import { Turns } from './turns'
import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { HealthBadge, Metric, Shell } from './components'
import { compactValue } from './format'

describe('integridade dos indicadores na interface', () => {
  it('distingue um valor não informado de zero efetivamente registrado', () => {
    const missing = renderToStaticMarkup(<Metric label="Input" value={compactValue(null)} />)
    const zero = renderToStaticMarkup(<Metric label="Input" value={compactValue(0)} />)
    expect(missing).toContain('Não informado')
    expect(zero).toContain('<strong>0</strong>')
  })

  it('exibe carga estrutural e indisponibilidade sem rótulos financeiros', () => {
    const high = renderToStaticMarkup(<HealthBadge health={{ score: 80, label: 'CARGA MUITO ALTA', heuristic: true, recommendation: '' }} />)
    const missing = renderToStaticMarkup(<HealthBadge health={{ score: null, label: 'INDISPONÍVEL', heuristic: true, recommendation: '' }} />)
    expect(high).toContain('CARGA MUITO ALTA')
    expect(high).toContain('health-carga-muito-alta')
    expect(missing).toContain('INDISPONÍVEL')
  })

  it('explicita a natureza heurística e a ausência de conversão financeira', () => {
    const html = renderToStaticMarkup(<Shell><p>Monitor</p></Shell>)
    expect(html).toContain('WCI e Health Score são heurísticos')
    expect(html).toContain('cota não equivale a tokens ou dinheiro')
  })
})


describe('consumo por turno', () => {
  it('mostra ausência, zero, metadados e encerramento sem presumir sucesso', () => {
    const html = renderToStaticMarkup(<Turns thread={{ turns: [{ id: 'a', started_at: null, ended_at: null, state: 'encerramento_observado', models: ['m1', 'm2'], efforts: ['high'], confirmed: true, ambiguous: false, metadata_changed: true, intervals: 1, incomplete_fields: [], usage: { input_tokens: 0, cached_input_tokens: null, uncached_input_tokens: null, output_tokens: 5, reasoning_output_tokens: 2, total_tokens: null } }], unassigned_usage: [{ timestamp: null, reason: 'primeira_referencia', usage: { input_tokens: null, cached_input_tokens: null, uncached_input_tokens: null, output_tokens: null, reasoning_output_tokens: null, total_tokens: null } }] }} />)
    expect(html).toContain('Entrada: 0')
    expect(html).toContain('Cache: Não informado')
    expect(html).toContain('Encerramento observado')
    expect(html).toContain('não indica sucesso')
    expect(html).toContain('Mudança de metadados observada')
    expect(html).toContain('Referência inicial, diferença desconhecida')
  })
  it('aceita detalhes antigos sem a coleção de turnos', () => {
    expect(renderToStaticMarkup(<Turns thread={{}} />)).toContain('Sem turnos identificados')
  })
})
