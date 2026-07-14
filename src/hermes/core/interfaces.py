from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class EmailPort(ABC):
    @abstractmethod
    def fetch_emails(self, date_ref: str) -> list[dict[str, str]]:
        pass


class LlmPort(ABC):
    @abstractmethod
    def generate_summary(self, newsletters: list[dict[str, str]]) -> dict[str, Any]:
        pass


class PdfPort(ABC):
    @abstractmethod
    def render_pdf(self, date_ref: str, digest: dict[str, Any], market_data: dict[str, Any]) -> str:
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
        kindle_email: str | None = None,
    ) -> str:
        pass


class MarketDataPort(ABC):
    @abstractmethod
    def fetch_market_data(self, date_ref: str | None = None) -> dict[str, dict[str, str]]:
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


class VectorStorePort(ABC):
    @abstractmethod
    def index_newsletter(self, date_ref: str, sender: str, subject: str, content: str) -> None:
        pass

    @abstractmethod
    def index_digest(self, date_ref: str, summary_data: dict[str, Any]) -> None:
        pass

    @abstractmethod
    def search(
        self,
        query: str,
        n_results: int = 20,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def get_topic_frequency(self, topic: str, days: int = 30) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def get_stats(self) -> dict[str, Any]:
        pass
