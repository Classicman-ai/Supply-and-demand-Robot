"""
Historical Strategy Adapter
===========================

Chronological, historical-only binding for the real Supply & Demand
strategy pipeline.

IMPORTANT:
- No MetaTrader5 import.
- No order_send().
- No live position access.
- No synthetic zones.
- No artificial grades.
- The historical timestamp is set BEFORE TopDownEngine.analyze().
- The real ZoneDetector, ZoneValidationEngine and EntryEngine are used.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from strategy.entry_engine import EntryEngine
from strategy.top_down import TopDownEngine


@dataclass
class StrategyDecision:
    accepted: bool
    direction: str | None = None
    entry: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    reason: str = ""
    raw: Any = None


class HistoricalStrategyAdapter:

    VERSION = "2.0.0-CHRONOLOGICAL-REAL-PIPELINE"

    def __init__(
        self,
        market_data: Any,
        entry_engine: EntryEngine | None = None,
        top_down_engine: TopDownEngine | None = None,
        bars: int = 500,
    ) -> None:
        self.market_data = market_data
        self.bars = int(bars)
        if self.bars < 20:
            raise ValueError("bars must be >= 20")

        self.top_down = top_down_engine or TopDownEngine(market_data)
        self.entry = entry_engine or EntryEngine()

    def evaluate_at(
        self,
        timestamp: Any,
        symbol: str,
    ) -> StrategyDecision:
        """
        Evaluate the real strategy at one historical timestamp.

        HistoricalMarketData.set_timestamp() is called first. Its contract
        guarantees that get_top_down_data() exposes only candles at or before
        that timestamp. Therefore TopDownEngine sees a genuine historical
        snapshot rather than the final dataset price.
        """
        if not hasattr(self.market_data, "set_timestamp"):
            raise TypeError(
                "market_data must implement set_timestamp(timestamp)"
            )

        self.market_data.set_timestamp(timestamp)

        analysis = self.top_down.analyze(
            symbol=symbol,
            bars=self.bars,
        )

        setup = self.entry.evaluate(analysis)

        if setup.get("status") != "SETUP":
            return StrategyDecision(
                accepted=False,
                reason=str(setup.get("reason", "NO_TRADE")),
                raw=setup,
            )

        return StrategyDecision(
            accepted=True,
            direction=str(setup.get("direction")),
            entry=float(setup["entry"]),
            stop_loss=float(setup["stop_loss"]),
            take_profit=float(setup["take_profit"]),
            reason=str(setup.get("reason", "SETUP")),
            raw=setup,
        )

    def evaluate(self, timestamp: Any, symbol: str) -> StrategyDecision:
        """Compatibility alias for chronological callers."""
        return self.evaluate_at(timestamp, symbol)

    def discovery_report(self) -> dict[str, Any]:
        return {
            "adapter_version": self.VERSION,
            "market_data": type(self.market_data).__name__,
            "top_down_engine": type(self.top_down).__name__,
            "zone_detector": type(self.top_down.detector).__name__,
            "zone_validator": type(self.top_down.validator).__name__,
            "entry_engine": type(self.entry).__name__,
            "historical_timestamp_gate": True,
            "synthetic_zones": False,
            "artificial_grades": False,
            "live_execution": False,
        }
