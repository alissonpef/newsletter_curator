from __future__ import annotations

from datetime import date, datetime, timezone
from email.message import EmailMessage
from email.utils import format_datetime

from hermes.app.use_cases.parse_and_clean import ParseAndCleanUseCase


class DummyNormalizer:
    def normalize_email_text(self, text: str) -> str:
        return text.strip()


class DummyLinkExtractor:
    def extract_links(self, text: str) -> list[str]:
        return []


class DummyStateStore:
    def __init__(self) -> None:
        self.processed: list[tuple[str | None, str, str]] = []

    def is_processed(self, message_id: str | None, content_hash: str) -> bool:
        return False

    def mark_processed(self, message_id: str | None, content_hash: str, run_id: str) -> None:
        self.processed.append((message_id, content_hash, run_id))

    def mark_processed_batch(self, records: list[tuple[str | None, str, str]]) -> None:
        self.processed.extend(records)


class DummyLogger:
    def info(self, *args, **kwargs) -> None:
        return None

    def exception(self, *args, **kwargs) -> None:
        return None


def _build_raw_email(
    message_id: str,
    sender: str,
    subject: str,
    received_at: datetime,
    body: str,
) -> bytes:
    message = EmailMessage()
    message["Message-ID"] = message_id
    message["From"] = sender
    message["Subject"] = subject
    message["Date"] = format_datetime(received_at)
    message.set_content(body)
    return message.as_bytes()


def test_execute_filters_by_reference_date_and_allowed_senders() -> None:
    use_case = ParseAndCleanUseCase(
        normalizer=DummyNormalizer(),
        link_extractor=DummyLinkExtractor(),
        state_store=DummyStateStore(),
        logger=DummyLogger(),
    )

    allowed_sender = "newsletter@neofeed.com.br"
    raw_emails = [
        (
            "1",
            _build_raw_email(
                message_id="<allowed-today@example.com>",
                sender="NeoFeed <newsletter@neofeed.com.br>",
                subject="Resumo do mercado",
                received_at=datetime(2026, 4, 15, 8, 0, tzinfo=timezone.utc),
                body="Conteudo da newsletter",
            ),
        ),
        (
            "2",
            _build_raw_email(
                message_id="<allowed-yesterday@example.com>",
                sender="NeoFeed <newsletter@neofeed.com.br>",
                subject="Edicao anterior",
                received_at=datetime(2026, 4, 14, 22, 0, tzinfo=timezone.utc),
                body="Conteudo antigo",
            ),
        ),
        (
            "3",
            _build_raw_email(
                message_id="<other-today@example.com>",
                sender="Outra fonte <outra@fonte.com>",
                subject="Nao deve entrar",
                received_at=datetime(2026, 4, 15, 9, 0, tzinfo=timezone.utc),
                body="Conteudo diverso",
            ),
        ),
    ]

    parsed = use_case.execute(
        run_id="run-1",
        date_ref=date(2026, 4, 15),
        raw_emails=raw_emails,
        negative_keywords=[],
        allowed_senders=[allowed_sender],
    )

    assert len(parsed) == 1
    assert parsed[0].message_id == "<allowed-today@example.com>"
    assert "newsletter@neofeed.com.br" in parsed[0].sender.lower()
