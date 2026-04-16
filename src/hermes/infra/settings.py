from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .runtime_paths import RuntimePathProvider


class ImapSettings(BaseModel):
    host: str
    port: int = 993
    username: str
    password: str
    use_ssl: bool = True
    mailbox: str = "INBOX"
    search_strategy: str = "UID"
    since_hours_back: int | None = None

    @field_validator("host", "username", "password", "mailbox", "search_strategy")
    @classmethod
    def validate_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("imap setting cannot be empty")
        return value


class SmtpSettings(BaseModel):
    host: str
    port: int = 465
    username: str
    password: str
    use_ssl: bool = True
    kindle_address: str

    @field_validator("host", "username", "password", "kindle_address")
    @classmethod
    def validate_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("smtp setting cannot be empty")
        return value


class OllamaSettings(BaseModel):
    base_url: str = "http://localhost:11434"
    chat_model: str = "qwen3.5:9b"
    embed_model: str = "nomic-embed-text"
    timeout_seconds: float = 60.0


class ChromaSettings(BaseModel):
    persist_path: Path
    chunks_collection: str = "newsletter_chunks"
    digests_collection: str = "daily_digests"
    topic_memory_collection: str = "topic_memory"


class PdfSettings(BaseModel):
    template_name: str = "newsletter.html.j2"
    output_dir: Path


class TtsSettings(BaseModel):
    piper_executable: str = "piper"
    model_path: Path
    sample_rate: int = 22050
    output_dir: Path


class PipelineSettings(BaseModel):
    chunk_size: int = 800
    chunk_overlap: int = 120
    negative_keywords: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    replay_days_back: int = 7
    allowed_senders: list[str] = Field(default_factory=list)


