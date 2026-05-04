from __future__ import annotations

import asyncio
import os
from datetime import datetime
from typing import Dict, List

from hermes.core.interfaces import (
    AudioPort,
    EmailPort,
    LlmPort,
    MarketDataPort,
    PdfPort,
    StateRepositoryPort,
)


class ProcessDailyUseCase:
    def __init__(
        self,
        email_port: EmailPort,
        llm_port: LlmPort,
        pdf_port: PdfPort,
        audio_port: AudioPort,
        state_repo: StateRepositoryPort,
        market_data_port: MarketDataPort,
    ):
        self.email_port = email_port
        self.llm_port = llm_port
        self.pdf_port = pdf_port
        self.audio_port = audio_port
        self.state_repo = state_repo
        self.market_data_port = market_data_port

    def _new_digest(self, date_ref: str) -> Dict:
        return {
            "dateRef": date_ref,
            "dateLabel": date_ref,
            "status": "idle",
            "statusLabel": "Aguardando",
            "runHistory": [],
            "pdfArtifacts": [],
            "audioArtifacts": [],
            "warnings": [],
            "hasContent": False,
            "pdfCount": 0,
            "audioCount": 0,
        }

    def _record_history(
        self, digest: Dict, label: str, status: str, status_label: str
    ) -> None:
        digest.setdefault("runHistory", []).insert(
            0,
            {
                "status": status,
                "statusLabel": status_label,
                "checkpointLabel": label,
                "startedAtLabel": datetime.now().strftime("%H:%M:%S"),
            },
        )
        digest["runHistory"] = digest["runHistory"][:18]
        digest["status"] = status
        digest["statusLabel"] = status_label

    def _save_job(
        self,
        date_ref: str,
        *,
        status: str,
        status_label: str,
        message: str,
        progress_pct: int,
        current_step_key: str,
        current_step_label: str,
        warnings: List[str] | None = None,
        error: str | None = None,
    ) -> Dict:
        job = {
            "dateRef": date_ref,
            "status": status,
            "statusLabel": status_label,
            "message": message,
            "progressPct": progress_pct,
            "currentStepKey": current_step_key,
            "currentStepLabel": current_step_label,
            "warnings": warnings or [],
        }
        if error:
            job["error"] = error
        self.state_repo.save_job(date_ref, job)
        return job

    async def _run_blocking(self, func, *args, **kwargs):
        return await asyncio.to_thread(func, *args, **kwargs)

    async def execute(self, date_ref: str, force: bool = False):
        existing_job = self.state_repo.get_job(date_ref)
        if (
            existing_job
            and existing_job.get("status") in {"running", "queued"}
            and not force
        ):
            return

        digest = self.state_repo.get_digest(date_ref) or self._new_digest(date_ref)
        digest.setdefault("warnings", [])
        digest["warnings"] = []
        digest["status"] = "running"
        digest["statusLabel"] = "Processando"
        self.state_repo.save_digest(date_ref, digest)

        self._save_job(
            date_ref,
            status="running",
            status_label="Executando",
            message="Iniciando a preparação do digest.",
            progress_pct=2,
            current_step_key="bootstrap",
            current_step_label="Preparando execução",
        )

        try:
            self._record_history(
                digest, "Buscando newsletters do dia", "running", "Executando"
            )
            self.state_repo.save_digest(date_ref, digest)
            self._save_job(
                date_ref,
                status="running",
                status_label="Executando",
                message="Coletando newsletters da data selecionada.",
                progress_pct=10,
                current_step_key="ingest",
                current_step_label="Buscando newsletters",
            )

            emails = await self._run_blocking(self.email_port.fetch_emails, date_ref)
            if not emails:
                warning = "Nenhuma newsletter elegível foi encontrada para esta data."
                digest["hasContent"] = False
                digest["summary"] = ""
                digest["summaryData"] = None
                digest["pdfArtifacts"] = []
                digest["audioArtifacts"] = []
                digest["pdfCount"] = 0
                digest["audioCount"] = 0
                digest["warnings"] = [warning]
                self._record_history(
                    digest,
                    "Sem conteúdo disponível para a data",
                    "missing",
                    "Sem Conteúdo",
                )
                self.state_repo.save_digest(date_ref, digest)
                self._save_job(
                    date_ref,
                    status="succeeded",
                    status_label="Sem conteúdo",
                    message=warning,
                    progress_pct=100,
                    current_step_key="done",
                    current_step_label="Execução encerrada",
                    warnings=[warning],
                )
                return

            digest["sourceCount"] = len(emails)
            self._record_history(
                digest, "Consolidando a síntese com IA", "running", "Executando"
            )
            self.state_repo.save_digest(date_ref, digest)
            self._save_job(
                date_ref,
                status="running",
                status_label="Executando",
                message="Limpando ruídos e consolidando os principais sinais do dia.",
                progress_pct=42,
                current_step_key="synthesis",
                current_step_label="Consolidando a síntese",
            )

            summary_data = await self._run_blocking(
                self.llm_port.generate_summary, emails
            )
            digest["summaryData"] = summary_data
            digest["summary"] = summary_data.get("plainText", "")
            digest["hasContent"] = bool(digest["summary"])

            self._record_history(
                digest, "Atualizando o radar de mercado", "running", "Executando"
            )
            self.state_repo.save_digest(date_ref, digest)
            self._save_job(
                date_ref,
                status="running",
                status_label="Executando",
                message="Buscando os principais fechamentos e variações de mercado.",
                progress_pct=60,
                current_step_key="market",
                current_step_label="Atualizando o radar de mercado",
            )

            market_data = await self._run_blocking(
                self.market_data_port.fetch_market_data, date_ref
            )
            digest["marketData"] = market_data

            self._record_history(
                digest, "Renderizando o PDF editorial", "running", "Executando"
            )
            self.state_repo.save_digest(date_ref, digest)
            self._save_job(
                date_ref,
                status="running",
                status_label="Executando",
                message="Montando o PDF com o novo layout editorial.",
                progress_pct=78,
                current_step_key="pdf",
                current_step_label="Renderizando o PDF",
            )

            pdf_path = await self._run_blocking(
                self.pdf_port.render_pdf, date_ref, digest, market_data
            )
            if pdf_path:
                size = os.path.getsize(pdf_path)
                digest["pdfArtifacts"] = [
                    {
                        "url": f"/artifacts/pdf/{os.path.basename(pdf_path)}",
                        "sizeLabel": f"{max(1, size // 1024)} KB",
                    }
                ]
                digest["pdfCount"] = 1

            self._record_history(
                digest, "Gerando a versão em áudio", "running", "Executando"
            )
            self.state_repo.save_digest(date_ref, digest)
            self._save_job(
                date_ref,
                status="running",
                status_label="Executando",
                message="Convertendo o briefing em uma narração mais fluida.",
                progress_pct=92,
                current_step_key="audio",
                current_step_label="Gerando o áudio",
            )

            audio_text = summary_data.get("ttsScript") or digest.get("summary") or ""
            audio_path = await self.audio_port.generate_audio(date_ref, audio_text)
            if audio_path:
                size = os.path.getsize(audio_path)
                digest["audioArtifacts"] = [
                    {
                        "url": f"/artifacts/audio/{os.path.basename(audio_path)}",
                        "sizeLabel": f"{max(1, size // 1024)} KB",
                    }
                ]
                digest["audioCount"] = 1

            digest["processedAtLabel"] = datetime.now().strftime("%d/%m/%Y %H:%M")
            self._record_history(
                digest, "Digest finalizado com sucesso", "ready", "Pronto"
            )
            self.state_repo.save_digest(date_ref, digest)
            self._save_job(
                date_ref,
                status="succeeded",
                status_label="Pronto",
                message="Digest, PDF e áudio atualizados com sucesso.",
                progress_pct=100,
                current_step_key="done",
                current_step_label="Digest pronto",
            )
        except Exception as exc:
            error_message = str(exc)
            digest.setdefault("warnings", []).append(
                "A última tentativa terminou com erro."
            )
            self._record_history(
                digest, f"Falha na execução: {error_message}", "failed", "Erro"
            )
            self.state_repo.save_digest(date_ref, digest)
            self._save_job(
                date_ref,
                status="failed",
                status_label="Erro",
                message="A execução falhou antes de concluir o digest.",
                progress_pct=100,
                current_step_key="failed",
                current_step_label="Execução interrompida",
                warnings=digest.get("warnings", []),
                error=error_message,
            )
            raise
