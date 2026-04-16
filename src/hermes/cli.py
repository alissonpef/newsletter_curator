from __future__ import annotations

import shutil
from contextlib import nullcontext
from datetime import date, datetime
from pathlib import Path
from urllib import request

import typer

from .adapters.imap.imaplib_client import ImaplibClient
from .adapters.market.yahoo_market_client import YahooMarketClient
from .adapters.ollama.ollama_chat_client import OllamaChatClient
from .adapters.ollama.ollama_embed_client import OllamaEmbedClient
from .adapters.pdf.weasyprint_renderer import WeasyprintRenderer
from .adapters.smtp.smtp_client import SmtpClient
from .adapters.state.sqlite_state_store import SqliteStateStore
from .adapters.tts.piper_tts_adapter import PiperTtsAdapter
from .adapters.vector.chroma_repository import ChromaRepository
from .app.orchestrator import DailyPipelineOrchestrator
from .app.runtime_config import (
    CurateDailyDigestConfig,
    IndexEmbeddingsConfig,
    PipelineRuntimeConfig,
    PodcastSynthesisConfig,
    RenderPdfConfig,
)
from .app.use_cases.build_market_snapshot import BuildMarketSnapshotUseCase
from .app.use_cases.catalog_digest_library import CatalogDigestLibraryUseCase
from .app.use_cases.curate_daily_digest import CurateDailyDigestUseCase
from .app.use_cases.fetch_new_emails import FetchNewEmailsUseCase
from .app.use_cases.index_embeddings import IndexEmbeddingsUseCase
from .app.use_cases.parse_and_clean import ParseAndCleanUseCase
from .app.use_cases.persist_run_state import PersistRunStateUseCase
from .app.use_cases.render_pdf import RenderPdfUseCase
from .app.use_cases.send_kindle_email import SendKindleEmailUseCase
from .app.use_cases.synthesize_podcast import SynthesizePodcastUseCase
from .core.services import ChunkingService, LinkExtractionService, NormalizationService
from .infra.clock import SystemClock
from .infra.logging import configure_logging, get_logger
from .infra.prompt_loader import load_prompt_file
from .infra.settings import load_settings
from .web.server import serve_dashboard

app = typer.Typer(help="Newsletter curator CLI", add_completion=False)


