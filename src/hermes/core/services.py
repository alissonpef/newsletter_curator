import re

from .entities import EmailItem, ChunkItem
from .policies import estimate_tokens


class NormalizationService:
    def normalize_email_text(self, raw_text: str) -> str:
        text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
        lines = []

        for line in text.split("\n"):
            stripped = line.strip()
            if stripped.startswith(">"):
                continue
            if stripped.lower().startswith("on ") and " wrote:" in stripped.lower():
                continue
            lines.append(line)

        normalized = "\n".join(lines)
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)
        return normalized.strip()


class LinkExtractionService:
    _URL_PATTERN = re.compile(r"https?://[^\s<>\"]+", flags=re.IGNORECASE)

    def extract_links(self, text: str) -> list[str]:
        links = self._URL_PATTERN.findall(text)
        # Keep insertion order while removing duplicates.
        return list(dict.fromkeys(links))


class ChunkingService:
    def __init__(self, chunk_size: int, overlap: int) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be greater than zero")
        if overlap < 0:
            raise ValueError("overlap must be non-negative")
        if overlap >= chunk_size:
            raise ValueError("overlap must be smaller than chunk_size")

        self._chunk_size = chunk_size
        self._overlap = overlap

    def chunk_email(self, email: EmailItem) -> list[ChunkItem]:
        words = email.body_text.split()
        if not words:
            return []

        step = max(1, self._chunk_size - self._overlap)
        chunks: list[ChunkItem] = []
        chunk_index = 0

        for start in range(0, len(words), step):
            chunk_words = words[start : start + self._chunk_size]
            if not chunk_words:
                continue

            chunk_text = " ".join(chunk_words).strip()
            chunk_id = f"{email.id}:{chunk_index}"
            chunks.append(
                ChunkItem(
                    id=chunk_id,
                    email_id=email.id,
                    chunk_index=chunk_index,
                    chunk_text=chunk_text,
                    tokens_est=estimate_tokens(chunk_text),
                )
            )

            chunk_index += 1
            if start + self._chunk_size >= len(words):
                break

        return chunks
