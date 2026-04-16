from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True, frozen=True)
class IndexEmbeddingsConfig:
    embed_model: str = "nomic-embed-text"
    chunks_collection: str = "newsletter_chunks"


@dataclass(slots=True, frozen=True)
class CurateDailyDigestConfig:
    embed_model: str = "nomic-embed-text"
    chat_model: str = "qwen3.5:9b"
    chunks_collection: str = "newsletter_chunks"
    digests_collection: str = "daily_digests"
    topic_memory_collection: str = "topic_memory"
    consolidate_prompt: str = (
        "Voce e um editor tecnico. Recebera trechos de newsletters e deve consolidar os principais temas do dia."
    )
    editorial_style_prompt: str = "Estilo editorial objetivo e direto."


@dataclass(slots=True, frozen=True)
class RenderPdfConfig:
    template_name: str = "newsletter.html.j2"
    output_dir: Path = Path("data/outputs/pdf")


@dataclass(slots=True, frozen=True)
class PodcastSynthesisConfig:
    chat_model: str = "qwen3.5:9b"
    output_dir: Path = Path("data/outputs/audio")
    script_prompt: str = (
        "Gere um roteiro de podcast curto em portugues brasileiro, com abertura acolhedora, "
        "linguagem natural, transicoes suaves e encerramento humano."
    )


@dataclass(slots=True, frozen=True)
class PipelineRuntimeConfig:
    mailbox: str = "INBOX"
    search_strategy: str = "UID"
    since_hours_back: int | None = None
    negative_keywords: tuple[str, ...] = field(default_factory=tuple)
    allowed_senders: tuple[str, ...] = field(default_factory=tuple)
    topics: tuple[str, ...] = field(default_factory=tuple)
    kindle_address: str = ""
    send_kindle: bool = True
    generate_podcast: bool = True
