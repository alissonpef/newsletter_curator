from pathlib import Path
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod


class EmailPort(ABC):
    @abstractmethod
    def fetch_emails(self, date_ref: str) -> List[Dict[str, str]]:
        pass


class LlmPort(ABC):
    @abstractmethod
    def generate_summary(self, newsletters: List[Dict[str, str]]) -> Dict[str, Any]:
        pass


class PdfPort(ABC):
    @abstractmethod
    def render_pdf(
        self, date_ref: str, digest: Dict[str, Any], market_data: Dict[str, Any]
    ) -> str:
        pass


class AudioPort(ABC):
    @abstractmethod
    async def generate_audio(self, date_ref: str, text: str) -> str:
        pass


class KindlePort(ABC):
    @abstractmethod
    def is_configured(self) -> bool:
        pass

    @abstractmethod
    def send_pdf(
        self,
        date_ref: str,
        pdf_path: Path,
        kindle_email: Optional[str] = None,
    ) -> str:
        pass


class MarketDataPort(ABC):
    @abstractmethod
    def fetch_market_data(
        self, date_ref: Optional[str] = None
    ) -> Dict[str, Dict[str, str]]:
        pass


class StateRepositoryPort(ABC):
    @abstractmethod
    def get_job(self, date_ref: str) -> dict:
        pass

    @abstractmethod
    def save_job(self, date_ref: str, job: dict):
        pass

    @abstractmethod
    def get_digest(self, date_ref: str) -> dict:
        pass

    @abstractmethod
    def save_digest(self, date_ref: str, digest: dict):
        pass
