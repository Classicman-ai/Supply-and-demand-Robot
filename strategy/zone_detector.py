"""Price-action Supply/Demand zone detector; no SMC/ICT concepts."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable
import hashlib

from models.zones import MitigationStatus, Zone, ZoneType


class ZoneDetector:
    def __init__(self, min_base_candles: int = 1, max_base_candles: int = 6,
                 departure_multiplier: float = 1.5) -> None:
        self.min_base_candles = min_base_candles
        self.max_base_candles = max_base_candles
        self.departure_multiplier = departure_multiplier

    def detect(self, candles: Iterable[dict[str, Any]], symbol: str, timeframe: str) -> list[Zone]:
        rows = [self._candle(c) for c in candles]
        if len(rows) < 12 or not symbol:
            return []
        atr = self._atr(rows)
        if atr <= 0:
            return []
        zones: list[Zone] = []
        for start in range(2, len(rows) - self.min_base_candles - 1):
            for size in range(self.min_base_candles, self.max_base_candles + 1):
                end, departure_index = start + size, start + size
                if departure_index >= len(rows):
                    break
                base = rows[start:end]
                if not self._is_base(base, atr):
                    continue
                departure = rows[departure_index]
                body = abs(departure["close"] - departure["open"])
                if body < atr * self.departure_multiplier:
                    continue
                direction = ZoneType.DEMAND if departure["close"] > departure["open"] else ZoneType.SUPPLY
                zone = self._make_zone(base, rows[departure_index + 1:], symbol, timeframe, direction, body / atr)
                if zone:
                    zones.append(zone)
                break
        return self._deduplicate(zones)

    @staticmethod
    def _candle(candle: dict[str, Any]) -> dict[str, Any]:
        required = ("open", "high", "low", "close", "time")
        if not all(key in candle for key in required):
            raise ValueError("candles require time, open, high, low and close")
        values = {key: float(candle[key]) for key in ("open", "high", "low", "close")}
        if values["high"] < max(values["open"], values["close"]) or values["low"] > min(values["open"], values["close"]):
            raise ValueError("invalid OHLC candle")
        value = candle["time"]
        if not isinstance(value, datetime):
            value = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        values["time"] = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
        return values

    @staticmethod
    def _atr(rows: list[dict[str, Any]], period: int = 10) -> float:
        ranges = [r["high"] - r["low"] for r in rows[-period:]]
        return sum(ranges) / len(ranges) if ranges else 0.0

    @staticmethod
    def _is_base(base: list[dict[str, Any]], atr: float) -> bool:
        width = max(r["high"] for r in base) - min(r["low"] for r in base)
        return width > 0 and width <= atr * max(1.2, len(base) * 0.9)

    def _make_zone(self, base: list[dict[str, Any]], subsequent: list[dict[str, Any]], symbol: str,
                   timeframe: str, zone_type: ZoneType, strength: float) -> Zone | None:
        upper, lower = max(r["high"] for r in base), min(r["low"] for r in base)
        tests = 0
        invalidated = False
        for row in subsequent:
            touched = row["low"] <= upper and row["high"] >= lower
            tests += int(touched)
            if zone_type is ZoneType.DEMAND and row["close"] < lower:
                invalidated = True
            if zone_type is ZoneType.SUPPLY and row["close"] > upper:
                invalidated = True
        if invalidated:
            status = MitigationStatus.INVALIDATED
        elif tests == 0:
            status = MitigationStatus.FRESH
        elif tests == 1:
            status = MitigationStatus.TESTED
        else:
            status = MitigationStatus.MITIGATED
        origin = base[0]["time"]
        departure = subsequent[0]["time"] if subsequent else base[-1]["time"]
        digest = hashlib.sha1(f"{symbol}|{timeframe}|{zone_type.value}|{origin.isoformat()}|{upper:.8f}|{lower:.8f}".encode()).hexdigest()[:12]
        return Zone(zone_id=f"{timeframe}_{zone_type.value}_{digest}", symbol=symbol, timeframe=timeframe,
                    zone_type=zone_type, upper_price=upper, lower_price=lower, created_at=datetime.now(timezone.utc),
                    origin_time=origin, freshness=max(0, 100 - tests * 30), test_count=tests,
                    mitigation_status=status, invalidation_status=invalidated, strength=min(100, strength * 20),
                    source_timeframe=timeframe,
                    metadata={
                        "base_candles": len(base),
                        "departure_atr": round(strength, 3),
                        "base_start_time": origin,
                        "departure_end_time": departure,
                        "departure_candles": 1,
                    })

    @staticmethod
    def _deduplicate(zones: list[Zone]) -> list[Zone]:
        unique: dict[tuple[str, str, int, int], Zone] = {}
        for zone in zones:
            key = (zone.timeframe, zone.zone_type.value, round(zone.upper_price * 100000), round(zone.lower_price * 100000))
            if key not in unique or unique[key].strength < zone.strength:
                unique[key] = zone
        return sorted(unique.values(), key=lambda zone: (zone.origin_time, zone.zone_id))
