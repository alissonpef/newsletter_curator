from __future__ import annotations

import smtplib
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

from ...core.errors import SmtpDeliveryError
from ...infra.retries import io_retry


class SmtpClient:
    def __init__(self, host: str, port: int, username: str, password: str, use_ssl: bool = True) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._use_ssl = use_ssl

    def send_with_attachment(
        self,
        to_address: str,
        subject: str,
        body_text: str,
        attachment_name: str,
        attachment_bytes: bytes,
        mime_type: str,
    ) -> None:
        try:
            maintype, subtype = mime_type.split("/", 1)
        except ValueError as exc:
            raise ValueError("invalid mime_type format") from exc

        msg = EmailMessage()
        msg["From"] = self._username
        msg["To"] = to_address
        msg["Subject"] = subject
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain="newsletter-curator.local")
        msg.set_content(body_text)
        msg.add_attachment(
            attachment_bytes,
            maintype=maintype,
            subtype=subtype,
            filename=attachment_name,
        )

        try:
            if self._use_ssl:
                self._send_ssl(msg)
                return

            self._send_starttls(msg)
        except Exception as exc:
            raise SmtpDeliveryError(f"smtp send_with_attachment failed: {exc}") from exc

    @io_retry()
    def _send_ssl(self, message: EmailMessage) -> None:
        with smtplib.SMTP_SSL(self._host, self._port, timeout=30) as client:
            client.login(self._username, self._password)
            refused = client.send_message(message)
            if refused:
                raise ConnectionError(f"smtp refused recipients: {refused}")

    @io_retry()
    def _send_starttls(self, message: EmailMessage) -> None:
        with smtplib.SMTP(self._host, self._port, timeout=30) as client:
            client.starttls()
            client.login(self._username, self._password)
            refused = client.send_message(message)
            if refused:
                raise ConnectionError(f"smtp refused recipients: {refused}")
