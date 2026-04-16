from dataclasses import dataclass, field
from datetime import datetime, date
from pathlib import Path
from typing import Literal


@dataclass(slots=True, frozen=True)
class EmailItem:
    id: str
    message_id: str
    uid: str
    sender: str
    subject: str
    received_at: datetime
    body_text: str
    links: list[str]


@dataclass(slots=True, frozen=True)
class ChunkItem:
    id: str
    email_id: str
    chunk_index: int
    chunk_text: str
    tokens_est: int


@dataclass(slots=True, frozen=True)
class MarketSnapshotItem:
    label: str
    symbol: str
    price: float
    change_pct: float | None
    currency: str
    as_of: datetime


@dataclass(slots=True, frozen=True)
class DailyDigest:
    run_id: str
    date_ref: date
    themes: list[str]
    highlights: list[str]
    sources: list[str]
    final_text: str
    market_snapshot: list[MarketSnapshotItem] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class MediaArtifact:
    run_id: str
    type: Literal["pdf", "audio"]
    path: Path
    checksum: str


@dataclass(slots=True, frozen=True)
class RunState:
    run_id: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    checkpoint: str
