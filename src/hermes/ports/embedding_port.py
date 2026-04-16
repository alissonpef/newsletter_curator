from typing import Protocol


class EmbeddingPort(Protocol):
    def embed_texts(self, model: str, inputs: list[str]) -> list[list[float]]: ...
