from datetime import date

from ...app.runtime_config import IndexEmbeddingsConfig
from ...core.entities import EmailItem, ChunkItem
from ...core.policies import resolve_namespace
from ...ports.embedding_port import EmbeddingPort
from ...ports.vector_store_port import VectorStorePort


class IndexEmbeddingsUseCase:
    def __init__(
        self,
        chunking_service,
        embedding_port: EmbeddingPort,
        vector_store: VectorStorePort,
        logger,
        config: IndexEmbeddingsConfig,
    ) -> None:
        self._chunking_service = chunking_service
        self._embedding_port = embedding_port
        self._vector_store = vector_store
        self._logger = logger
        self._config = config

    def execute(self, run_id: str, date_ref: date, emails: list[EmailItem]) -> list[ChunkItem]:
        chunks: list[ChunkItem] = []
        for email in emails:
            chunks.extend(self._chunking_service.chunk_email(email))

        if not chunks:
            self._logger.info("no chunks generated", extra={"run_id": run_id})
            return []

        documents = [chunk.chunk_text for chunk in chunks]
        embeddings = self._embedding_port.embed_texts(model=self._config.embed_model, inputs=documents)

        if len(embeddings) != len(chunks):
            raise RuntimeError("embedding count does not match chunk count")

        metadatas = [
            {
                "run_id": run_id,
                "date_ref": date_ref.isoformat(),
                "namespace": resolve_namespace(date_ref),
                "email_id": chunk.email_id,
                "chunk_index": chunk.chunk_index,
            }
            for chunk in chunks
        ]
        self._vector_store.upsert_chunks(
            collection=self._config.chunks_collection,
            ids=[chunk.id for chunk in chunks],
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        self._logger.info(
            "indexed embeddings",
            extra={"run_id": run_id, "chunks": len(chunks), "collection": self._config.chunks_collection},
        )
        return chunks
