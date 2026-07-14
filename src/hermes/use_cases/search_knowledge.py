from __future__ import annotations

from datetime import datetime
from typing import Any

from hermes.core.interfaces import VectorStorePort


class SearchKnowledgeUseCase:
    def __init__(self, vector_store: VectorStorePort):
        self.vector_store = vector_store

    def execute(
        self,
        query: str,
        n_results: int = 20,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> dict[str, Any]:
        query = (query or "").strip()
        if not query:
            return {
                "query": query,
                "total": 0,
                "results": [],
                "date_from": date_from,
                "date_to": date_to,
            }

        raw_results = self.vector_store.search(
            query,
            n_results=n_results,
            date_from=date_from,
            date_to=date_to,
        )

        for result in raw_results:
            result["date_label"] = self._format_date_label(result.get("date_ref", ""))

        return {
            "query": query,
            "total": len(raw_results),
            "results": raw_results,
            "date_from": date_from,
            "date_to": date_to,
        }

    def get_topic_timeline(
        self,
        topic: str,
        days: int = 30,
    ) -> dict[str, Any]:
        topic = (topic or "").strip()
        if not topic:
            return {"query": topic, "days": days, "total_occurrences": 0, "by_date": []}

        occurrences = self.vector_store.get_topic_frequency(topic, days=days)
        total = sum(item.get("count", 0) for item in occurrences)

        for item in occurrences:
            item["date_label"] = self._format_date_label(item.get("date_ref", ""))

        return {
            "query": topic,
            "days": days,
            "total_occurrences": total,
            "by_date": occurrences,
        }

    def get_vector_stats(self) -> dict[str, Any]:
        return self.vector_store.get_stats()

    _PT_WEEKDAYS = [
        "segunda",
        "terça",
        "quarta",
        "quinta",
        "sexta",
        "sábado",
        "domingo",
    ]
    _PT_MONTHS = [
        "janeiro",
        "fevereiro",
        "março",
        "abril",
        "maio",
        "junho",
        "julho",
        "agosto",
        "setembro",
        "outubro",
        "novembro",
        "dezembro",
    ]

    def _format_date_label(self, date_ref: str) -> str:
        try:
            day = datetime.strptime(date_ref, "%Y-%m-%d")
            weekday = self._PT_WEEKDAYS[day.weekday()]
            month = self._PT_MONTHS[day.month - 1]
            return f"{weekday}, {day.day} de {month}"
        except (ValueError, IndexError):
            return date_ref
