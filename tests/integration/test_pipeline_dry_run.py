from __future__ import annotations

from datetime import date

from hermes.app.orchestrator import DailyPipelineOrchestrator
from tests.unit.test_orchestrator import (
    DigestUC,
    DummyClock,
    DummyLock,
    DummyLogger,
    DummyStateStore,
    FetchUC,
    IndexUC,
    ParseUC,
    PersistSpy,
    RenderUC,
    SendUC,
    SynthUC,
)


def test_pipeline_dry_run_end_to_end_without_external_side_effects() -> None:
    persist = PersistSpy(checkpoints=[], finished=[])
    send_uc = SendUC()
    synth_uc = SynthUC()

    orchestrator = DailyPipelineOrchestrator(
        fetch_new_emails_uc=FetchUC(),
        parse_and_clean_uc=ParseUC(),
        index_embeddings_uc=IndexUC(),
        curate_daily_digest_uc=DigestUC(),
        render_pdf_uc=RenderUC(),
        send_kindle_email_uc=send_uc,
        synthesize_podcast_uc=synth_uc,
        persist_run_state_uc=persist,
        state_store=DummyStateStore(),
        lock=DummyLock(),
        clock=DummyClock(),
        logger=DummyLogger(),
    )

    run_state = orchestrator.run_daily(date_ref=date(2026, 4, 14), dry_run=True)

    assert run_state.status == "succeeded"
    assert send_uc.called is False
    assert synth_uc.called is False
