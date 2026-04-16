from __future__ import annotations

import base64
import json
import os
import ipaddress
import hmac
import mimetypes
import threading
from dataclasses import dataclass
from datetime import date, datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlparse

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..app.use_cases.catalog_digest_library import (
    CatalogDigestLibraryUseCase,
    DayLibraryEntry,
    LibraryArtifact,
    LibraryOverview,
    RunRecord,
)

_MONTHS_PT_BR = [
    "jan",
    "fev",
    "mar",
    "abr",
    "mai",
    "jun",
    "jul",
    "ago",
    "set",
    "out",
    "nov",
    "dez",
]
_STATUS_LABELS = {
    "ready": "Pronto",
    "partial": "Parcial",
    "running": "Em processamento",
    "failed": "Falhou",
    "missing": "Nao gerado",
    "queued": "Na fila",
    "succeeded": "Concluido",
}
_MAX_REQUEST_BYTES = 64 * 1024
_STREAM_CHUNK_BYTES = 64 * 1024
_MAX_JOB_HISTORY = 180
_JOB_RETENTION_HOURS = 48


@dataclass(slots=True)
class GenerationJob:
    date_ref: date
    status: str
    requested_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    message: str = ""
    run_id: str | None = None
    error: str | None = None
    force: bool = False


class DashboardWebApp:
    def __init__(
        self,
        host: str,
        port: int,
        default_days_back: int,
        project_root: Path,
        catalog_use_case: CatalogDigestLibraryUseCase,
        orchestrator_factory,
        logger,
    ) -> None:
        self._host = host
        self._port = port
        self._default_days_back = max(1, default_days_back)
        self._project_root = Path(project_root)
        self._catalog = catalog_use_case
        self._orchestrator_factory = orchestrator_factory
        self._logger = logger
        self._jobs: dict[str, GenerationJob] = {}
        self._jobs_lock = threading.Lock()
        self._template_env = Environment(
            loader=FileSystemLoader(str(self._project_root / "src/hermes/templates")),
            autoescape=select_autoescape(("html", "xml", "j2")),
        )
        self._static_dir = self._project_root / "src/hermes/web/static"
        self._requires_auth = not self._is_loopback_host(self._host)
        self._access_token = os.getenv("HERMES_WEB_TOKEN", "").strip()
        self._show_detailed_errors = self._is_loopback_host(self._host)
        if self._requires_auth and not self._access_token:
            self._logger.warning(
                "dashboard started on non-loopback host without HERMES_WEB_TOKEN; requests will be denied",
                extra={"run_id": "-"},
            )

    def build_handler(self):
        app = self

        class DashboardHandler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                app.handle_get(self)

            def do_POST(self) -> None:
                app.handle_post(self)

            def log_message(self, format: str, *args) -> None:
                app._logger.info(
                    "dashboard request %s",
                    format % args,
                    extra={"run_id": "-"},
                )

        return DashboardHandler

    def handle_get(self, handler: BaseHTTPRequestHandler) -> None:
        if not self._is_request_authorized(handler):
            self._send_json(
                handler,
                {"error": "Unauthorized. Provide X-Hermes-Token for remote access."},
                status=HTTPStatus.UNAUTHORIZED,
            )
            return

        parsed = urlparse(handler.path)
        if parsed.path == "/":
            self._render_dashboard_page(handler, parse_qs(parsed.query))
            return
        if parsed.path == "/api/overview":
            self._send_overview(handler, parse_qs(parsed.query))
            return
        if parsed.path.startswith("/api/days/"):
            self._send_day_details(handler, parsed.path.rsplit("/", 1)[-1])
            return
        if parsed.path.startswith("/artifacts/pdf/"):
            self._send_artifact(handler, "pdf", parsed.path[len("/artifacts/pdf/") :])
            return
        if parsed.path.startswith("/artifacts/audio/"):
            self._send_artifact(handler, "audio", parsed.path[len("/artifacts/audio/") :])
            return
        if parsed.path == "/static/dashboard.css":
            self._send_static_file(handler, self._static_dir / "dashboard.css", "text/css; charset=utf-8")
            return
        if parsed.path == "/static/dashboard.js":
            self._send_static_file(
                handler,
                self._static_dir / "dashboard.js",
                "application/javascript; charset=utf-8",
            )
            return
        self._send_json(handler, {"error": "Route not found."}, status=HTTPStatus.NOT_FOUND)

    def handle_post(self, handler: BaseHTTPRequestHandler) -> None:
        if not self._is_request_authorized(handler):
            self._send_json(
                handler,
                {"error": "Unauthorized. Provide X-Hermes-Token for remote access."},
                status=HTTPStatus.UNAUTHORIZED,
            )
            return

        parsed = urlparse(handler.path)
        if parsed.path != "/api/generate":
            self._send_json(handler, {"error": "Route not found."}, status=HTTPStatus.NOT_FOUND)
            return

        try:
            payload = self._read_request_payload(handler)
        except ValueError as exc:
            self._send_json(handler, {"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return

        raw_date = str(payload.get("date_ref", "")).strip()
        if not raw_date:
            self._send_json(handler, {"error": "date_ref is required."}, status=HTTPStatus.BAD_REQUEST)
            return

        try:
            date_ref = date.fromisoformat(raw_date)
        except ValueError:
            self._send_json(
                handler,
                {"error": "date_ref must use YYYY-MM-DD."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        force = self._as_bool(payload.get("force"))
        try:
            job, created = self._submit_generation(date_ref=date_ref, force=force)
        except ValueError as exc:
            self._send_json(handler, {"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return

        active_dates = self._active_dates()
        entry = self._catalog.get_entry(date_ref, active_dates=active_dates)
        self._send_json(
            handler,
            {
                "created": created,
                "entry": self._serialize_entry(entry),
                "job": self._serialize_job(job),
            },
            status=HTTPStatus.ACCEPTED if created else HTTPStatus.OK,
        )

    def _render_dashboard_page(self, handler: BaseHTTPRequestHandler, query: dict[str, list[str]]) -> None:
        days_back = self._parse_days_back(query.get("days", [str(self._default_days_back)])[0])
        selected_date = self._parse_optional_date(query.get("date", [""])[0])
        payload = self._build_overview_payload(days_back=days_back, selected_date=selected_date)
        state_payload_b64 = base64.b64encode(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ).decode("ascii")
        template = self._template_env.get_template("dashboard.html.j2")
        html = template.render(
            page_title="Hermes Studio",
            state_payload_b64=state_payload_b64,
        )
        self._send_html(handler, html)

    def _send_overview(self, handler: BaseHTTPRequestHandler, query: dict[str, list[str]]) -> None:
        days_back = self._parse_days_back(query.get("days", [str(self._default_days_back)])[0])
        selected_date = self._parse_optional_date(query.get("date", [""])[0])
        payload = self._build_overview_payload(days_back=days_back, selected_date=selected_date)
        self._send_json(handler, payload)

    def _send_day_details(self, handler: BaseHTTPRequestHandler, raw_date: str) -> None:
        try:
            date_ref = date.fromisoformat(raw_date)
        except ValueError:
            self._send_json(handler, {"error": "invalid date"}, status=HTTPStatus.BAD_REQUEST)
            return

        active_dates = self._active_dates()
        entry = self._catalog.get_entry(date_ref, active_dates=active_dates)
        self._send_json(
            handler,
            {
                "entry": self._serialize_entry(entry),
                "job": self._serialize_job(self._get_job(date_ref)),
            },
        )

    def _send_artifact(self, handler: BaseHTTPRequestHandler, artifact_type: str, raw_filename: str) -> None:
        filename = unquote(raw_filename)
        base_dir = self._catalog.pdf_output_dir if artifact_type == "pdf" else self._catalog.audio_output_dir
        target = (base_dir / filename).resolve()
        base_resolved = base_dir.resolve()
        if target.parent != base_resolved or not target.exists() or not target.is_file():
            self._send_json(handler, {"error": "artifact not found"}, status=HTTPStatus.NOT_FOUND)
            return

        content_type = "application/pdf" if artifact_type == "pdf" else "audio/wav"
        disposition = "attachment" if artifact_type == "pdf" else "inline"
        stat = target.stat()
        handler.send_response(HTTPStatus.OK)
        handler.send_header("Content-Type", content_type)
        handler.send_header("Content-Length", str(stat.st_size))
        handler.send_header("Content-Disposition", f'{disposition}; filename="{target.name}"')
        handler.send_header("Cache-Control", "no-store")
        handler.send_header("X-Content-Type-Options", "nosniff")
        handler.end_headers()
        with target.open("rb") as stream:
            while True:
                chunk = stream.read(_STREAM_CHUNK_BYTES)
                if not chunk:
                    break
                handler.wfile.write(chunk)

    def _send_static_file(
        self,
        handler: BaseHTTPRequestHandler,
        path: Path,
        content_type: str | None = None,
    ) -> None:
        if not path.exists() or not path.is_file():
            self._send_json(handler, {"error": "static asset not found"}, status=HTTPStatus.NOT_FOUND)
            return
        data = path.read_bytes()
        resolved_type = content_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        handler.send_response(HTTPStatus.OK)
        handler.send_header("Content-Type", resolved_type)
        handler.send_header("Content-Length", str(len(data)))
        handler.send_header("Cache-Control", "no-store")
        handler.send_header("X-Content-Type-Options", "nosniff")
        handler.end_headers()
        handler.wfile.write(data)

    def _build_overview_payload(self, days_back: int, selected_date: date | None) -> dict[str, Any]:
        active_dates = self._active_dates()
        overview = self._catalog.build_overview(
            days_back=days_back,
            selected_date=selected_date,
            active_dates=active_dates,
        )
        return self._serialize_overview(overview, selected_job=self._get_job(overview.selected_date))

    def _submit_generation(self, date_ref: date, force: bool) -> tuple[GenerationJob, bool]:
        if date_ref > self._catalog.today_local():
            raise ValueError("Nao faz sentido gerar um resumo para uma data futura.")

        job_key = date_ref.isoformat()
        with self._jobs_lock:
            self._prune_jobs_locked()
            existing = self._jobs.get(job_key)
            if existing is not None and existing.status in {"queued", "running"}:
                return existing, False

            active_dates = self._active_dates_locked()
            entry = self._catalog.get_entry(date_ref, active_dates=active_dates)
            if not force and entry.pdf_artifacts and entry.audio_artifacts:
                ready_job = GenerationJob(
                    date_ref=date_ref,
                    status="ready",
                    requested_at=datetime.now(timezone.utc),
                    finished_at=datetime.now(timezone.utc),
                    message="Ja existe PDF e podcast disponiveis para esta data.",
                    run_id=entry.latest_run.run_id if entry.latest_run else None,
                    error=entry.latest_run.error if entry.latest_run else None,
                    force=False,
                )
                self._jobs[job_key] = ready_job
                return ready_job, False

            job = GenerationJob(
                date_ref=date_ref,
                status="queued",
                requested_at=datetime.now(timezone.utc),
                message="Solicitacao recebida. Preparando a execucao.",
                force=force,
            )
            self._jobs[job_key] = job

        worker = threading.Thread(
            target=self._run_generation,
            args=(date_ref,),
            daemon=True,
            name=f"hermes-dashboard-{job_key}",
        )
        worker.start()
        return job, True

    def _run_generation(self, date_ref: date) -> None:
        job_key = date_ref.isoformat()
        self._update_job(
            job_key,
            status="running",
            started_at=datetime.now(timezone.utc),
            message="Buscando e-mails e gerando PDF e podcast.",
        )
        try:
            orchestrator = self._orchestrator_factory()
            state = orchestrator.run_daily(date_ref=date_ref, dry_run=False)
            entry = self._catalog.get_entry(date_ref)
            if state.status == "succeeded":
                message = "Conteudo atualizado com sucesso." if (entry.pdf_artifacts or entry.audio_artifacts) else (
                    "Execucao concluida, mas nenhum artefato apareceu no catalogo."
                )
                self._update_job(
                    job_key,
                    status="succeeded",
                    finished_at=datetime.now(timezone.utc),
                    message=message,
                    run_id=state.run_id,
                    error=entry.latest_run.error if entry.latest_run else None,
                )
                return

            self._update_job(
                job_key,
                status="failed",
                finished_at=datetime.now(timezone.utc),
                message="A execucao terminou com falha.",
                run_id=state.run_id,
                error=entry.latest_run.error if entry.latest_run else "Falha nao detalhada.",
            )
        except Exception as exc:
            self._logger.exception(
                "dashboard generation failed",
                extra={"run_id": "-", "date_ref": date_ref.isoformat()},
            )
            self._update_job(
                job_key,
                status="failed",
                finished_at=datetime.now(timezone.utc),
                message="Nao foi possivel concluir a geracao.",
                error=self._public_error_message(str(exc)),
            )

    def _update_job(self, job_key: str, **updates: Any) -> GenerationJob:
        with self._jobs_lock:
            job = self._jobs[job_key]
            for field_name, value in updates.items():
                setattr(job, field_name, value)
            self._prune_jobs_locked()
            return job

    def _get_job(self, date_ref: date) -> GenerationJob | None:
        with self._jobs_lock:
            return self._jobs.get(date_ref.isoformat())

    def _active_dates(self) -> set[date]:
        with self._jobs_lock:
            return self._active_dates_locked()

    def _active_dates_locked(self) -> set[date]:
        return {
            job.date_ref
            for job in self._jobs.values()
            if job.status in {"queued", "running"}
        }

    def _prune_jobs_locked(self) -> None:
        now = datetime.now(timezone.utc)
        cutoff = now.timestamp() - (_JOB_RETENTION_HOURS * 3600)

        removable_keys = [
            key
            for key, job in self._jobs.items()
            if job.status not in {"queued", "running"}
            and (
                (job.finished_at is not None and job.finished_at.timestamp() < cutoff)
                or (job.finished_at is None and job.requested_at.timestamp() < cutoff)
            )
        ]
        for key in removable_keys:
            self._jobs.pop(key, None)

        if len(self._jobs) <= _MAX_JOB_HISTORY:
            return

        # Keep active jobs and newest completed jobs.
        sorted_items = sorted(
            self._jobs.items(),
            key=lambda pair: (
                1 if pair[1].status in {"queued", "running"} else 0,
                pair[1].finished_at or pair[1].requested_at,
            ),
            reverse=True,
        )
        keep_keys = {key for key, _ in sorted_items[:_MAX_JOB_HISTORY]}
        for key in list(self._jobs):
            if key not in keep_keys:
                self._jobs.pop(key, None)

    def _public_error_message(self, error: str | None) -> str | None:
        if not error:
            return None
        if self._show_detailed_errors:
            return error
        return "Falha interna na execucao. Consulte os logs do servidor para detalhes."

    def _serialize_overview(
        self,
        overview: LibraryOverview,
        selected_job: GenerationJob | None,
    ) -> dict[str, Any]:
        return {
            "generatedAt": overview.generated_at.isoformat(),
            "generatedAtLabel": self._format_timestamp(overview.generated_at),
            "daysBack": overview.days_back,
            "selectedDate": overview.selected_date.isoformat(),
            "stats": {
                "totalDays": overview.total_days,
                "readyDays": overview.ready_days,
                "partialDays": overview.partial_days,
                "runningDays": overview.running_days,
                "failedDays": overview.failed_days,
                "missingDays": overview.missing_days,
                "totalPdfs": overview.total_pdfs,
                "totalAudios": overview.total_audios,
            },
            "entries": [self._serialize_entry(entry) for entry in overview.entries],
            "selectedEntry": self._serialize_entry(overview.selected_entry),
            "selectedJob": self._serialize_job(selected_job),
            "baseUrl": f"http://{self._host}:{self._port}",
        }

    def _serialize_entry(self, entry: DayLibraryEntry) -> dict[str, Any]:
        return {
            "dateRef": entry.date_ref.isoformat(),
            "dateLabel": self._format_date(entry.date_ref),
            "status": entry.status,
            "statusLabel": _STATUS_LABELS.get(entry.status, entry.status.title()),
            "summary": entry.summary,
            "pdfCount": len(entry.pdf_artifacts),
            "audioCount": len(entry.audio_artifacts),
            "pdfArtifacts": [self._serialize_artifact(artifact) for artifact in entry.pdf_artifacts],
            "audioArtifacts": [self._serialize_artifact(artifact) for artifact in entry.audio_artifacts],
            "latestRun": self._serialize_run(entry.latest_run),
            "runHistory": [self._serialize_run(run) for run in entry.run_history],
            "hasContent": bool(entry.pdf_artifacts or entry.audio_artifacts),
            "isReady": bool(entry.pdf_artifacts and entry.audio_artifacts),
        }

    def _serialize_artifact(self, artifact: LibraryArtifact) -> dict[str, Any]:
        return {
            "type": artifact.artifact_type,
            "filename": artifact.filename,
            "sizeBytes": artifact.size_bytes,
            "sizeLabel": self._format_bytes(artifact.size_bytes),
            "modifiedAt": artifact.modified_at.isoformat(),
            "modifiedAtLabel": self._format_timestamp(artifact.modified_at),
            "url": f"/artifacts/{artifact.artifact_type}/{quote(artifact.filename)}",
        }

    def _serialize_run(self, run: RunRecord | None) -> dict[str, Any] | None:
        if run is None:
            return None
        return {
            "runId": run.run_id,
            "dateRef": run.date_ref.isoformat(),
            "status": run.status,
            "statusLabel": _STATUS_LABELS.get(run.status, run.status.title()),
            "checkpoint": run.checkpoint,
            "checkpointLabel": run.checkpoint.replace("_", " "),
            "startedAt": run.started_at.isoformat(),
            "startedAtLabel": self._format_timestamp(run.started_at),
            "finishedAt": run.finished_at.isoformat() if run.finished_at else None,
            "finishedAtLabel": self._format_timestamp(run.finished_at) if run.finished_at else None,
            "error": self._public_error_message(run.error),
        }

    def _serialize_job(self, job: GenerationJob | None) -> dict[str, Any] | None:
        if job is None:
            return None
        return {
            "dateRef": job.date_ref.isoformat(),
            "status": job.status,
            "statusLabel": _STATUS_LABELS.get(job.status, job.status.title()),
            "message": job.message,
            "requestedAt": job.requested_at.isoformat(),
            "requestedAtLabel": self._format_timestamp(job.requested_at),
            "startedAt": job.started_at.isoformat() if job.started_at else None,
            "startedAtLabel": self._format_timestamp(job.started_at) if job.started_at else None,
            "finishedAt": job.finished_at.isoformat() if job.finished_at else None,
            "finishedAtLabel": self._format_timestamp(job.finished_at) if job.finished_at else None,
            "runId": job.run_id,
            "error": self._public_error_message(job.error),
            "force": job.force,
        }

    def _read_request_payload(self, handler: BaseHTTPRequestHandler) -> dict[str, Any]:
        raw_length = handler.headers.get("Content-Length", "0")
        try:
            length = int(raw_length) if raw_length else 0
        except ValueError as exc:
            raise ValueError("invalid Content-Length header") from exc

        if length < 0:
            raise ValueError("invalid Content-Length header")
        if length > _MAX_REQUEST_BYTES:
            raise ValueError(
                f"payload too large; maximum is {_MAX_REQUEST_BYTES} bytes"
            )

        raw_body = handler.rfile.read(length) if length > 0 else b""
        content_type = handler.headers.get("Content-Type", "")
        if "application/json" in content_type:
            if not raw_body:
                return {}
            try:
                payload = json.loads(raw_body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError("invalid JSON payload") from exc
            if isinstance(payload, dict):
                return payload
            raise ValueError("JSON payload must be an object")

        try:
            parsed = parse_qs(raw_body.decode("utf-8"))
        except UnicodeDecodeError as exc:
            raise ValueError("invalid request payload encoding") from exc
        return {key: values[0] for key, values in parsed.items()}

    def _is_loopback_host(self, host: str) -> bool:
        normalized = str(host).strip().lower()
        if normalized in {"localhost", "127.0.0.1", "::1"}:
            return True
        try:
            return ipaddress.ip_address(normalized).is_loopback
        except ValueError:
            return False

    def _is_request_authorized(self, handler: BaseHTTPRequestHandler) -> bool:
        if not self._requires_auth:
            return True
        if not self._access_token:
            return False

        provided = handler.headers.get("X-Hermes-Token", "").strip()
        if not provided:
            parsed = urlparse(handler.path)
            token = parse_qs(parsed.query).get("token", [""])[0]
            provided = token.strip()

        if not provided:
            return False
        return hmac.compare_digest(provided, self._access_token)

    def _parse_days_back(self, raw_value: str) -> int:
        try:
            value = int(raw_value)
        except (TypeError, ValueError):
            return self._default_days_back
        return min(max(value, 1), 60)

    def _parse_optional_date(self, raw_value: str) -> date | None:
        raw = str(raw_value).strip()
        if not raw:
            return None
        try:
            return date.fromisoformat(raw)
        except ValueError:
            return None

    def _as_bool(self, value: Any) -> bool:
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def _send_html(self, handler: BaseHTTPRequestHandler, payload: str) -> None:
        data = payload.encode("utf-8")
        handler.send_response(HTTPStatus.OK)
        handler.send_header("Content-Type", "text/html; charset=utf-8")
        handler.send_header("Content-Length", str(len(data)))
        handler.send_header("Cache-Control", "no-store")
        handler.send_header("X-Content-Type-Options", "nosniff")
        handler.send_header("Referrer-Policy", "no-referrer")
        handler.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'",
        )
        handler.end_headers()
        handler.wfile.write(data)

    def _send_json(
        self,
        handler: BaseHTTPRequestHandler,
        payload: dict[str, Any],
        status: HTTPStatus = HTTPStatus.OK,
    ) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Content-Length", str(len(data)))
        handler.send_header("Cache-Control", "no-store")
        handler.send_header("X-Content-Type-Options", "nosniff")
        handler.send_header("Referrer-Policy", "no-referrer")
        handler.end_headers()
        handler.wfile.write(data)

    def _format_date(self, value: date) -> str:
        return f"{value.day:02d} {_MONTHS_PT_BR[value.month - 1]} {value.year}"

    def _format_timestamp(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        local = value.astimezone() if value.tzinfo is not None else value
        return f"{local.day:02d} {_MONTHS_PT_BR[local.month - 1]} {local.year} • {local.hour:02d}:{local.minute:02d}"

    def _format_bytes(self, size_bytes: int) -> str:
        if size_bytes >= 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        if size_bytes >= 1024:
            return f"{size_bytes / 1024:.0f} KB"
        return f"{size_bytes} B"


def serve_dashboard(
    host: str,
    port: int,
    default_days_back: int,
    project_root: Path,
    catalog_use_case: CatalogDigestLibraryUseCase,
    orchestrator_factory,
    logger,
) -> None:
    app = DashboardWebApp(
        host=host,
        port=port,
        default_days_back=default_days_back,
        project_root=project_root,
        catalog_use_case=catalog_use_case,
        orchestrator_factory=orchestrator_factory,
        logger=logger,
    )
    server = ThreadingHTTPServer((host, port), app.build_handler())
    server.daemon_threads = True
    logger.info(
        "dashboard started at http://%s:%s",
        host,
        port,
        extra={"run_id": "-"},
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("dashboard stopped", extra={"run_id": "-"})
    finally:
        server.server_close()
