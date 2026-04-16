from pathlib import Path

from hermes.app.use_cases.send_kindle_email import SendKindleEmailUseCase


class DummyLogger:
    def info(self, *args, **kwargs):
        return None


class CaptureSmtp:
    def __init__(self) -> None:
        self.kwargs = {}

    def send_with_attachment(self, **kwargs):
        self.kwargs = kwargs


def test_send_kindle_email_normalizes_destination_and_subject(tmp_path) -> None:
    pdf_path = tmp_path / "digest.pdf"
    pdf_path.write_bytes(b"pdf-content")

    smtp = CaptureSmtp()
    use_case = SendKindleEmailUseCase(smtp_port=smtp, logger=DummyLogger())

    use_case.execute(
        run_id="2026-04-15-abc123",
        pdf_path=pdf_path,
        kindle_address="MyDevice@Kindle.Com  ",
        subject="",
    )

    assert smtp.kwargs["to_address"] == "MyDevice@kindle.com"
    assert smtp.kwargs["subject"].startswith("convert - Newsletter Curator Digest")
    assert smtp.kwargs["attachment_name"] == "digest.pdf"


def test_send_kindle_email_rejects_invalid_address(tmp_path) -> None:
    pdf_path = tmp_path / "digest.pdf"
    pdf_path.write_bytes(b"pdf-content")

    smtp = CaptureSmtp()
    use_case = SendKindleEmailUseCase(smtp_port=smtp, logger=DummyLogger())

    try:
        use_case.execute(
            run_id="2026-04-15-abc123",
            pdf_path=pdf_path,
            kindle_address="invalid-address",
            subject="digest",
        )
    except ValueError as exc:
        assert "KINDLE_ADDRESS" in str(exc)
    else:
        raise AssertionError("expected ValueError for invalid kindle address")
