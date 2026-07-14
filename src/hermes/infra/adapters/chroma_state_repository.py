from __future__ import annotations

import json
import logging
from typing import Any

import chromadb

from hermes.core.interfaces import StateRepositoryPort

logger = logging.getLogger(__name__)

_DUMMY_EMBEDDING = [[1.0]]


class ChromaStateRepository(StateRepositoryPort):
    JOBS_COLLECTION = "state_jobs"
    DIGESTS_COLLECTION = "state_digests"

    def __init__(self, client: chromadb.ClientAPI):
        self._jobs = client.get_or_create_collection(
            name=self.JOBS_COLLECTION,
            metadata={"description": "Pipeline job status per date"},
        )
        self._digests = client.get_or_create_collection(
            name=self.DIGESTS_COLLECTION,
            metadata={"description": "Digest content and metadata per date"},
        )
        logger.debug(
            "ChromaStateRepository initialized | jobs=%d digests=%d",
            self._jobs.count(),
            self._digests.count(),
        )

    def get_job(self, date_ref: str) -> dict[str, Any] | None:
        result = self._jobs.get(ids=[date_ref], include=["documents"])
        if result["ids"]:
            try:
                return json.loads(result["documents"][0])
            except (json.JSONDecodeError, IndexError):
                return None
        return None

    def save_job(self, date_ref: str, job: dict[str, Any]) -> None:
        self._jobs.upsert(
            ids=[date_ref],
            embeddings=_DUMMY_EMBEDDING,
            documents=[json.dumps(job, ensure_ascii=False)],
            metadatas=[{"date_ref": date_ref}],
        )

    def get_digest(self, date_ref: str) -> dict[str, Any] | None:
        result = self._digests.get(ids=[date_ref], include=["documents"])
        if result["ids"]:
            try:
                return json.loads(result["documents"][0])
            except (json.JSONDecodeError, IndexError):
                return None
        return None

    def save_digest(self, date_ref: str, digest: dict[str, Any]) -> None:
        self._digests.upsert(
            ids=[date_ref],
            embeddings=_DUMMY_EMBEDDING,
            documents=[json.dumps(digest, ensure_ascii=False)],
            metadatas=[{"date_ref": date_ref}],
        )
