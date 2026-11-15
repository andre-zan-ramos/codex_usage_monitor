# Formato dos logs observado

O monitor lê somente JSONL locais e ignora com segurança campos ou linhas inválidas.

- `session_meta` identifica sessão/thread e início.
- `turn_context` fornece modelo e esforço.
- `event_msg.token_count` contém `info.total_token_usage` acumulado, `last_token_usage`, contexto e snapshots globais de `rate_limits`.
- `response_item.*_call` fornece chamadas de ferramentas deduplicadas.
- Eventos de compactação e mensagens de usuário são contados; prompts completos não são enviados nem exibidos.

`input_tokens` inclui `cached_input_tokens`; input novo é a diferença não negativa. `reasoning_output_tokens` já faz parte de `output_tokens` e não é somado outra vez.

Campos de tokens ausentes, nulos ou inválidos são expostos como `null`, e não como zero. Logs antigos continuam aceitos. A API mantém as chaves, mas consumidores precisam aceitar valores nulos e os novos rótulos de carga. Input novo, cache ratio e WCI ficam indisponíveis quando faltam seus operandos; o Health Score fica indisponível sem entrada ou saída. Zero explicitamente registrado continua sendo zero.

A evolução só adiciona pontos quando os contadores conhecidos mudam; timestamps, ferramentas ou atualizações de cota isolados não criam chamadas. Sem acumulados, a comparação usa `last_token_usage`: chamadas distintas de tamanho idêntico não podem ser distinguidas de snapshots repetidos. A evolução representa alterações observadas, não uma contagem garantida de chamadas. As observações globais de cota continuam sendo coletadas mesmo sem alteração de tokens.

## Thread Health

WCI e Health Score são diagnósticos heurísticos estruturais da thread: contexto, input, cache, output e tools. As fórmulas e os limites foram preservados para dados completos. Os rótulos são CARGA BAIXA, CARGA MODERADA, CARGA ALTA e CARGA MUITO ALTA. Eles não medem nem estimam dinheiro, créditos, franquia ou eficiência da tarefa e não recomendam automaticamente reiniciar threads. Os fatores relativos por modelo são configurações sem calibração verificada, não preços.

## Allowance Burn

Rate limits são globais da conta. Cada `token_count` pode registrar `primary` (5h) e `secondary` (semanal), com `used_percent`, `window_minutes` e `resets_at`. A timeline é consolidada entre arquivos; uma thread que contém o snapshot não recebe autoria do consumo.

Percentual de cota não equivale diretamente a tokens, créditos ou dinheiro. Uma única thread local observada recebe no máximo confiança MEDIUM de associação temporal; isso não comprova exclusividade global ou causalidade. Uma thread apenas próxima ao intervalo recebe LOW.

Pontos equivalentes próximos são fundidos. Pequenas regressões entre produtores são descartadas da série canônica. Um novo ciclo é aberto por mudança material de `resets_at` ou queda inequívoca, como 98% para 2%; nenhum burn atravessa ciclos.

Para 5h, as taxas curta e recente usam regressão linear sobre pontos reamostrados a cada 15 segundos nas janelas de 5 e 15 minutos. A estimativa até o limite só aparece com dados suficientes, sem reset cruzado e com snapshot de no máximo 120 segundos. Os parâmetros e thresholds ficam centralizados em `config.py`.
