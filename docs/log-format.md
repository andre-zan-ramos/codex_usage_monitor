# Formato dos logs observado

Inspeção local realizada em 14/09/2026 sobre amostras recentes, sem copiar conteúdo pessoal.

- `session_meta`: identifica sessão/thread, início, diretório e, em algumas versões, `context_window`.
- `turn_context`: fornece `model`, `effort` e configuração do turno.
- `event_msg.token_count`: contém `info.total_token_usage` acumulado, `info.last_token_usage` da chamada, `model_context_window` e snapshots globais de rate limit.
- `token_usage_record`: representação adicional presente nas versões atuais. O parser usa `token_count` como fonte canônica para evitar dupla contagem.
- `response_item.*_call`: chamadas de ferramentas, deduplicadas por `call_id`/`id`.
- `event_msg.user_message`: contado; apenas um título local curto é derivado da primeira mensagem. Textos integrais não são enviados nem exibidos no dashboard.
- `compacted` e `event_msg.context_compacted`: eventos de compactação.

## Semântica adotada

`input_tokens` inclui `cached_input_tokens`; portanto, input novo é a diferença não negativa. `total_tokens` observado equivale a input + output. `reasoning_output_tokens` faz parte do output e é apenas exibido separadamente, nunca somado outra vez.

Pressão de contexto usa o input da última chamada dividido por `model_context_window`, ambos informados no mesmo snapshot. Se um deles faltar, a métrica fica indisponível e o Health Score é normalizado pelo máximo disponível.

Rate limits são globais da conta. O monitor mostra apenas o snapshot mais recente, separa janelas por `window_minutes` e detecta queda de uso acompanhada de mudança em `resets_at`. Nenhum percentual é atribuído a uma thread.

O formato é interno e pode mudar; campos desconhecidos ou ausentes são ignorados com segurança.
