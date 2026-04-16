from __future__ import annotations

from datetime import date, datetime, timezone

from hermes.app.use_cases.catalog_digest_library import (
    DayLibraryEntry,
    LibraryOverview,
)
from hermes.web.server import DashboardWebApp


class DummyLogger:
    def info(self, *args, **kwargs):
        return None

    def warning(self, *args, **kwargs):
        return None

    def exception(self, *args, **kwargs):
        return None


class DummyCatalog:
    def __init__(self, tmp_path) -> None:
        self.pdf_output_dir = tmp_path / "pdf"
        self.audio_output_dir = tmp_path / "audio"
        self.pdf_output_dir.mkdir(parents=True, exist_ok=True)
        self.audio_output_dir.mkdir(parents=True, exist_ok=True)

    def today_local(self) -> date:
        return date(2026, 4, 15)

    def get_entry(self, date_ref: date, active_dates: set[date] | None = None) -> DayLibraryEntry:
        status = "running" if active_dates and date_ref in active_dates else "missing"
        summary = "Pipeline em andamento." if status == "running" else "Nenhum artefato disponível."
        return DayLibraryEntry(
            date_ref=date_ref,
            status=status,
            summary=summary,
            pdf_artifacts=[],
            audio_artifacts=[],
            latest_run=None,
            run_history=[],
        )

    def build_overview(self, days_back: int, selected_date: date | None = None, active_dates: set[date] | None = None) -> LibraryOverview:
        selected = selected_date or self.today_local()
        entry = self.get_entry(selected, active_dates=active_dates)
        return LibraryOverview(
            generated_at=datetime(2026, 4, 15, 15, 0, tzinfo=timezone.utc),
            days_back=days_back,
            total_days=1,
            ready_days=0,
            partial_days=0,
            running_days=1 if entry.status == "running" else 0,
            failed_days=0,
            missing_days=1 if entry.status == "missing" else 0,
            total_pdfs=0,
            total_audios=0,
            selected_date=selected,
            selected_entry=entry,
            entries=[entry],
        )


def test_public_error_message_is_hidden_on_non_loopback_host(tmp_path) -> None:
    app = DashboardWebApp(
        host="0.0.0.0",
        port=8787,
        default_days_back=14,
        project_root=tmp_path,
        catalog_use_case=DummyCatalog(tmp_path),
        orchestrator_factory=lambda: None,
        logger=DummyLogger(),
    )

    assert app._public_error_message("token=secret") == (
        "Falha interna na execucao. Consulte os logs do servidor para detalhes."
    )


def test_public_error_message_is_visible_on_loopback_host(tmp_path) -> None:
    app = DashboardWebApp(
        host="127.0.0.1",
        port=8787,
        default_days_back=14,
        project_root=tmp_path,
        catalog_use_case=DummyCatalog(tmp_path),
        orchestrator_factory=lambda: None,
        logger=DummyLogger(),
    )

    assert app._public_error_message("token=secret") == "token=secret"


def test_submit_generation_is_idempotent_while_job_is_active(tmp_path, monkeypatch) -> None:
    app = DashboardWebApp(
        host="127.0.0.1",
        port=8787,
        default_days_back=14,
        project_root=tmp_path,
        catalog_use_case=DummyCatalog(tmp_path),
        orchestrator_factory=lambda: None,
        logger=DummyLogger(),
    )

    monkeypatch.setattr("threading.Thread.start", lambda self: None)

    job_a, created_a = app._submit_generation(date_ref=date(2026, 4, 15), force=False)
    job_b, created_b = app._submit_generation(date_ref=date(2026, 4, 15), force=False)

    assert created_a is True
    assert created_b is False
    assert job_a is job_b
    assert job_b.status == "queued"
