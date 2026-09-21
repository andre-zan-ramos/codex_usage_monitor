# Formato dos logs observado

O monitor lê somente JSONL locais e ignora com segurança campos ou linhas inválidas.

- `session_meta` identifica sessão/thread e início.
- `turn_context` fornece modelo e esforço.
- `event_msg.token_count` contém `info.total_token_usage` acumulado, `last_token_usage`, contexto e snapshots globais de `rate_limits`.
- `response_item.*_call` fornece chamadas de ferramentas deduplicadas.
- Eventos de compactação e mensagens de usuário são contados; prompts completos não são enviados nem exibidos.

`input_tokens` inclui `cached_input_tokens`; input novo é a diferença não negativa. `reasoning_output_tokens` já faz parte de `output_tokens` e não é somado outra vez.

## Thread Health

WCI e Health Score são diagnósticos estruturais da thread: contexto, input, cache, output e tools. Eles não medem nem estimam créditos ou franquia do Codex.

## Allowance Burn

Rate limits são globais da conta. Cada `token_count` pode registrar `primary` (5h) e `secondary` (semanal), com `used_percent`, `window_minutes` e `resets_at`. A timeline é consolidada entre arquivos; uma thread que contém o snapshot não recebe autoria do consumo.

Pontos equivalentes próximos são fundidos. Pequenas regressões entre produtores são descartadas da série canônica. Um novo ciclo é aberto por mudança material de `resets_at` ou queda inequívoca, como 98% para 2%; nenhum burn atravessa ciclos.

Para 5h, as taxas curta e recente usam regressão linear sobre pontos reamostrados a cada 15 segundos nas janelas de 5 e 15 minutos. A estimativa até o limite só aparece com dados suficientes, sem reset cruzado e com snapshot de no máximo 120 segundos. Os parâmetros e thresholds ficam centralizados em `config.py`.
