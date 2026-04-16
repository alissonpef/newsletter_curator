from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from ...core.errors import MarketDataUnavailableError
from ...core.entities import MarketSnapshotItem
from ...infra.retries import io_retry
from ...ports.market_data_port import MarketDataPort


class YahooMarketClient(MarketDataPort):
    _TRACKED_SYMBOLS: tuple[tuple[str, str], ...] = (
        ("IBOVESPA", "^BVSP"),
        ("S&P 500", "^GSPC"),
        ("NASDAQ", "^IXIC"),
        ("DOW JONES", "^DJI"),
        ("BITCOIN", "BTC-USD"),
        ("ETHEREUM", "ETH-USD"),
        ("USD/BRL", "USDBRL=X"),
        ("PETROLEO BRENT", "BZ=F"),
        ("OURO", "GC=F"),
        ("VIX", "^VIX"),
    )

    def __init__(self, timeout_seconds: float = 12.0) -> None:
        self._timeout_seconds = timeout_seconds

    def _build_url(self) -> str:
        symbols = ",".join(symbol for _, symbol in self._TRACKED_SYMBOLS)
        query = urlencode(
            {
                "symbols": symbols,
                "range": "5d",
                "interval": "1d",
            }
        )
        return f"https://query1.finance.yahoo.com/v7/finance/spark?{query}"

    def _compute_change_pct(self, closes: list[float], current_price: float, fallback_previous: float | None) -> float | None:
        if len(closes) >= 2:
            previous = closes[-2]
        else:
            previous = fallback_previous

        if previous in (None, 0):
            return None

        return ((current_price - previous) / previous) * 100

    def fetch_snapshot(self) -> list[MarketSnapshotItem]:
        request = Request(
            self._build_url(),
            headers={"User-Agent": "Mozilla/5.0"},
        )

        try:
            payload = self._fetch_payload(request)
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError) as exc:
            raise MarketDataUnavailableError("failed to fetch market snapshot") from exc

        symbol_order = {symbol: index for index, (_, symbol) in enumerate(self._TRACKED_SYMBOLS)}
        labels = {symbol: label for label, symbol in self._TRACKED_SYMBOLS}

        items: list[MarketSnapshotItem] = []
        for result in payload.get("spark", {}).get("result", []):
            symbol = str(result.get("symbol", "")).strip()
            if not symbol:
                continue

            response_items = result.get("response") or []
            if not response_items:
                continue

            snapshot = response_items[0]
            meta = snapshot.get("meta") or {}
            quote_items = (snapshot.get("indicators") or {}).get("quote") or []
            closes_raw = quote_items[0].get("close", []) if quote_items else []
            closes = [float(value) for value in closes_raw if isinstance(value, (int, float))]

            market_price = meta.get("regularMarketPrice")
            if isinstance(market_price, (int, float)):
                price = float(market_price)
            elif closes:
                price = closes[-1]
            else:
                continue

            fallback_previous = meta.get("chartPreviousClose")
            if not isinstance(fallback_previous, (int, float)):
                fallback_previous = meta.get("previousClose")
            prev_value = float(fallback_previous) if isinstance(fallback_previous, (int, float)) else None
            change_pct = self._compute_change_pct(closes=closes, current_price=price, fallback_previous=prev_value)

            regular_market_time = meta.get("regularMarketTime")
            if isinstance(regular_market_time, (int, float)):
                as_of = datetime.fromtimestamp(float(regular_market_time), tz=timezone.utc)
            else:
                as_of = datetime.now(timezone.utc)

            currency = str(meta.get("currency", "")).strip().upper()
            label = labels.get(symbol, symbol)

            items.append(
                MarketSnapshotItem(
                    label=label,
                    symbol=symbol,
                    price=price,
                    change_pct=change_pct,
                    currency=currency,
                    as_of=as_of,
                )
            )

        items.sort(key=lambda item: symbol_order.get(item.symbol, 999))
        return items

    @io_retry()
    def _fetch_payload(self, request: Request) -> dict[str, object]:
        with urlopen(request, timeout=self._timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
