from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from hermes.app.orchestrator import DailyPipelineOrchestrator
from hermes.core.errors import LlmUnavailableError
from hermes.core.entities import DailyDigest, MarketSnapshotItem, MediaArtifact


class DummyLogger:
    def info(self, *args, **kwargs):
        return None

    def warning(self, *args, **kwargs):
        return None

    def exception(self, *args, **kwargs):
        return None


class DummyLock:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class DummyClock:
    def today_local(self) -> date:
        return date(2026, 4, 14)

    def now_utc(self) -> datetime:
        return datetime(2026, 4, 14, 10, 0, tzinfo=timezone.utc)


class DummyStateStore:
    def __init__(self) -> None:
        self.acquired: list[str] = []
        self.released: list[str] = []

    def acquire_run_lock(self, run_key: str) -> bool:
        self.acquired.append(run_key)
        return True

    def release_run_lock(self, run_key: str) -> None:
        self.released.append(run_key)


@dataclass
class PersistSpy:
    checkpoints: list[str]
    finished: list[str]

    def start(self, run_id: str, date_ref: date):
        return None

    def checkpoint(self, run_id: str, checkpoint: str, status: str = "running"):
        self.checkpoints.append(checkpoint)
        return None

    def finish(self, run_id: str, status: str, error: str | None = None):
        self.finished.append(status)
        from hermes.core.entities import RunState

        return RunState(
            run_id=run_id,
            status=status,
            started_at=datetime(2026, 4, 14, 10, 0, tzinfo=timezone.utc),
            finished_at=datetime(2026, 4, 14, 10, 1, tzinfo=timezone.utc),
            checkpoint="finished",
        )

    def recover_missed_dates(self, days_back: int):
        return []


class FetchUC:
    def execute(self, **kwargs):
        return [("100", b"raw")]


class ParseUC:
    def execute(self, **kwargs):
        return []


class IndexUC:
    def execute(self, **kwargs):
        return []


class DigestUC:
    def execute(self, **kwargs):
        return DailyDigest(
            run_id=kwargs["run_id"],
            date_ref=kwargs["date_ref"],
            themes=[],
            highlights=[],
            sources=[],
            final_text="texto",
        )


class RenderUC:
    def execute(self, **kwargs):
        path = Path("/tmp/test.pdf")
        path.write_bytes(b"pdf")
        return MediaArtifact(run_id=kwargs["run_id"], type="pdf", path=path, checksum="x")


class RenderCaptureUC:
    def __init__(self) -> None:
        self.last_digest = None

    def execute(self, **kwargs):
        self.last_digest = kwargs["digest"]
        path = Path("/tmp/test_capture.pdf")
        path.write_bytes(b"pdf")
        return MediaArtifact(run_id=kwargs["run_id"], type="pdf", path=path, checksum="x")


class SendUC:
    def __init__(self) -> None:
        self.called = False

    def execute(self, **kwargs):
        self.called = True


class SynthUC:
    def __init__(self) -> None:
        self.called = False

    def execute(self, **kwargs):
        self.called = True
        return MediaArtifact(
            run_id=kwargs["run_id"],
            type="audio",
            path=Path("/tmp/test.wav"),
            checksum="y",
        )


class MarketSnapshotUC:
    def execute(self, **kwargs):
        return [
            MarketSnapshotItem(
                label="IBOVESPA",
                symbol="^BVSP",
                price=197500.0,
                change_pct=0.42,
                currency="BRL",
                as_of=datetime(2026, 4, 15, 15, 30, tzinfo=timezone.utc),
            )
        ]


def test_orchestrator_run_daily_dry_run_succeeds() -> None:
    persist = PersistSpy(checkpoints=[], finished=[])
    send_uc = SendUC()
    synth_uc = SynthUC()
    store = DummyStateStore()

    orchestrator = DailyPipelineOrchestrator(
        fetch_new_emails_uc=FetchUC(),
        parse_and_clean_uc=ParseUC(),
        index_embeddings_uc=IndexUC(),
        curate_daily_digest_uc=DigestUC(),
        render_pdf_uc=RenderUC(),
        send_kindle_email_uc=send_uc,
        synthesize_podcast_uc=synth_uc,
        persist_run_state_uc=persist,
        state_store=store,
        lock=DummyLock(),
        clock=DummyClock(),
        logger=DummyLogger(),
    )

    state = orchestrator.run_daily(date_ref=date(2026, 4, 14), dry_run=True)

    assert state.status == "succeeded"
    assert "fetch_new_emails" in persist.checkpoints
    assert "parse_and_clean" in persist.checkpoints
    assert "index_embeddings" in persist.checkpoints
    assert "curate_daily_digest" in persist.checkpoints
    assert "render_pdf" in persist.checkpoints
    assert "send_kindle_email_skipped" in persist.checkpoints
    assert "synthesize_podcast_skipped" in persist.checkpoints
    assert send_uc.called is False
    assert synth_uc.called is False
    assert store.acquired == ["2026-04-14"]
    assert store.released == ["2026-04-14"]


