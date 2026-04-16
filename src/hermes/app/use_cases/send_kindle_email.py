from pathlib import Path

from ...ports.smtp_port import SmtpPort


class SendKindleEmailUseCase:
    _MAX_KINDLE_ATTACHMENT_BYTES = 200 * 1024 * 1024

    def __init__(self, smtp_port: SmtpPort, logger) -> None:
        self._smtp_port = smtp_port
        self._logger = logger

    def _normalize_kindle_address(self, kindle_address: str) -> str:
        candidate = kindle_address.strip()
        if "@" not in candidate:
            raise ValueError("invalid KINDLE_ADDRESS: missing '@'")

        local_part, domain = candidate.rsplit("@", 1)
        local_part = local_part.strip()
        domain = domain.strip().lower()

        if not local_part or not domain:
            raise ValueError("invalid KINDLE_ADDRESS: local-part or domain is empty")

        if domain not in {"kindle.com", "free.kindle.com"}:
            self._logger.warning(
                "kindle address domain is unusual",
                extra={"kindle_domain": domain},
            )

        return f"{local_part}@{domain}"

    def _normalize_subject(self, run_id: str, subject: str) -> str:
        base = subject.strip() if subject.strip() else f"Newsletter Curator Digest {run_id}"
        if "convert" in base.lower():
            return base
        return f"convert - {base}"

    def execute(self, run_id: str, pdf_path: Path, kindle_address: str, subject: str = "") -> None:
        if not pdf_path.exists():
            raise FileNotFoundError(f"pdf artifact not found: {pdf_path}")

        normalized_to = self._normalize_kindle_address(kindle_address)
        normalized_subject = self._normalize_subject(run_id=run_id, subject=subject)

        payload = pdf_path.read_bytes()
        if len(payload) > self._MAX_KINDLE_ATTACHMENT_BYTES:
            raise ValueError(
                "pdf attachment is too large for Kindle send-to-email "
                f"({len(payload)} bytes > {self._MAX_KINDLE_ATTACHMENT_BYTES} bytes)"
            )

        self._smtp_port.send_with_attachment(
            to_address=normalized_to,
            subject=normalized_subject,
            body_text=f"Daily digest run {run_id}",
            attachment_name=pdf_path.name,
            attachment_bytes=payload,
            mime_type="application/pdf",
        )
        self._logger.info("sent kindle email", extra={"run_id": run_id, "to": normalized_to})
