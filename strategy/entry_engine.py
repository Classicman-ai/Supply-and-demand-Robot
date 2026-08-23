"""Turns confirmed supply/demand context into a validated trade setup or NO_TRADE."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from models.zones import Zone, ZoneType


class EntryEngine:
    def __init__(self, min_risk_reward: float = 3.0, stop_buffer_fraction: float = 0.2) -> None:
        self.min_risk_reward = min_risk_reward
        self.stop_buffer_fraction = stop_buffer_fraction

    def evaluate(self, analysis: dict[str, Any]) -> dict[str, Any]:
        if analysis.get("status") != "OK":
            return self._reject("ANALYSIS_UNAVAILABLE", analysis.get("rejection_reasons", []))
        price, bias = analysis["current_price"], analysis["higher_timeframe_bias"]
        confirmed = analysis["m15_confirmation"].get("confirmed") and analysis["m5_entry_context"].get("confirmed")
        if not confirmed:
            return self._reject("CONFIRMATION_REQUIRED", ["M15 and M5 confirmation are required"])
        zone: Zone | None = analysis["nearest_demand"] if bias.startswith("BULLISH") else analysis["nearest_supply"] if bias.startswith("BEARISH") else None
        if zone is None or not zone.active or not (zone.lower_price <= price <= zone.upper_price):
            return self._reject("VALID_ZONE_REQUIRED", ["price must be inside an active matching zone"])
        direction = "BUY" if zone.zone_type is ZoneType.DEMAND else "SELL"
        stop = zone.lower_price - zone.width * self.stop_buffer_fraction if direction == "BUY" else zone.upper_price + zone.width * self.stop_buffer_fraction
        risk = abs(price - stop)
        if risk <= 0:
            return self._reject("INVALID_STOP_DISTANCE", [])
        opposing: Zone | None = analysis["nearest_supply"] if direction == "BUY" else analysis["nearest_demand"]
        structural_target = opposing.lower_price if direction == "BUY" and opposing else opposing.upper_price if opposing else None
        minimum_target = price + risk * self.min_risk_reward if direction == "BUY" else price - risk * self.min_risk_reward
        target = structural_target if structural_target and ((direction == "BUY" and structural_target >= minimum_target) or (direction == "SELL" and structural_target <= minimum_target)) else minimum_target
        reward = abs(target - price)
        return {"status": "SETUP", "symbol": analysis["symbol"], "direction": direction, "timeframe": "M5", "entry": price,
                "stop_loss": stop, "take_profit": target, "risk_reward": round(reward / risk, 3), "zone_id": zone.zone_id,
                "reason": f"{zone.zone_type.value} zone with M15/M5 confirmation", "timestamp": datetime.now(timezone.utc).isoformat(),
                "requires_risk_approval": True}

    @staticmethod
    def _reject(code: str, reasons: list[str]) -> dict[str, Any]:
        return {"status": "NO_TRADE", "reason": code, "rejection_reasons": reasons}
