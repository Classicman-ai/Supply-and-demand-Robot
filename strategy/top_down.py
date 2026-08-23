"""Canonical D1 → H4 → H1 → M15 → M5 supply/demand analysis."""
from __future__ import annotations
from typing import Any
from models.zones import Zone, ZoneType
from strategy.zone_detector import ZoneDetector
from strategy.zone_scorer import ZoneScorer


class TopDownEngine:
    TIMEFRAMES = ("D1", "H4", "H1", "M15", "M5")

    def __init__(self, market_data: Any, detector: ZoneDetector | None = None, scorer: ZoneScorer | None = None) -> None:
        self.market_data = market_data
        self.detector = detector or ZoneDetector()
        self.scorer = scorer or ZoneScorer()

    def analyze(self, symbol: str, bars: int = 500) -> dict[str, Any]:
        data = self.market_data.get_top_down_data(symbol, bars)
        missing = [timeframe for timeframe in self.TIMEFRAMES if not data.get(timeframe)]
        if missing:
            return self._rejected(symbol, f"missing or insufficient data: {', '.join(missing)}")
        resolved = next((row[0].get("symbol") for row in data.values() if row and row[0].get("symbol")), symbol)
        current_price = float(data["M5"][-1]["close"])
        by_timeframe: dict[str, list[Zone]] = {}
        for timeframe in self.TIMEFRAMES:
            zones = self.detector.detect(data[timeframe], resolved, timeframe)
            by_timeframe[timeframe] = self.scorer.score_all(zones, current_price)
        supply = [z for zones in by_timeframe.values() for z in zones if z.zone_type is ZoneType.SUPPLY and z.active]
        demand = [z for zones in by_timeframe.values() for z in zones if z.zone_type is ZoneType.DEMAND and z.active]
        nearest_supply = self._nearest(supply, current_price)
        nearest_demand = self._nearest(demand, current_price)
        bias = self._bias(nearest_supply, nearest_demand, current_price)
        m15_confirmation = self._confirmation(by_timeframe["M15"], current_price, bias)
        m5_context = self._confirmation(by_timeframe["M5"], current_price, bias)
        reasons = [f"{timeframe}: {len(by_timeframe[timeframe])} detected zone(s)" for timeframe in self.TIMEFRAMES]
        reasons.append(f"context bias: {bias}")
        return {"status": "OK", "symbol": resolved, "current_price": current_price, "timeframes": by_timeframe,
                "active_supply_zones": supply, "active_demand_zones": demand, "nearest_supply": nearest_supply,
                "nearest_demand": nearest_demand, "higher_timeframe_bias": bias,
                "m15_confirmation": m15_confirmation, "m5_entry_context": m5_context, "reasons": reasons,
                "rejection_reasons": []}

    @staticmethod
    def _nearest(zones: list[Zone], price: float) -> Zone | None:
        return min(zones, key=lambda z: min(abs(price-z.lower_price), abs(price-z.upper_price)), default=None)

    @staticmethod
    def _bias(supply: Zone | None, demand: Zone | None, price: float) -> str:
        if demand and demand.lower_price <= price <= demand.upper_price: return "BULLISH"
        if supply and supply.lower_price <= price <= supply.upper_price: return "BEARISH"
        if demand and (not supply or demand.score > supply.score): return "BULLISH_CONTEXT"
        if supply: return "BEARISH_CONTEXT"
        return "NEUTRAL"

    @staticmethod
    def _confirmation(zones: list[Zone], price: float, bias: str) -> dict[str, Any]:
        relevant = [z for z in zones if z.lower_price <= price <= z.upper_price]
        return {"confirmed": bool(relevant) and bias != "NEUTRAL", "zones": relevant,
                "reason": "price is reacting inside a matching zone" if relevant else "price is not inside an MTF zone"}

    @staticmethod
    def _rejected(symbol: str, reason: str) -> dict[str, Any]:
        return {"status": "NO_ANALYSIS", "symbol": symbol, "rejection_reasons": [reason], "reasons": []}
