from __future__ import annotations

import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Optional

from hermes.core.interfaces import KindlePort


class SmtpKindleAdapter(KindlePort):
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        use_ssl: bool = True,
        default_kindle_email: str = "",
    ) -> None:
        self.host = host
        self.port = int(port or 0)
        self.username = username
        self.password = password
        self.use_ssl = use_ssl
        self.default_kindle_email = default_kindle_email.strip()

    def is_configured(self) -> bool:
        return bool(self.host and self.port and self.username and self.password)

    def _normalize_kindle_email(self, kindle_email: Optional[str]) -> str:
        candidate = (kindle_email or self.default_kindle_email).strip()
        if "@" not in candidate:
            raise ValueError("Informe um e-mail válido do Kindle.")
        return candidate

    def _build_message(
        self, date_ref: str, kindle_email: str, pdf_path: Path
    ) -> EmailMessage:
        message = EmailMessage()
        message["From"] = self.username
        message["To"] = kindle_email
        message["Subject"] = f"convert - Hermes {date_ref}"
        message.set_content(
            "Envio automático do digest Hermes.\n"
            "Se este remetente ainda não estiver liberado na Amazon, autorize-o na sua conta Kindle."
        )
        message.add_attachment(
            pdf_path.read_bytes(),
            maintype="application",
            subtype="pdf",
            filename=pdf_path.name,
        )
        return message

    def send_pdf(
        self, date_ref: str, pdf_path: Path, kindle_email: Optional[str] = None
    ) -> str:
        if not self.is_configured():
            raise RuntimeError("O envio para Kindle não está configurado no servidor.")

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF não encontrado: {pdf_path}")

        normalized_email = self._normalize_kindle_email(kindle_email)
        message = self._build_message(date_ref, normalized_email, pdf_path)

        if self.use_ssl:
            with smtplib.SMTP_SSL(self.host, self.port, timeout=30) as client:
                client.login(self.username, self.password)
                client.send_message(message)
        else:
            with smtplib.SMTP(self.host, self.port, timeout=30) as client:
                client.starttls()
                client.login(self.username, self.password)
                client.send_message(message)

        return normalized_email
