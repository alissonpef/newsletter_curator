from datetime import date, datetime, timezone

from hermes.app.use_cases.catalog_digest_library import CatalogDigestLibraryUseCase


class DummyClock:
    def today_local(self) -> date:
        return date(2026, 4, 15)

    def now_utc(self) -> datetime:
        return datetime(2026, 4, 15, 12, 0, tzinfo=timezone.utc)


class DummyStateStore:
    def list_runs(self, limit: int = 100, date_from=None, date_to=None):
        return [
            {
                "run_id": "run-ready",
                "date_ref": "2026-04-15",
                "status": "succeeded",
                "checkpoint": "finished",
                "started_at": "2026-04-15T08:00:00+00:00",
                "finished_at": "2026-04-15T08:15:00+00:00",
                "error": None,
            },
            {
                "run_id": "run-partial",
                "date_ref": "2026-04-14",
                "status": "failed",
                "checkpoint": "synthesize_podcast",
                "started_at": "2026-04-14T09:00:00+00:00",
                "finished_at": "2026-04-14T09:05:00+00:00",
                "error": "audio timeout",
            },
            {
                "run_id": "run-failed",
                "date_ref": "2026-04-13",
                "status": "failed",
                "checkpoint": "render_pdf",
                "started_at": "2026-04-13T07:00:00+00:00",
                "finished_at": "2026-04-13T07:02:00+00:00",
                "error": "template crash",
            },
        ]


def test_build_overview_combines_artifacts_and_runs(tmp_path) -> None:
    pdf_dir = tmp_path / "pdf"
    audio_dir = tmp_path / "audio"
    pdf_dir.mkdir()
    audio_dir.mkdir()

    (pdf_dir / "2026-04-15-mercado.pdf").write_bytes(b"pdf-ready")
    (audio_dir / "2026-04-15-podcast-mercado.wav").write_bytes(b"audio-ready")
    (pdf_dir / "2026-04-14-mercado.pdf").write_bytes(b"pdf-partial")

    use_case = CatalogDigestLibraryUseCase(
        state_store=DummyStateStore(),
        pdf_output_dir=pdf_dir,
        audio_output_dir=audio_dir,
        clock=DummyClock(),
    )

    overview = use_case.build_overview(days_back=3, active_dates={date(2026, 4, 14)})

    assert overview.ready_days == 1
    assert overview.running_days == 1
    assert overview.failed_days == 1
    assert overview.total_pdfs == 2
    assert overview.total_audios == 1

    first, second, third = overview.entries
    assert first.date_ref == date(2026, 4, 15)
    assert first.status == "ready"
    assert second.date_ref == date(2026, 4, 14)
    assert second.status == "running"
    assert third.date_ref == date(2026, 4, 13)
    assert third.status == "failed"
    assert third.latest_run is not None
    assert third.latest_run.error == "template crash"
