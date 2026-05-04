from __future__ import annotations

import os

import uvicorn
from dotenv import load_dotenv

from hermes.infra.adapters.fpdf_adapter import FpdfAdapter
from hermes.infra.adapters.imap_adapter import ImapAdapter
from hermes.infra.adapters.kindle_adapter import SmtpKindleAdapter
from hermes.infra.adapters.market_data_adapter import YFinanceMarketDataAdapter
from hermes.infra.adapters.ollama_adapter import OllamaAdapter
from hermes.infra.adapters.state_repository import SqliteStateRepository
from hermes.infra.adapters.tts_adapter import EdgeTtsAdapter
from hermes.infra.web.server import ServerConfig, app
from hermes.use_cases.process_daily import ProcessDailyUseCase
from hermes.use_cases.send_to_kindle import SendToKindleUseCase


def main():
    load_dotenv()

    imap_host = os.getenv("IMAP_HOST", "imap.gmail.com")
    imap_port = os.getenv("IMAP_PORT", "993")
    imap_user = os.getenv("IMAP_USERNAME", "")
    imap_pass = os.getenv("IMAP_PASSWORD", "")
    imap_ssl = os.getenv("IMAP_USE_SSL", "true")
    imap_mailbox = os.getenv("IMAP_MAILBOX", "INBOX")
    imap_search = os.getenv("IMAP_SEARCH_STRATEGY", "SINCE")
    imap_allowed = os.getenv("NEWSLETTER_ALLOWED_SENDERS", "")

    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    ollama_model = os.getenv("OLLAMA_CHAT_MODEL", "qwen2.5:7b")
    ollama_timeout = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "600"))

    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", "465"))
    smtp_user = os.getenv("SMTP_USERNAME", "")
    smtp_pass = os.getenv("SMTP_PASSWORD", "")
    smtp_ssl = os.getenv("SMTP_USE_SSL", "true").lower() == "true"
    kindle_address = os.getenv("KINDLE_ADDRESS", "")

    state_db_path = os.getenv("STATE_SQLITE_PATH", "data/state/hermes.sqlite")
    web_host = os.getenv("WEB_HOST", "127.0.0.1")
    web_port = int(os.getenv("WEB_PORT", "8787"))
    web_days_back = int(os.getenv("WEB_DEFAULT_DAYS_BACK", "28"))

    email_port = ImapAdapter(
        host=imap_host,
        port=imap_port,
        user=imap_user,
        password=imap_pass,
        use_ssl=imap_ssl,
        mailbox=imap_mailbox,
        search_strategy=imap_search,
        allowed_senders=imap_allowed,
    )
    llm_port = OllamaAdapter(base_url=ollama_url, model=ollama_model, timeout=ollama_timeout)
    pdf_port = FpdfAdapter(output_dir="data/pdf")
    audio_port = EdgeTtsAdapter(output_dir="data/audio", voice="pt-BR-AntonioNeural")
    state_repo = SqliteStateRepository(db_path=state_db_path)
    market_data_port = YFinanceMarketDataAdapter()

    process_daily_uc = ProcessDailyUseCase(
        email_port=email_port,
        llm_port=llm_port,
        pdf_port=pdf_port,
        audio_port=audio_port,
        state_repo=state_repo,
        market_data_port=market_data_port,
    )

    kindle_adapter = SmtpKindleAdapter(
        host=smtp_host,
        port=smtp_port,
        username=smtp_user,
        password=smtp_pass,
        use_ssl=smtp_ssl,
        default_kindle_email=kindle_address,
    )
    send_to_kindle_uc = SendToKindleUseCase(kindle_port=kindle_adapter, state_repo=state_repo)

    ServerConfig.state_repo = state_repo
    ServerConfig.process_daily_uc = process_daily_uc
    ServerConfig.send_to_kindle_uc = send_to_kindle_uc
    ServerConfig.days_back = web_days_back
    ServerConfig.default_kindle_email = kindle_address
    ServerConfig.kindle_enabled = kindle_adapter.is_configured()

    print(f"Starting Hermes Server on {web_host}:{web_port}")
    uvicorn.run(app, host=web_host, port=web_port)


if __name__ == "__main__":
    main()

