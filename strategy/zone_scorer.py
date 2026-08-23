"""Deterministic, explainable quality scoring for supply/demand zones."""
from __future__ import annotations

from typing import Iterable
from models.zones import Zone


class ZoneScorer:
    def score(self, zone: Zone, current_price: float | None = None,
              higher_timeframe_alignment: bool | None = None) -> Zone:
        reasons: list[str] = []
        total = 0.0
        freshness = zone.freshness * 0.25
        total += freshness
        reasons.append(f"freshness {zone.freshness:.0f}% contributes {freshness:.1f}")
        departure = min(25.0, zone.strength * 0.25)
        total += departure
        reasons.append(f"departure strength {zone.strength:.1f} contributes {departure:.1f}")
        tests = max(0.0, 20.0 - zone.test_count * 8.0)
        total += tests
        reasons.append(f"{zone.test_count} retest(s) contributes {tests:.1f}")
        if zone.active:
            total += 15.0; reasons.append("zone remains valid contributes 15.0")
        else:
            reasons.append("invalidated zone contributes 0.0")
        if current_price and current_price > 0:
            distance = min(abs(current_price - zone.upper_price), abs(current_price - zone.lower_price))
            proximity = max(0.0, 10.0 * (1 - distance / max(zone.width * 10, 1e-12)))
            total += proximity; reasons.append(f"price proximity contributes {proximity:.1f}")
        if higher_timeframe_alignment is True:
            total += 5.0; reasons.append("higher-timeframe alignment contributes 5.0")
        elif higher_timeframe_alignment is False:
            total -= 10.0; reasons.append("higher-timeframe conflict subtracts 10.0")
        zone.score = round(min(100.0, max(0.0, total)), 2)
        zone.score_reasons = reasons
        return zone

    def score_all(self, zones: Iterable[Zone], current_price: float | None = None) -> list[Zone]:
        return [self.score(zone, current_price) for zone in zones]
