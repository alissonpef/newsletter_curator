from typing import Any, Protocol


class VectorStorePort(Protocol):
    def upsert_chunks(
        self,
        collection: str,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
    ) -> None: ...

    def query_similar(
        self,
        collection: str,
        query_embeddings: list[list[float]],
        n_results: int,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]: ...

    def upsert_digest(
        self,
        collection: str,
        digest_id: str,
        digest_text: str,
        metadata: dict[str, Any],
    ) -> None: ...