def _build_orchestrator(
    *,
    send_kindle: bool = True,
    generate_podcast: bool = True,
) -> DailyPipelineOrchestrator:
    settings = load_settings()
    configure_logging(settings.logging_config_path)
    logger = get_logger("hermes")

    state_store = SqliteStateStore(
        sqlite_path=str(settings.state_sqlite_path),
        checkpoints_json_path=str(settings.state_checkpoints_path),
    )

    imap_client = ImaplibClient(
        host=settings.imap.host,
        port=settings.imap.port,
        username=settings.imap.username,
        password=settings.imap.password,
        use_ssl=settings.imap.use_ssl,
    )
    smtp_client = SmtpClient(
        host=settings.smtp.host,
        port=settings.smtp.port,
        username=settings.smtp.username,
        password=settings.smtp.password,
        use_ssl=settings.smtp.use_ssl,
    )
    ollama_chat = OllamaChatClient(
        base_url=settings.ollama.base_url,
        timeout_seconds=settings.ollama.timeout_seconds,
    )
    ollama_embed = OllamaEmbedClient(
        base_url=settings.ollama.base_url,
        timeout_seconds=settings.ollama.timeout_seconds,
    )
    vector_store = ChromaRepository(persist_path=str(settings.chroma.persist_path))
    market_data_client = YahooMarketClient()
    pdf_renderer = WeasyprintRenderer(template_dir=settings.project_root / "src/hermes/templates")
    tts_adapter = PiperTtsAdapter(
        piper_executable=settings.tts.piper_executable,
        model_path=settings.tts.model_path,
        sample_rate=settings.tts.sample_rate,
    )

    normalizer = NormalizationService()
    link_extractor = LinkExtractionService()
    chunking_service = ChunkingService(
        chunk_size=settings.pipeline.chunk_size,
        overlap=settings.pipeline.chunk_overlap,
    )

    consolidate_prompt = load_prompt_file(
        settings.prompts.consolidate_topics_path,
        fallback="Consolide os temas diarios a partir do contexto recebido.",
    )
    editorial_style_prompt = load_prompt_file(
        settings.prompts.editorial_style_path,
        fallback="Estilo editorial objetivo e direto.",
    )
    podcast_script_prompt = load_prompt_file(
        settings.prompts.podcast_script_path,
        fallback="Crie um roteiro curto de podcast em portugues com base no digest diario.",
    )

    index_config = IndexEmbeddingsConfig(
        embed_model=settings.ollama.embed_model,
        chunks_collection=settings.chroma.chunks_collection,
    )
    curate_config = CurateDailyDigestConfig(
        embed_model=settings.ollama.embed_model,
        chat_model=settings.ollama.chat_model,
        chunks_collection=settings.chroma.chunks_collection,
        digests_collection=settings.chroma.digests_collection,
        topic_memory_collection=settings.chroma.topic_memory_collection,
        consolidate_prompt=consolidate_prompt,
        editorial_style_prompt=editorial_style_prompt,
    )
    render_pdf_config = RenderPdfConfig(
        template_name=settings.pdf.template_name,
        output_dir=settings.pdf.output_dir,
    )
    podcast_config = PodcastSynthesisConfig(
        chat_model=settings.ollama.chat_model,
        output_dir=settings.tts.output_dir,
        script_prompt=podcast_script_prompt,
    )
    runtime_config = PipelineRuntimeConfig(
        mailbox=settings.imap.mailbox,
        search_strategy=settings.imap.search_strategy,
        since_hours_back=settings.imap.since_hours_back,
        negative_keywords=tuple(settings.pipeline.negative_keywords),
        allowed_senders=tuple(settings.pipeline.allowed_senders),
        topics=tuple(settings.pipeline.topics),
        kindle_address=settings.smtp.kindle_address,
        send_kindle=send_kindle,
        generate_podcast=generate_podcast,
    )

    fetch_new_emails_uc = FetchNewEmailsUseCase(imap_client, state_store, logger)
    parse_and_clean_uc = ParseAndCleanUseCase(normalizer, link_extractor, state_store, logger)
    index_embeddings_uc = IndexEmbeddingsUseCase(
        chunking_service,
        ollama_embed,
        vector_store,
        logger,
        config=index_config,
    )
    curate_daily_digest_uc = CurateDailyDigestUseCase(
        ollama_embed,
        vector_store,
        ollama_chat,
        logger,
        config=curate_config,
    )
    build_market_snapshot_uc = BuildMarketSnapshotUseCase(market_data_client, logger)
    render_pdf_uc = RenderPdfUseCase(pdf_renderer, logger, config=render_pdf_config)
    send_kindle_email_uc = SendKindleEmailUseCase(smtp_client, logger)
    synthesize_podcast_uc = SynthesizePodcastUseCase(
        ollama_chat,
        tts_adapter,
        logger,
        config=podcast_config,
    )
    persist_run_state_uc = PersistRunStateUseCase(state_store, SystemClock(), logger)

    orchestrator = DailyPipelineOrchestrator(
        fetch_new_emails_uc=fetch_new_emails_uc,
        parse_and_clean_uc=parse_and_clean_uc,
        index_embeddings_uc=index_embeddings_uc,
        curate_daily_digest_uc=curate_daily_digest_uc,
        render_pdf_uc=render_pdf_uc,
        send_kindle_email_uc=send_kindle_email_uc,
        synthesize_podcast_uc=synthesize_podcast_uc,
        persist_run_state_uc=persist_run_state_uc,
        state_store=state_store,
        lock=nullcontext(),
        clock=SystemClock(),
        logger=logger,
        build_market_snapshot_uc=build_market_snapshot_uc,
        runtime_config=runtime_config,
    )
    return orchestrator


def run_daily(date_ref: str | None = None, dry_run: bool = False) -> None:
    orchestrator = _build_orchestrator(send_kindle=True, generate_podcast=True)

    parsed_date: date | None = None
    if date_ref:
        try:
            parsed_date = date.fromisoformat(date_ref)
        except ValueError as exc:
            raise typer.BadParameter("date_ref must use YYYY-MM-DD") from exc

    state = orchestrator.run_daily(date_ref=parsed_date, dry_run=dry_run)
    if state.status != "succeeded":
        raise typer.Exit(code=1)


def replay_missed(days_back: int | None = None) -> None:
    settings = load_settings()
    resolved_days_back = int(days_back) if days_back is not None else int(settings.pipeline.replay_days_back)
    orchestrator = _build_orchestrator(send_kindle=True, generate_podcast=True)
    states = orchestrator.replay_missed_runs(days_back=resolved_days_back)
    if any(state.status != "succeeded" for state in states):
        raise typer.Exit(code=1)


def _resolve_latest_pdf(pdf_dir: Path) -> Path:
    candidates = [path for path in pdf_dir.glob("*.pdf") if path.is_file()]
    if not candidates:
        raise FileNotFoundError(f"no PDF files found in {pdf_dir}")

    candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return candidates[0]


def send_latest_kindle(pdf_path: str | None = None, subject: str = "") -> None:
    settings = load_settings()
    configure_logging(settings.logging_config_path)
    logger = get_logger("hermes")

    smtp_client = SmtpClient(
        host=settings.smtp.host,
        port=settings.smtp.port,
        username=settings.smtp.username,
        password=settings.smtp.password,
        use_ssl=settings.smtp.use_ssl,
    )
    sender = SendKindleEmailUseCase(smtp_client, logger)

    target_pdf = Path(pdf_path).expanduser().resolve() if pdf_path else _resolve_latest_pdf(settings.pdf.output_dir)
    run_id = f"manual-kindle-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    sender.execute(
        run_id=run_id,
        pdf_path=target_pdf,
        kindle_address=settings.smtp.kindle_address,
        subject=subject,
    )
    typer.echo(f"SENT: {target_pdf} -> {settings.smtp.kindle_address}")


