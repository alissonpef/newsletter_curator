from pathlib import Path
from unittest.mock import Mock

import pytest

from hermes.use_cases.send_to_kindle import SendToKindleUseCase


def test_execute_kindle_not_configured():
    kindle_port_mock = Mock()
    kindle_port_mock.is_configured.return_value = False
    state_repo_mock = Mock()

    use_case = SendToKindleUseCase(kindle_port_mock, state_repo_mock)

    with pytest.raises(
        RuntimeError,
        match="Configure SMTP e o remetente autorizado antes de usar o envio para Kindle.",
    ):
        use_case.execute("2023-10-01")


def test_execute_no_digest():
    kindle_port_mock = Mock()
    kindle_port_mock.is_configured.return_value = True

    state_repo_mock = Mock()
    state_repo_mock.get_digest.return_value = None

    use_case = SendToKindleUseCase(kindle_port_mock, state_repo_mock)

    with pytest.raises(ValueError, match="Nenhum digest encontrado para a data informada."):
        use_case.execute("2023-10-01")


def test_execute_no_pdf():
    kindle_port_mock = Mock()
    kindle_port_mock.is_configured.return_value = True

    state_repo_mock = Mock()
    state_repo_mock.get_digest.return_value = {"pdfArtifacts": []}

    use_case = SendToKindleUseCase(kindle_port_mock, state_repo_mock)

    with pytest.raises(ValueError, match="Ainda não existe PDF gerado para esta data."):
        use_case.execute("2023-10-01")


def test_execute_success():
    kindle_port_mock = Mock()
    kindle_port_mock.is_configured.return_value = True
    kindle_port_mock.send_pdf.return_value = "mykindle@kindle.com"

    state_repo_mock = Mock()
    digest_data = {"pdfArtifacts": [{"url": "http://example.com/test.pdf"}]}
    state_repo_mock.get_digest.return_value = digest_data

    use_case = SendToKindleUseCase(kindle_port_mock, state_repo_mock)

    result = use_case.execute("2023-10-01", kindle_email="mykindle@kindle.com")

    assert result["status"] == "sent"
    assert result["dateRef"] == "2023-10-01"
    assert result["kindleEmail"] == "mykindle@kindle.com"

    kindle_port_mock.send_pdf.assert_called_once_with(
        date_ref="2023-10-01",
        pdf_path=Path("data/pdf/test.pdf"),
        kindle_email="mykindle@kindle.com",
    )

    assert digest_data["lastKindleEmail"] == "mykindle@kindle.com"
    assert digest_data["lastKindleStatus"] == "sent"
    state_repo_mock.save_digest.assert_called_once_with("2023-10-01", digest_data)
