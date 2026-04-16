from __future__ import annotations

from datetime import datetime, timezone

from hermes.app.use_cases.build_market_snapshot import BuildMarketSnapshotUseCase
from hermes.core.entities import MarketSnapshotItem


class DummyLogger:
    def info(self, *args, **kwargs):
        return None


class FakeMarketPort:
    def fetch_snapshot(self):
        return [
            MarketSnapshotItem(
                label="IBOVESPA",
                symbol="^BVSP",
                price=197500.0,
                change_pct=0.41,
                currency="BRL",
                as_of=datetime(2026, 4, 15, 18, 0, tzinfo=timezone.utc),
            )
        ]


def test_build_market_snapshot_use_case_returns_items() -> None:
    use_case = BuildMarketSnapshotUseCase(market_data_port=FakeMarketPort(), logger=DummyLogger())

    snapshot = use_case.execute(run_id="run-1")

    assert len(snapshot) == 1
    assert snapshot[0].label == "IBOVESPA"
    assert snapshot[0].symbol == "^BVSP"
