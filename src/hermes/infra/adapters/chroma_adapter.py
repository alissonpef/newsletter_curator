from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta
from typing import Any

import chromadb
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction

from hermes.core.interfaces import VectorStorePort

logger = logging.getLogger(__name__)


class SearchResult:
    def __init__(
        self,
        doc_id: str,
        document: str,
        metadata: dict[str, Any],
        score: float,
    ):
        self.doc_id = doc_id
        self.document = document
        self.metadata = metadata
        self.score = score

    def to_dict(self) -> dict[str, Any]:
        date_ref = self.metadata.get("date_ref", "")
        result: dict[str, Any] = {
            "id": self.doc_id,
            "score": round(self.score, 4),
            "date_ref": date_ref,
            "snippet": self.document[:400].strip(),
            "dashboard_url": f"/?date={date_ref}" if date_ref else "/",
        }

        source_type = self.metadata.get("source_type", "digest")
        result["type"] = source_type

        if source_type == "newsletter":
            result["sender"] = self.metadata.get("sender", "")
            result["subject"] = self.metadata.get("subject", "")
        else:
            result["section"] = self.metadata.get("section", "")
            result["topic_title"] = self.metadata.get("topic_title", "")
            result["signal"] = self.metadata.get("signal", "")

        return result


def _make_newsletter_id(date_ref: str, sender: str, subject: str) -> str:
    raw = f"{date_ref}|{sender}|{subject}"
    return hashlib.sha256(raw.encode()).hexdigest()[:20]


def _make_digest_id(date_ref: str, section: str, index: int = 0) -> str:
    return f"{date_ref}:{section}:{index}"


def _truncate(text: str, max_chars: int = 1500) -> str:
    return text[:max_chars].strip() if text else ""


