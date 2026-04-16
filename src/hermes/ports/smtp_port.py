from typing import Protocol


class SmtpPort(Protocol):
    def send_with_attachment(
        self,
        to_address: str,
        subject: str,
        body_text: str,
        attachment_name: str,
        attachment_bytes: bytes,
        mime_type: str,
    ) -> None: ...
