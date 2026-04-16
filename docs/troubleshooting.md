# Troubleshooting

## Falha no IMAP
- Verificar `IMAP_HOST`, porta, SSL e credenciais.
- Validar acesso da mailbox configurada.

## Falha no Ollama
- Confirmar servico ativo (`ollama serve`).
- Executar `scripts/bootstrap_models.sh`.

## Falha no envio Kindle
- Confirmar endereco `@kindle.com` em `KINDLE_ADDRESS`.
- Verificar remetente aprovado na conta Amazon.
- Reenviar manualmente o ultimo PDF com `newsletter-curator send-latest-kindle`.

## Radar de mercado vazio no PDF
- Verificar acesso HTTPS de saida para `query1.finance.yahoo.com`.
- Rodar novamente a pipeline; se a coleta falhar, o digest continua sem bloquear o restante do fluxo.

## Falha no Piper
- Validar `PIPER_MODEL_PATH`.
- Verificar se executavel `piper` esta no PATH.

## Execucoes sobrepostas
- Verificar tabela `run_locks` no SQLite.
- Se houver lock preso apos interrupcao brusca, aguardar o TTL expirar ou remover a linha manualmente no banco.
