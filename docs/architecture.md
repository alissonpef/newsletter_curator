# Arquitetura

## Camadas
- Domain: entidades, policies e servicos puros sem IO.
- Application: use cases e orquestrador diario em Template Method.
- Ports: contratos estaveis para IMAP, SMTP, LLM, embeddings, vetor store, PDF, TTS e estado.
- Adapters: implementacoes concretas das integracoes locais.
- Web: adaptador HTTP local para catalogar execucoes, exibir historico e disparar geracao por data.
- Infra: configuracao, logging estruturado, retry, clock e runtime paths.

## Fluxo diario
1. `fetch_new_emails`
2. `parse_and_clean`
3. `index_embeddings`
4. `curate_daily_digest`
5. `render_pdf`
6. `send_kindle_email`
7. `synthesize_podcast`
8. `persist_run_state`

## Decisoes
- Execucao local-first: Ollama, Chroma e Piper.
- Dependencia `piper-tts` mantida para disponibilizar binario local do Piper no ambiente virtual sem exigir pacote de sistema.
- Agendamento com `systemd timer` + `Persistent=true`.
- Estado auditavel com SQLite como fonte canonica (checkpoint JSON apenas para import/export).
- Catalogo local de artefatos por data, combinando historico persistido e arquivos gerados em disco.