class ChromaAdapter(VectorStorePort):
    NEWSLETTER_COLLECTION = "newsletters"
    DIGEST_COLLECTION = "digests"

    def __init__(
        self,
        client: chromadb.ClientAPI,
        embedding_model: str = "mxbai-embed-large",
        ollama_url: str = "http://localhost:11434",
    ):
        self.embedding_model = embedding_model
        self.ollama_url = ollama_url.rstrip("/")

        self._embedding_fn = OllamaEmbeddingFunction(
            url=f"{self.ollama_url}/api/embeddings",
            model_name=embedding_model,
        )

        self._newsletters = client.get_or_create_collection(
            name=self.NEWSLETTER_COLLECTION,
            embedding_function=self._embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )
        self._digests = client.get_or_create_collection(
            name=self.DIGEST_COLLECTION,
            embedding_function=self._embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "ChromaAdapter ready | newsletters=%d digests=%d",
            self._newsletters.count(),
            self._digests.count(),
        )

    def index_newsletter(
        self,
        date_ref: str,
        sender: str,
        subject: str,
        content: str,
    ) -> None:
        doc_id = _make_newsletter_id(date_ref, sender, subject)
        document = _truncate(content, 1500)
        if not document:
            return

        metadata = {
            "date_ref": date_ref,
            "date_int": int(date_ref.replace("-", "")),
            "sender": sender,
            "subject": subject,
            "source_type": "newsletter",
            "indexed_at": datetime.utcnow().isoformat(),
        }

        self._newsletters.upsert(
            ids=[doc_id],
            documents=[document],
            metadatas=[metadata],
        )
        logger.debug("Indexed newsletter %s [%s · %s]", doc_id, date_ref, sender)

    def index_digest(self, date_ref: str, summary_data: dict[str, Any]) -> None:
        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict[str, Any]] = []

        base_meta: dict[str, Any] = {
            "date_ref": date_ref,
            "date_int": int(date_ref.replace("-", "")),
            "source_type": "digest",
            "indexed_at": datetime.utcnow().isoformat(),
        }

        thesis = summary_data.get("thesis", "").strip()
        if thesis:
            ids.append(_make_digest_id(date_ref, "thesis"))
            documents.append(_truncate(thesis))
            metadatas.append({**base_meta, "section": "thesis", "topic_title": "", "signal": ""})

        exec_summary = summary_data.get("executiveSummary", "").strip()
        if exec_summary:
            ids.append(_make_digest_id(date_ref, "executiveSummary"))
            documents.append(_truncate(exec_summary))
            metadatas.append(
                {
                    **base_meta,
                    "section": "executiveSummary",
                    "topic_title": "",
                    "signal": "",
                }
            )

        for idx, point in enumerate(summary_data.get("keyPoints", [])):
            point = (point or "").strip()
            if point:
                ids.append(_make_digest_id(date_ref, "keyPoint", idx))
                documents.append(_truncate(point, 800))
                metadatas.append(
                    {
                        **base_meta,
                        "section": "keyPoint",
                        "topic_title": "",
                        "signal": "",
                    }
                )

        for idx, topic in enumerate(summary_data.get("topics", [])):
            title = (topic.get("title") or "").strip()
            summary = (topic.get("summary") or "").strip()
            impact = (topic.get("impact") or "").strip()
            signal = topic.get("signal", "Média")

            text_parts = [p for p in [title, summary, impact] if p]
            full_text = " — ".join(text_parts)
            if not full_text:
                continue

            ids.append(_make_digest_id(date_ref, "topic", idx))
            documents.append(_truncate(full_text, 1200))
            metadatas.append(
                {
                    **base_meta,
                    "section": "topic",
                    "topic_title": title,
                    "signal": signal,
                }
            )

        closing = summary_data.get("closing", "").strip()
        if closing:
            ids.append(_make_digest_id(date_ref, "closing"))
            documents.append(_truncate(closing))
            metadatas.append({**base_meta, "section": "closing", "topic_title": "", "signal": ""})

        if not ids:
            logger.warning("No content to index for digest %s", date_ref)
            return

        self._digests.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )
        logger.info("Indexed digest %s (%d chunks)", date_ref, len(ids))

    def search(
        self,
        query: str,
        n_results: int = 20,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict[str, Any]]:
        where = self._build_date_filter(date_from, date_to)

        newsletter_results = self._query_collection(
            self._newsletters, query, n_results=max(5, n_results // 2), where=where
        )
        digest_results = self._query_collection(
            self._digests, query, n_results=n_results, where=where
        )

        merged = newsletter_results + digest_results
        merged.sort(key=lambda r: r.score, reverse=True)

        seen: set = set()
        unique: list[SearchResult] = []
        for r in merged:
            if r.doc_id not in seen:
                seen.add(r.doc_id)
                unique.append(r)

        return [r.to_dict() for r in unique[:n_results]]

    def search_newsletters(
        self,
        query: str,
        n_results: int = 10,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict[str, Any]]:
        where = self._build_date_filter(date_from, date_to)
        results = self._query_collection(self._newsletters, query, n_results=n_results, where=where)
        return [r.to_dict() for r in results]

    def search_digests(
        self,
        query: str,
        n_results: int = 10,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict[str, Any]]:
        where = self._build_date_filter(date_from, date_to)
        results = self._query_collection(self._digests, query, n_results=n_results, where=where)
        return [r.to_dict() for r in results]

    def get_topic_frequency(self, topic: str, days: int = 30) -> list[dict[str, Any]]:
        date_from = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        where = self._build_date_filter(date_from=date_from)
        try:
            digest_results = self._query_collection(self._digests, topic, n_results=50, where=where)
            newsletter_results = self._query_collection(
                self._newsletters, topic, n_results=30, where=where
            )
        except Exception as exc:
            logger.warning("get_topic_frequency failed: %s", exc)
            return []

        all_results = digest_results + newsletter_results

        by_date: dict[str, dict[str, Any]] = {}
        for r in all_results:
            d = r.metadata.get("date_ref", "")
            if not d:
                continue
            if d not in by_date:
                by_date[d] = {
                    "date_ref": d,
                    "count": 0,
                    "top_snippet": "",
                    "top_score": 0.0,
                }
            by_date[d]["count"] += 1
            if r.score > by_date[d]["top_score"]:
                by_date[d]["top_score"] = r.score
                by_date[d]["top_snippet"] = r.document[:200].strip()

        sorted_dates = sorted(by_date.values(), key=lambda x: x["date_ref"], reverse=True)
        for item in sorted_dates:
            item.pop("top_score", None)

        return sorted_dates

    def get_stats(self) -> dict[str, Any]:
        return {
            "newsletters_indexed": self._newsletters.count(),
            "digests_indexed": self._digests.count(),
            "embedding_model": self.embedding_model,
        }

    def _query_collection(
        self,
        collection,
        query: str,
        n_results: int,
        where: dict | None = None,
    ) -> list[SearchResult]:
        try:
            count = collection.count()
            if count == 0:
                return []

            actual_n = min(n_results, count)
            kwargs: dict[str, Any] = {
                "query_texts": [query],
                "n_results": actual_n,
                "include": ["documents", "metadatas", "distances"],
            }
            if where:
                kwargs["where"] = where

            response = collection.query(**kwargs)
        except Exception as exc:
            logger.warning("ChromaDB query failed on '%s': %s", collection.name, exc)
            return []

        results: list[SearchResult] = []
        ids = response.get("ids", [[]])[0]
        docs = response.get("documents", [[]])[0]
        metas = response.get("metadatas", [[]])[0]
        distances = response.get("distances", [[]])[0]

        for doc_id, document, metadata, distance in zip(ids, docs, metas, distances, strict=True):
            score = max(0.0, 1.0 - (distance / 2.0))
            results.append(
                SearchResult(
                    doc_id=doc_id,
                    document=document or "",
                    metadata=metadata or {},
                    score=score,
                )
            )

        return results

    @staticmethod
    def _build_date_filter(
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> dict | None:
        def _to_int(date_str: str) -> int:
            return int(date_str.replace("-", ""))

        conditions = []
        if date_from:
            conditions.append({"date_int": {"$gte": _to_int(date_from)}})
        if date_to:
            conditions.append({"date_int": {"$lte": _to_int(date_to)}})

        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}
