from __future__ import annotations

from ...core.entities import MarketSnapshotItem
from ...ports.market_data_port import MarketDataPort


class BuildMarketSnapshotUseCase:
    def __init__(self, market_data_port: MarketDataPort, logger) -> None:
        self._market_data_port = market_data_port
        self._logger = logger

    def execute(self, run_id: str) -> list[MarketSnapshotItem]:
        snapshot = self._market_data_port.fetch_snapshot()
        self._logger.info(
            "built market snapshot",
            extra={"run_id": run_id, "count": len(snapshot)},
        )
        return snapshot
