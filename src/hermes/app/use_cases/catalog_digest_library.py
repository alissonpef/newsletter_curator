from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


_DATE_PREFIX = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2})(?:$|-)")


@dataclass(slots=True, frozen=True)
class LibraryArtifact:
    artifact_type: str
    filename: str
    path: Path
    size_bytes: int
    modified_at: datetime


@dataclass(slots=True, frozen=True)
class RunRecord:
    run_id: str
    date_ref: date
    status: str
    checkpoint: str
    started_at: datetime
    finished_at: datetime | None
    error: str | None


@dataclass(slots=True, frozen=True)
class DayLibraryEntry:
    date_ref: date
    status: str
    summary: str
    pdf_artifacts: list[LibraryArtifact]
    audio_artifacts: list[LibraryArtifact]
    latest_run: RunRecord | None
    run_history: list[RunRecord]


@dataclass(slots=True, frozen=True)
class LibraryOverview:
    generated_at: datetime
    days_back: int
    total_days: int
    ready_days: int
    partial_days: int
    running_days: int
    failed_days: int
    missing_days: int
    total_pdfs: int
    total_audios: int
    selected_date: date
    selected_entry: DayLibraryEntry
    entries: list[DayLibraryEntry]


class CatalogDigestLibraryUseCase:
    def __init__(self, state_store, pdf_output_dir: Path, audio_output_dir: Path, clock) -> None:
        self._state_store = state_store
        self._pdf_output_dir = Path(pdf_output_dir)
        self._audio_output_dir = Path(audio_output_dir)
        self._clock = clock

    @property
    def pdf_output_dir(self) -> Path:
        return self._pdf_output_dir

    @property
    def audio_output_dir(self) -> Path:
        return self._audio_output_dir

    def today_local(self) -> date:
        return self._clock.today_local()

    def build_overview(
        self,
        days_back: int = 14,
        selected_date: date | None = None,
        active_dates: set[date] | None = None,
    ) -> LibraryOverview:
        normalized_days_back = max(1, days_back)
        entries = self.list_entries(days_back=normalized_days_back, active_dates=active_dates)
        selected = selected_date or self._clock.today_local()
        selected_entry = next((entry for entry in entries if entry.date_ref == selected), None)
        if selected_entry is None:
            selected_entry = self.get_entry(selected, active_dates=active_dates)

        return LibraryOverview(
            generated_at=self._clock.now_utc(),
            days_back=normalized_days_back,
            total_days=len(entries),
            ready_days=sum(1 for entry in entries if entry.status == "ready"),
            partial_days=sum(1 for entry in entries if entry.status == "partial"),
            running_days=sum(1 for entry in entries if entry.status == "running"),
            failed_days=sum(1 for entry in entries if entry.status == "failed"),
            missing_days=sum(1 for entry in entries if entry.status == "missing"),
            total_pdfs=sum(len(entry.pdf_artifacts) for entry in entries),
            total_audios=sum(len(entry.audio_artifacts) for entry in entries),
            selected_date=selected,
            selected_entry=selected_entry,
            entries=entries,
        )

    def list_entries(self, days_back: int = 14, active_dates: set[date] | None = None) -> list[DayLibraryEntry]:
        normalized_days_back = max(1, days_back)
        today = self._clock.today_local()
        start = today - timedelta(days=normalized_days_back - 1)
        artifacts_by_date = self._scan_artifacts()
        runs_by_date = self._load_runs_by_date(date_from=start, date_to=today, limit=max(100, normalized_days_back * 12))
        active = active_dates or set()

        entries: list[DayLibraryEntry] = []
        for offset in range(normalized_days_back):
            day = today - timedelta(days=offset)
            buckets = artifacts_by_date.get(day, {})
            entries.append(
                self._build_entry(
                    date_ref=day,
                    runs=runs_by_date.get(day, []),
                    pdf_artifacts=list(buckets.get("pdf", [])),
                    audio_artifacts=list(buckets.get("audio", [])),
                    active_dates=active,
                )
            )
        return entries

    def get_entry(self, date_ref: date, active_dates: set[date] | None = None) -> DayLibraryEntry:
        artifacts_by_date = self._scan_artifacts()
        runs = self._load_runs(date_from=date_ref, date_to=date_ref, limit=30)
        buckets = artifacts_by_date.get(date_ref, {})
        return self._build_entry(
            date_ref=date_ref,
            runs=runs,
            pdf_artifacts=list(buckets.get("pdf", [])),
            audio_artifacts=list(buckets.get("audio", [])),
            active_dates=active_dates or set(),
        )

    def _scan_artifacts(self) -> dict[date, dict[str, list[LibraryArtifact]]]:
        grouped: dict[date, dict[str, list[LibraryArtifact]]] = {}
        self._scan_output_dir(self._pdf_output_dir, "pdf", grouped)
        self._scan_output_dir(self._audio_output_dir, "audio", grouped)
        return grouped

    def _scan_output_dir(
        self,
        output_dir: Path,
        artifact_type: str,
        grouped: dict[date, dict[str, list[LibraryArtifact]]],
    ) -> None:
        if not output_dir.exists():
            return

        def sort_key(path: Path) -> float:
            try:
                return path.stat().st_mtime
            except OSError:
                return 0.0

        for path in sorted(output_dir.glob("*"), key=sort_key, reverse=True):
            if not path.is_file():
                continue
            match = _DATE_PREFIX.match(path.stem)
            if match is None:
                continue
            try:
                date_ref = date.fromisoformat(match.group("date"))
            except ValueError:
                continue

            stat = path.stat()
            artifact = LibraryArtifact(
                artifact_type=artifact_type,
                filename=path.name,
                path=path.resolve(),
                size_bytes=stat.st_size,
                modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
            )
            grouped.setdefault(date_ref, {}).setdefault(artifact_type, []).append(artifact)

    def _load_runs_by_date(
        self,
        date_from: date | None,
        date_to: date | None,
        limit: int,
    ) -> dict[date, list[RunRecord]]:
        grouped: dict[date, list[RunRecord]] = {}
        for record in self._load_runs(date_from=date_from, date_to=date_to, limit=limit):
            grouped.setdefault(record.date_ref, []).append(record)
        return grouped

    def _load_runs(
        self,
        date_from: date | None,
        date_to: date | None,
        limit: int,
    ) -> list[RunRecord]:
        rows = self._state_store.list_runs(limit=limit, date_from=date_from, date_to=date_to)
        records = [self._row_to_run_record(row) for row in rows]
        records.sort(key=lambda item: item.started_at, reverse=True)
        return records

    def _row_to_run_record(self, row: dict[str, object]) -> RunRecord:
        started_at = self._parse_timestamp(row.get("started_at"))
        finished_at_raw = row.get("finished_at")
        finished_at = self._parse_timestamp(finished_at_raw) if finished_at_raw else None
        error_raw = row.get("error")
        return RunRecord(
            run_id=str(row.get("run_id", "")),
            date_ref=date.fromisoformat(str(row.get("date_ref"))),
            status=str(row.get("status", "unknown")),
            checkpoint=str(row.get("checkpoint", "started")),
            started_at=started_at,
            finished_at=finished_at,
            error=str(error_raw) if error_raw else None,
        )

    def _parse_timestamp(self, value: object) -> datetime:
        parsed = datetime.fromisoformat(str(value))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def _build_entry(
        self,
        date_ref: date,
        runs: list[RunRecord],
        pdf_artifacts: list[LibraryArtifact],
        audio_artifacts: list[LibraryArtifact],
        active_dates: set[date],
    ) -> DayLibraryEntry:
        latest_run = runs[0] if runs else None
        status = self._derive_status(
            date_ref=date_ref,
            latest_run=latest_run,
            pdf_artifacts=pdf_artifacts,
            audio_artifacts=audio_artifacts,
            active_dates=active_dates,
        )
        summary = self._build_summary(status, latest_run, pdf_artifacts, audio_artifacts)
        return DayLibraryEntry(
            date_ref=date_ref,
            status=status,
            summary=summary,
            pdf_artifacts=pdf_artifacts,
            audio_artifacts=audio_artifacts,
            latest_run=latest_run,
            run_history=runs[:6],
        )

    def _derive_status(
        self,
        date_ref: date,
        latest_run: RunRecord | None,
        pdf_artifacts: list[LibraryArtifact],
        audio_artifacts: list[LibraryArtifact],
        active_dates: set[date],
    ) -> str:
        if date_ref in active_dates:
            return "running"
        if latest_run is not None and latest_run.status == "running":
            return "running"
        if pdf_artifacts and audio_artifacts:
            return "ready"
        if pdf_artifacts or audio_artifacts:
            return "partial"
        if latest_run is not None and latest_run.status == "failed":
            return "failed"
        return "missing"

    def _build_summary(
        self,
        status: str,
        latest_run: RunRecord | None,
        pdf_artifacts: list[LibraryArtifact],
        audio_artifacts: list[LibraryArtifact],
    ) -> str:
        if status == "running":
            checkpoint = latest_run.checkpoint.replace("_", " ") if latest_run else "preparacao"
            return f"Pipeline em andamento: {checkpoint}."
        if status == "ready":
            return f"{len(pdf_artifacts)} PDF(s) e {len(audio_artifacts)} podcast(s) prontos para uso."
        if status == "partial":
            if pdf_artifacts and not audio_artifacts:
                return "PDF disponivel; o podcast ainda nao foi encontrado."
            if audio_artifacts and not pdf_artifacts:
                return "Podcast disponivel; o PDF ainda nao foi encontrado."
            return "Conteudo parcial disponivel para esta data."
        if status == "failed":
            checkpoint = latest_run.checkpoint.replace("_", " ") if latest_run else "pipeline"
            return f"A ultima execucao falhou durante {checkpoint}."
        return "Nenhum PDF ou podcast foi gerado para esta data ainda."
