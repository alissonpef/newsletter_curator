# Hermes (Newsletter Curator)

Pipeline local-first para:
- ler newsletters por IMAP
- consolidar os temas com LLM local (Ollama)
- gerar PDF para Kindle
- gerar podcast curto em audio
- disponibilizar dashboard web local para consulta e reprocessamento

## O que o projeto faz

Entrada:
- emails da sua mailbox (ex.: Gmail IMAP)

Processamento:
- limpeza e normalizacao de texto
- indexacao vetorial (Chroma)
- curadoria de digest diario com LLM local

Saidas:
- PDF em `data/outputs/pdf`
- audio em `data/outputs/audio`
- envio do PDF para o seu Kindle por SMTP

## Como o fluxo funciona

1. Busca emails novos no IMAP
2. Filtra/normaliza conteudo
3. Indexa embeddings
4. Gera digest diario
5. Renderiza PDF
6. Envia para Kindle (quando nao e dry-run)
7. Gera podcast em WAV

## Requisitos

- Linux/macOS (Windows via WSL recomendado)
- Python 3.11+
- Conta de email com IMAP/SMTP
- Ollama instalado e rodando
- Modelo Piper (`.onnx`) para TTS

## Instalacao do zero

### 1) Clonar projeto

```bash
git clone https://github.com/alissonpef/Newsletter-Curator.git
cd Newsletter-Curator
```

### 2) Criar ambiente e instalar dependencias

```bash
python -m venv .venv
./.venv/bin/pip install -e .[dev]
```

### 3) Preparar variaveis de ambiente

```bash
cp .env.example .env
```

Edite `.env` com seus dados reais.

### 4) Instalar e iniciar Ollama

Se nao tiver Ollama no sistema, instale pelo site oficial.
Depois inicie:

```bash
ollama serve
```

Se preferir binario local no projeto, o script de bootstrap tambem aceita `.tools/ollama/bin/ollama`.

### 5) Baixar modelos (LLM + embedding + Piper)

LLM/embedding:

```bash
ollama pull qwen2.5:1.5b
ollama pull nomic-embed-text
```

Modelo de voz Piper (exemplo):

```bash
mkdir -p models
curl -L -o models/pt_BR-voice.onnx \
	https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx
curl -L -o models/pt_BR-voice.onnx.json \
	https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx.json
```

Opcional: bootstrap automatizado de modelos Ollama + validacao do Piper:

```bash
./scripts/bootstrap_models.sh
```

### 6) Validar ambiente

```bash
./.venv/bin/newsletter-curator healthcheck
```

## Configuracao detalhada

### IMAP/SMTP (exemplo com Gmail)

No Gmail:
1. Ative 2FA
2. Gere uma App Password
3. Ative IMAP nas configuracoes da conta

No `.env`:
- `IMAP_HOST=imap.gmail.com`
- `IMAP_PORT=993`
- `IMAP_USERNAME=seu_email`
- `IMAP_PASSWORD=app_password`
- `SMTP_HOST=smtp.gmail.com`
- `SMTP_PORT=465`
- `SMTP_USERNAME=seu_email`
- `SMTP_PASSWORD=app_password`

### Kindle (obrigatorio para entrega)

1. Pegue o endereco do seu Kindle (algo como `seunome_xxxxx@kindle.com`)
2. Configure `KINDLE_ADDRESS` no `.env`
3. Na Amazon, adicione o email remetente (`SMTP_USERNAME`) na lista de remetentes aprovados:
	 - Manage Your Content and Devices
	 - Preferences
	 - Personal Document Settings
	 - Approved Personal Document E-mail List

Sem este passo, a Amazon pode rejeitar o envio.

### Remetentes permitidos de newsletters

Use `NEWSLETTER_ALLOWED_SENDERS` no `.env`, separado por virgula.

Exemplo:

```dotenv
NEWSLETTER_ALLOWED_SENDERS=newsletter@fonte1.com,contato@fonte2.com
```

### Ajustes de pipeline

O arquivo `config/app.yaml` define:
- estrategia de busca IMAP (`SINCE`, janela em horas)
- topicos de curadoria
- diretorios de saida
- host/porta do dashboard

## Execucao

### Dry-run (sem envio para Kindle)

```bash
./.venv/bin/newsletter-curator run-daily --dry-run
```

### Execucao completa

```bash
./.venv/bin/newsletter-curator run-daily
```

### Reenviar ultimo PDF para Kindle

```bash
./.venv/bin/newsletter-curator send-latest-kindle
```

### Dashboard web local

```bash
./.venv/bin/newsletter-curator serve-web
```

Acesse: `http://127.0.0.1:8787`

### Replay de dias perdidos

```bash
./.venv/bin/newsletter-curator replay-missed --days-back 7
```

### Exportar checkpoints para JSON (sob demanda)

```bash
./.venv/bin/newsletter-curator export-checkpoints
```

## Testes

Executar todos os testes:

```bash
./.venv/bin/python -m pytest -q
```

## Estrutura de saida

- `data/outputs/pdf/*.pdf`
- `data/outputs/audio/*.wav`
- `data/state/processed_ids.sqlite`

## Troubleshooting rapido

- `ollama endpoint unavailable`:
	- verifique `ollama serve`
- falha no Kindle:
	- confirme `KINDLE_ADDRESS`
	- confirme email aprovado na Amazon
- falha IMAP:
	- valide App Password
	- valide IMAP habilitado na conta
- falha TTS:
	- confira `PIPER_MODEL_PATH`
	- confira existencia de `models/pt_BR-voice.onnx`

## Seguranca

Nao versione:
- `.env`
- `.venv/`
- `.ollama/`
- `.tools/`
- `data/`
- modelos locais grandes em `models/`
