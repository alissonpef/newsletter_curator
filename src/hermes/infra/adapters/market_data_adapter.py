from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict

import yfinance as yf

from hermes.core.interfaces import MarketDataPort


class YFinanceMarketDataAdapter(MarketDataPort):
    def _format_value(self, ticker: str, current: float) -> str:
        if ticker == "^BVSP":
            return f"{current:,.0f}".replace(",", ".")
        if ticker == "BRL=X":
            return f"R$ {current:.2f}".replace(".", ",")
        return f"$ {current:,.2f}"

    def _history_for_date(self, ticker: str, date_ref: str | None):
        ticker_obj = yf.Ticker(ticker)

        if not date_ref:
            history = ticker_obj.history(period="5d")
            if len(history) < 2:
                raise ValueError("insufficient market history")
            return history.sort_index().tail(2)

        target_date = datetime.strptime(date_ref, "%Y-%m-%d").date()
        start_date = (target_date - timedelta(days=14)).isoformat()
        end_date = (target_date + timedelta(days=2)).isoformat()
        history = ticker_obj.history(start=start_date, end=end_date)
        if history.empty:
            raise ValueError("insufficient market history")

        history = history.sort_index().dropna(subset=["Close"])
        up_to_target = history[history.index.date <= target_date]
        if len(up_to_target) >= 2:
            return up_to_target.tail(2)

        if len(history) >= 2:
            return history.tail(2)

        raise ValueError("insufficient market history")

    def fetch_market_data(
        self, date_ref: str | None = None
    ) -> Dict[str, Dict[str, str]]:
        tickers = {
            "Ibovespa": "^BVSP",
            "S&P 500": "^GSPC",
            "Dólar": "BRL=X",
            "Bitcoin": "BTC-USD",
            "Ethereum": "ETH-USD",
            "Ouro": "GC=F",
        }

        result: Dict[str, Dict[str, str]] = {}
        for name, ticker in tickers.items():
            try:
                history = self._history_for_date(ticker, date_ref)
                current = float(history["Close"].iloc[-1])
                previous = float(history["Close"].iloc[-2])
                change_pct = ((current - previous) / previous) * 100

                value_label = self._format_value(ticker, current)

                direction = "up" if change_pct >= 0 else "down"
                result[name] = {
                    "value": value_label,
                    "changePct": f"{change_pct:+.2f}%",
                    "direction": direction,
                    "display": f"{value_label} ({change_pct:+.2f}%)",
                }
            except Exception:
                result[name] = {
                    "value": "Indisponível",
                    "changePct": "",
                    "direction": "flat",
                    "display": "Indisponível",
                }

        return result
