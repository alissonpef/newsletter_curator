from __future__ import annotations

from typing import Any

import chromadb


class ChromaRepository:
    def __init__(self, persist_path: str) -> None:
        self._client = chromadb.PersistentClient(path=persist_path)

    def upsert_chunks(
        self,
        collection: str,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
    ) -> None:
        coll = self._client.get_or_create_collection(collection)
        coll.upsert(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)

    def query_similar(
        self,
        collection: str,
        query_embeddings: list[list[float]],
        n_results: int,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        coll = self._client.get_or_create_collection(collection)
        result = coll.query(query_embeddings=query_embeddings, n_results=n_results, where=where)

        ids = result.get("ids", [])
        documents = result.get("documents", [])
        metadatas = result.get("metadatas", [])
        distances = result.get("distances", [])

        flattened: list[dict[str, Any]] = []
        for idx in range(len(ids)):
            row_ids = ids[idx] if idx < len(ids) else []
            row_docs = documents[idx] if idx < len(documents) else []
            row_meta = metadatas[idx] if idx < len(metadatas) else []
            row_distances = distances[idx] if idx < len(distances) else []

            for row_idx, chunk_id in enumerate(row_ids):
                distance = row_distances[row_idx] if row_idx < len(row_distances) else 0.0
                score = float(max(0.0, 1.0 - float(distance)))
                flattened.append(
                    {
                        "chunk_id": chunk_id,
                        "score": score,
                        "text": row_docs[row_idx] if row_idx < len(row_docs) else "",
                        "metadata": row_meta[row_idx] if row_idx < len(row_meta) else {},
                    }
                )

        return flattened

    def upsert_digest(
        self,
        collection: str,
        digest_id: str,
        digest_text: str,
        metadata: dict[str, Any],
    ) -> None:
        coll = self._client.get_or_create_collection(collection)
        coll.upsert(ids=[digest_id], documents=[digest_text], metadatas=[metadata])
