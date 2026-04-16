# Operacao

## Bootstrap
1. Configurar `.env` a partir de `.env.example`.
2. Ajustar `config/app.yaml`.
3. Instalar dependencias e modelos locais.

## Execucao manual
```bash
newsletter-curator run-daily
```

## Reenvio manual para Kindle
```bash
newsletter-curator send-latest-kindle
```

## Dry-run
```bash
newsletter-curator run-daily --dry-run
```

## Replay
```bash
newsletter-curator replay-missed --days-back 7
```

## Dashboard web
```bash
newsletter-curator serve-web
```

Parametros uteis:
- `newsletter-curator serve-web --host 0.0.0.0 --port 8787`
- `newsletter-curator serve-web --days-back 30`

A dashboard permite:
- consultar os ultimos dias
- inspecionar uma data especifica
- detectar se PDF e podcast ja existem
- gerar novamente o conteudo a partir dos e-mails daquele dia
- baixar o PDF e tocar o audio diretamente pela interface

## Scheduler systemd
```bash
sudo systemctl enable --now newsletter-curator.timer
systemctl list-timers | grep newsletter-curator
```

## Matriz de riscos e mitigacao
| Risco | Impacto | Mitigacao |
|---|---|---|
| Qualidade editorial inconsistente no LLM local | Digest com baixa utilidade | Prompt estruturado com schema JSON e revisao por amostragem. |
| Ruido promocional elevado nas newsletters | Poluicao de contexto e resumo | Filtro por palavras negativas e limpeza de quoted text/assinatura. |
| Falhas transitorias em IO (IMAP/SMTP/Ollama) | Quebra de etapa do pipeline | Retry com backoff e checkpoints persistentes por estagio. |
| Execucoes sobrepostas | Corrupcao de estado e duplicidade | Lock de execucao diaria em SQLite com heartbeat e expiracao. |
| Ausencia de modelo Piper/Ollama | Falha em TTS ou consolidacao | Script de bootstrap e healthcheck operacional antes do agendamento. |