class WebSettings(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8787
    default_days_back: int = 14


class PromptSettings(BaseModel):
    consolidate_topics_path: Path
    editorial_style_path: Path
    podcast_script_path: Path


class AppSettings(BaseModel):
    project_root: Path
    app_config_path: Path
    logging_config_path: Path
    state_sqlite_path: Path
    state_checkpoints_path: Path
    imap: ImapSettings
    smtp: SmtpSettings
    ollama: OllamaSettings
    chroma: ChromaSettings
    pdf: PdfSettings
    tts: TtsSettings
    pipeline: PipelineSettings
    web: WebSettings
    prompts: PromptSettings


class _EnvSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    IMAP_HOST: str
    IMAP_PORT: int = 993
    IMAP_USERNAME: str
    IMAP_PASSWORD: str
    IMAP_USE_SSL: bool = True
    IMAP_MAILBOX: str = "INBOX"
    IMAP_SEARCH_STRATEGY: str = "UID"

    SMTP_HOST: str
    SMTP_PORT: int = 465
    SMTP_USERNAME: str
    SMTP_PASSWORD: str
    SMTP_USE_SSL: bool = True
    KINDLE_ADDRESS: str

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_CHAT_MODEL: str = "qwen3.5:9b"
    OLLAMA_EMBED_MODEL: str = "nomic-embed-text"
    OLLAMA_TIMEOUT_SECONDS: float = 60.0

    CHROMA_PERSIST_PATH: str = "data/vector_store"
    CHROMA_CHUNKS_COLLECTION: str = "newsletter_chunks"
    CHROMA_DIGESTS_COLLECTION: str = "daily_digests"
    CHROMA_TOPIC_MEMORY_COLLECTION: str = "topic_memory"

    PIPER_EXECUTABLE: str = "piper"
    PIPER_MODEL_PATH: str = "models/pt_BR-voice.onnx"
    PIPER_SAMPLE_RATE: int = 22050

    PROJECT_ROOT: str = "."
    LOGGING_CONFIG_PATH: str = "config/logging.yaml"
    APP_CONFIG_PATH: str = "config/app.yaml"
    STATE_SQLITE_PATH: str = "data/state/processed_ids.sqlite"
    STATE_CHECKPOINTS_PATH: str = "data/state/checkpoints.json"
    NEWSLETTER_ALLOWED_SENDERS: str = ""
    WEB_HOST: str = "127.0.0.1"
    WEB_PORT: int = 8787
    WEB_DEFAULT_DAYS_BACK: int = 14


def _resolve_path(project_root: Path, value: str | Path) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    return project_root / candidate


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as stream:
        content = yaml.safe_load(stream) or {}
        if not isinstance(content, dict):
            raise ValueError("app.yaml must contain a mapping at root")
        return content


def _normalize_string_list(values: Any) -> list[str]:
    if values is None:
        return []

    raw_items: list[str]
    if isinstance(values, str):
        raw_items = re.split(r"[,;\n]", values)
    elif isinstance(values, list):
        raw_items = [str(item) for item in values]
    else:
        return []

    normalized: list[str] = []
    for item in raw_items:
        candidate = item.strip().lower()
        if candidate:
            normalized.append(candidate)
    return normalized


def load_settings(env_file: Path | str = ".env") -> AppSettings:
    env = _EnvSettings(_env_file=env_file)
    project_root = Path(env.PROJECT_ROOT).resolve()

    app_config_path = _resolve_path(project_root, env.APP_CONFIG_PATH)
    yaml_config = _load_yaml(app_config_path)

    imap_cfg = yaml_config.get("imap", {})
    pipeline_cfg = yaml_config.get("pipeline", {})
    vector_cfg = yaml_config.get("vector_store", {})
    pdf_cfg = yaml_config.get("pdf", {})
    tts_cfg = yaml_config.get("tts", {})
    web_cfg = yaml_config.get("web", {})
    prompts_cfg = yaml_config.get("prompts", {})
    env_allowed_senders = _normalize_string_list(env.NEWSLETTER_ALLOWED_SENDERS)
    yaml_allowed_senders = _normalize_string_list(pipeline_cfg.get("allowed_senders"))

    settings = AppSettings(
        project_root=project_root,
        app_config_path=app_config_path,
        logging_config_path=_resolve_path(project_root, env.LOGGING_CONFIG_PATH),
        state_sqlite_path=_resolve_path(project_root, env.STATE_SQLITE_PATH),
        state_checkpoints_path=_resolve_path(project_root, env.STATE_CHECKPOINTS_PATH),
        imap=ImapSettings(
            host=env.IMAP_HOST,
            port=env.IMAP_PORT,
            username=env.IMAP_USERNAME,
            password=env.IMAP_PASSWORD,
            use_ssl=env.IMAP_USE_SSL,
            mailbox=imap_cfg.get("mailbox", env.IMAP_MAILBOX),
            search_strategy=imap_cfg.get("search_strategy", env.IMAP_SEARCH_STRATEGY),
            since_hours_back=imap_cfg.get("since_hours_back"),
        ),
        smtp=SmtpSettings(
            host=env.SMTP_HOST,
            port=env.SMTP_PORT,
            username=env.SMTP_USERNAME,
            password=env.SMTP_PASSWORD,
            use_ssl=env.SMTP_USE_SSL,
            kindle_address=env.KINDLE_ADDRESS,
        ),
        ollama=OllamaSettings(
            base_url=env.OLLAMA_BASE_URL,
            chat_model=env.OLLAMA_CHAT_MODEL,
            embed_model=env.OLLAMA_EMBED_MODEL,
            timeout_seconds=env.OLLAMA_TIMEOUT_SECONDS,
        ),
        chroma=ChromaSettings(
            persist_path=_resolve_path(project_root, env.CHROMA_PERSIST_PATH),
            chunks_collection=vector_cfg.get("chunks_collection", env.CHROMA_CHUNKS_COLLECTION),
            digests_collection=vector_cfg.get("digests_collection", env.CHROMA_DIGESTS_COLLECTION),
            topic_memory_collection=vector_cfg.get(
                "topic_memory_collection", env.CHROMA_TOPIC_MEMORY_COLLECTION
            ),
        ),
        pdf=PdfSettings(
            template_name=pdf_cfg.get("template_name", "newsletter.html.j2"),
            output_dir=_resolve_path(project_root, pdf_cfg.get("output_dir", "data/outputs/pdf")),
        ),
        tts=TtsSettings(
            piper_executable=env.PIPER_EXECUTABLE,
            model_path=_resolve_path(project_root, env.PIPER_MODEL_PATH),
            sample_rate=env.PIPER_SAMPLE_RATE,
            output_dir=_resolve_path(project_root, tts_cfg.get("output_dir", "data/outputs/audio")),
        ),
        pipeline=PipelineSettings(
            chunk_size=int(pipeline_cfg.get("chunk_size", 800)),
            chunk_overlap=int(pipeline_cfg.get("chunk_overlap", 120)),
            negative_keywords=list(pipeline_cfg.get("negative_keywords", [])),
            topics=list(pipeline_cfg.get("topics", [])),
            replay_days_back=int(pipeline_cfg.get("replay_days_back", 7)),
            allowed_senders=env_allowed_senders if env_allowed_senders else yaml_allowed_senders,
        ),
        web=WebSettings(
            host=str(web_cfg.get("host", env.WEB_HOST)).strip(),
            port=int(web_cfg.get("port", env.WEB_PORT)),
            default_days_back=int(web_cfg.get("default_days_back", env.WEB_DEFAULT_DAYS_BACK)),
        ),
        prompts=PromptSettings(
            consolidate_topics_path=_resolve_path(
                project_root,
                prompts_cfg.get("consolidate_topics", "config/prompts/consolidate_topics.md"),
            ),
            editorial_style_path=_resolve_path(
                project_root,
                prompts_cfg.get("editorial_style", "config/prompts/editorial_style.md"),
            ),
            podcast_script_path=_resolve_path(
                project_root,
                prompts_cfg.get("podcast_script", "config/prompts/podcast_script.md"),
            ),
        ),
    )

    RuntimePathProvider(project_root).ensure_runtime_dirs(
        state_sqlite_path=settings.state_sqlite_path,
        state_checkpoints_path=settings.state_checkpoints_path,
        vector_persist_path=settings.chroma.persist_path,
        pdf_output_dir=settings.pdf.output_dir,
        audio_output_dir=settings.tts.output_dir,
    )

    return settings
