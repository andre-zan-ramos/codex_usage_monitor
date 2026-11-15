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
