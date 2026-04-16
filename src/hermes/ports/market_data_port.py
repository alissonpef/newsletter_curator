from __future__ import annotations

from typing import Protocol

from ..core.entities import MarketSnapshotItem


class MarketDataPort(Protocol):
    def fetch_snapshot(self) -> list[MarketSnapshotItem]: ...
