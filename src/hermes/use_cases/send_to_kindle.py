from __future__ import annotations

from pathlib import Path
from typing import Optional

from hermes.core.interfaces import KindlePort, StateRepositoryPort


class SendToKindleUseCase:
    def __init__(self, kindle_port: KindlePort, state_repo: StateRepositoryPort):
        self.kindle_port = kindle_port
        self.state_repo = state_repo

    def execute(self, date_ref: str, kindle_email: Optional[str] = None) -> dict:
        if not self.kindle_port.is_configured():
            raise RuntimeError(
                "Configure SMTP e o remetente autorizado antes de usar o envio para Kindle."
            )

        digest = self.state_repo.get_digest(date_ref)
        if not digest:
            raise ValueError("Nenhum digest encontrado para a data informada.")

        pdf_artifact = (digest.get("pdfArtifacts") or [{}])[0]
        pdf_url = pdf_artifact.get("url", "")
        if not pdf_url:
            raise ValueError("Ainda não existe PDF gerado para esta data.")

        pdf_path = Path("data/pdf") / Path(pdf_url).name
        sent_to = self.kindle_port.send_pdf(
            date_ref=date_ref, pdf_path=pdf_path, kindle_email=kindle_email
        )

        digest["lastKindleEmail"] = sent_to
        digest["lastKindleStatus"] = "sent"
        self.state_repo.save_digest(date_ref, digest)

        return {
            "status": "sent",
            "dateRef": date_ref,
            "kindleEmail": sent_to,
        }
