from unittest.mock import AsyncMock, Mock, patch

import pytest

from hermes.use_cases.process_daily import ProcessDailyUseCase


@pytest.fixture
def mock_ports():
    email_port = Mock()
    llm_port = Mock()
    pdf_port = Mock()
    audio_port = Mock()
    state_repo = Mock()
    market_data_port = Mock()
    vector_store = Mock()

    state_repo.get_job.return_value = None
    state_repo.get_digest.return_value = None

    return {
        "email_port": email_port,
        "llm_port": llm_port,
        "pdf_port": pdf_port,
        "audio_port": audio_port,
        "state_repo": state_repo,
        "market_data_port": market_data_port,
        "vector_store": vector_store,
    }


@pytest.mark.anyio
async def test_process_daily_no_emails(mock_ports):
    mock_ports["email_port"].fetch_emails.return_value = []

    use_case = ProcessDailyUseCase(**mock_ports)

    await use_case.execute("2023-10-01")

    mock_ports["email_port"].fetch_emails.assert_called_once_with("2023-10-01")
    assert mock_ports["state_repo"].save_job.call_count >= 2
    last_job_call = mock_ports["state_repo"].save_job.call_args_list[-1]
    saved_job = last_job_call[0][1]
    assert saved_job["status"] == "succeeded"
    assert saved_job["statusLabel"] == "Sem conteúdo"
    assert "Nenhuma newsletter" in saved_job["message"]

    mock_ports["llm_port"].generate_summary.assert_not_called()
    mock_ports["pdf_port"].render_pdf.assert_not_called()
    mock_ports["audio_port"].generate_audio.assert_not_called()


@pytest.mark.anyio
async def test_process_daily_job_already_running(mock_ports):
    mock_ports["state_repo"].get_job.return_value = {"status": "running"}
    use_case = ProcessDailyUseCase(**mock_ports)

    await use_case.execute("2023-10-01")

    mock_ports["email_port"].fetch_emails.assert_not_called()


@pytest.mark.anyio
@patch("os.path.getsize")
async def test_process_daily_success(mock_getsize, mock_ports):
    mock_getsize.return_value = 2048

    mock_ports["email_port"].fetch_emails.return_value = [{"subject": "Test", "content": "Content"}]
    mock_ports["llm_port"].generate_summary.return_value = {
        "plainText": "Summary text",
        "ttsScript": "TTS text",
    }
    mock_ports["market_data_port"].fetch_market_data.return_value = {"IBOV": "+1%"}
    mock_ports["pdf_port"].render_pdf.return_value = "/tmp/test.pdf"

    mock_ports["audio_port"].generate_audio = AsyncMock(return_value="/tmp/test.mp3")

    use_case = ProcessDailyUseCase(**mock_ports)

    await use_case.execute("2023-10-01")

    mock_ports["email_port"].fetch_emails.assert_called_once()
    mock_ports["llm_port"].generate_summary.assert_called_once()
    mock_ports["market_data_port"].fetch_market_data.assert_called_once()
    mock_ports["pdf_port"].render_pdf.assert_called_once()
    mock_ports["audio_port"].generate_audio.assert_called_once_with("2023-10-01", "TTS text")

    mock_ports["vector_store"].index_newsletter.assert_called_once()
    mock_ports["vector_store"].index_digest.assert_called_once()

    last_job_call = mock_ports["state_repo"].save_job.call_args_list[-1]
    saved_job = last_job_call[0][1]
    assert saved_job["status"] == "succeeded"
    assert saved_job["progressPct"] == 100


@pytest.mark.anyio
async def test_process_daily_error_handling(mock_ports):
    mock_ports["email_port"].fetch_emails.side_effect = Exception("API Error")

    use_case = ProcessDailyUseCase(**mock_ports)

    with pytest.raises(Exception, match="API Error"):
        await use_case.execute("2023-10-01")

    last_job_call = mock_ports["state_repo"].save_job.call_args_list[-1]
    saved_job = last_job_call[0][1]
    assert saved_job["status"] == "failed"
    assert saved_job["error"] == "API Error"