def test_orchestrator_marks_failure_on_exception() -> None:
    class FailingFetch:
        def execute(self, **kwargs):
            raise RuntimeError("boom")

    persist = PersistSpy(checkpoints=[], finished=[])
    store = DummyStateStore()

    orchestrator = DailyPipelineOrchestrator(
        fetch_new_emails_uc=FailingFetch(),
        parse_and_clean_uc=ParseUC(),
        index_embeddings_uc=IndexUC(),
        curate_daily_digest_uc=DigestUC(),
        render_pdf_uc=RenderUC(),
        send_kindle_email_uc=SendUC(),
        synthesize_podcast_uc=SynthUC(),
        persist_run_state_uc=persist,
        state_store=store,
        lock=DummyLock(),
        clock=DummyClock(),
        logger=DummyLogger(),
    )

    state = orchestrator.run_daily(date_ref=date(2026, 4, 14), dry_run=False)
    assert state.status == "failed"
    assert persist.finished[-1] == "failed"
    assert store.released == ["2026-04-14"]


def test_orchestrator_uses_fallback_digest_when_ollama_unavailable() -> None:
    class FailingIndex:
        def execute(self, **kwargs):
            raise LlmUnavailableError("ollama embedding request failed")

    persist = PersistSpy(checkpoints=[], finished=[])
    store = DummyStateStore()

    orchestrator = DailyPipelineOrchestrator(
        fetch_new_emails_uc=FetchUC(),
        parse_and_clean_uc=ParseUC(),
        index_embeddings_uc=FailingIndex(),
        curate_daily_digest_uc=DigestUC(),
        render_pdf_uc=RenderUC(),
        send_kindle_email_uc=SendUC(),
        synthesize_podcast_uc=SynthUC(),
        persist_run_state_uc=persist,
        state_store=store,
        lock=DummyLock(),
        clock=DummyClock(),
        logger=DummyLogger(),
    )

    state = orchestrator.run_daily(date_ref=date(2026, 4, 14), dry_run=True)

    assert state.status == "succeeded"
    assert "curate_daily_digest_fallback" in persist.checkpoints


def test_orchestrator_fallback_digest_removes_urls_from_highlights() -> None:
    class FailingIndex:
        def execute(self, **kwargs):
            raise LlmUnavailableError("ollama embedding request failed")

    class ParseWithUrl:
        def execute(self, **kwargs):
            from hermes.core.entities import EmailItem

            return [
                EmailItem(
                    id="email-1",
                    message_id="<msg-1>",
                    uid="1",
                    sender="newsletter@neofeed.com.br",
                    subject="Assunto teste",
                    received_at=datetime(2026, 4, 15, 10, 0, tzinfo=timezone.utc),
                    body_text=(
                        "Veja mais em https://example.com/artigo?utm_source=test. "
                        "Leia o conteúdo deste e-mail no seu browser. "
                        "Detalhes importantes para o mercado brasileiro."
                    ),
                    links=["https://example.com/artigo?utm_source=test"],
                )
            ]

    persist = PersistSpy(checkpoints=[], finished=[])
    store = DummyStateStore()
    render_capture = RenderCaptureUC()

    orchestrator = DailyPipelineOrchestrator(
        fetch_new_emails_uc=FetchUC(),
        parse_and_clean_uc=ParseWithUrl(),
        index_embeddings_uc=FailingIndex(),
        curate_daily_digest_uc=DigestUC(),
        render_pdf_uc=render_capture,
        send_kindle_email_uc=SendUC(),
        synthesize_podcast_uc=SynthUC(),
        persist_run_state_uc=persist,
        state_store=store,
        lock=DummyLock(),
        clock=DummyClock(),
        logger=DummyLogger(),
    )

    state = orchestrator.run_daily(date_ref=date(2026, 4, 15), dry_run=True)

    assert state.status == "succeeded"
    assert render_capture.last_digest is not None
    assert "http" not in render_capture.last_digest.highlights[0].lower()
    assert "browser" not in render_capture.last_digest.highlights[0].lower()
    assert "Leitura rapida" in render_capture.last_digest.final_text
    assert "Cobertura detalhada" not in render_capture.last_digest.final_text


def test_orchestrator_enriches_digest_with_market_snapshot() -> None:
    persist = PersistSpy(checkpoints=[], finished=[])
    store = DummyStateStore()
    render_capture = RenderCaptureUC()

    orchestrator = DailyPipelineOrchestrator(
        fetch_new_emails_uc=FetchUC(),
        parse_and_clean_uc=ParseUC(),
        index_embeddings_uc=IndexUC(),
        curate_daily_digest_uc=DigestUC(),
        render_pdf_uc=render_capture,
        send_kindle_email_uc=SendUC(),
        synthesize_podcast_uc=SynthUC(),
        persist_run_state_uc=persist,
        state_store=store,
        lock=DummyLock(),
        clock=DummyClock(),
        logger=DummyLogger(),
        build_market_snapshot_uc=MarketSnapshotUC(),
    )

    state = orchestrator.run_daily(date_ref=date(2026, 4, 15), dry_run=True)

    assert state.status == "succeeded"
    assert "collect_market_snapshot" in persist.checkpoints
    assert render_capture.last_digest is not None
    assert len(render_capture.last_digest.market_snapshot) == 1
    assert render_capture.last_digest.market_snapshot[0].label == "IBOVESPA"