def export_checkpoints() -> None:
    settings = load_settings()
    state_store = SqliteStateStore(
        sqlite_path=str(settings.state_sqlite_path),
        checkpoints_json_path=str(settings.state_checkpoints_path),
    )
    state_store.export_checkpoints_json()
    typer.echo(f"EXPORTED: {settings.state_checkpoints_path}")


def healthcheck() -> None:
    settings = load_settings()
    failures: list[str] = []

    required_paths = [
        settings.app_config_path,
        settings.logging_config_path,
        settings.state_checkpoints_path.parent,
        settings.project_root / "src/hermes/templates/newsletter.html.j2",
        settings.prompts.consolidate_topics_path,
        settings.prompts.editorial_style_path,
        settings.prompts.podcast_script_path,
    ]
    for path in required_paths:
        if not path.exists():
            failures.append(f"missing path: {path}")

    if Path(settings.tts.piper_executable).is_absolute():
        if not Path(settings.tts.piper_executable).exists():
            failures.append(f"piper executable not found: {settings.tts.piper_executable}")
    else:
        if shutil.which(settings.tts.piper_executable) is None:
            failures.append(f"piper executable not in PATH: {settings.tts.piper_executable}")

    if not settings.tts.model_path.exists():
        failures.append(f"piper model not found: {settings.tts.model_path}")

    kindle_address = settings.smtp.kindle_address.strip()
    if "@" not in kindle_address:
        failures.append("invalid KINDLE_ADDRESS: missing '@'")
    else:
        local_part, domain = kindle_address.rsplit("@", 1)
        if not local_part.strip() or domain.strip().lower() not in {"kindle.com", "free.kindle.com"}:
            failures.append(
                "invalid KINDLE_ADDRESS: expected *@kindle.com or *@free.kindle.com"
            )

    try:
        with request.urlopen(f"{settings.ollama.base_url.rstrip('/')}/api/tags", timeout=3):
            pass
    except Exception:
        failures.append("ollama endpoint unavailable")

    if failures:
        for failure in failures:
            typer.echo(f"FAIL: {failure}")
        raise typer.Exit(code=1)

    typer.echo("OK")


def serve_web(host: str | None = None, port: int | None = None, days_back: int | None = None) -> None:
    settings = load_settings()
    configure_logging(settings.logging_config_path)
    logger = get_logger("hermes.web")

    state_store = SqliteStateStore(
        sqlite_path=str(settings.state_sqlite_path),
        checkpoints_json_path=str(settings.state_checkpoints_path),
    )
    catalog = CatalogDigestLibraryUseCase(
        state_store=state_store,
        pdf_output_dir=settings.pdf.output_dir,
        audio_output_dir=settings.tts.output_dir,
        clock=SystemClock(),
    )

    def orchestrator_factory() -> DailyPipelineOrchestrator:
        return _build_orchestrator(send_kindle=False, generate_podcast=True)

    serve_dashboard(
        host=host or settings.web.host,
        port=port or settings.web.port,
        default_days_back=days_back or settings.web.default_days_back,
        project_root=settings.project_root,
        catalog_use_case=catalog,
        orchestrator_factory=orchestrator_factory,
        logger=logger,
    )


@app.command("run-daily")
def _run_daily_command(
    date_ref: str | None = typer.Option(None, help="Reference date in YYYY-MM-DD"),
    dry_run: bool = typer.Option(False, help="Run without external side effects"),
) -> None:
    run_daily(date_ref=date_ref, dry_run=dry_run)


@app.command("replay-missed")
def _replay_missed_command(
    days_back: int | None = typer.Option(None, min=1, help="How many days back to replay"),
) -> None:
    replay_missed(days_back=days_back)


@app.command("healthcheck")
def _healthcheck_command() -> None:
    healthcheck()


@app.command("send-latest-kindle")
def _send_latest_kindle_command(
    pdf_path: str | None = typer.Option(None, help="Optional path to a specific PDF file"),
    subject: str = typer.Option("", help="Optional custom email subject"),
) -> None:
    send_latest_kindle(pdf_path=pdf_path, subject=subject)


@app.command("export-checkpoints")
def _export_checkpoints_command() -> None:
    export_checkpoints()


@app.command("serve-web")
def _serve_web_command(
    host: str | None = typer.Option(None, help="Bind host for the dashboard"),
    port: int | None = typer.Option(None, min=1, help="Bind port for the dashboard"),
    days_back: int | None = typer.Option(None, min=1, help="Default history window in days"),
) -> None:
    serve_web(host=host, port=port, days_back=days_back)
