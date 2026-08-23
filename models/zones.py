"""Typed, validated supply and demand zone contracts."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping
import math


class ZoneType(str, Enum):
    SUPPLY = "SUPPLY"
    DEMAND = "DEMAND"


class MitigationStatus(str, Enum):
    FRESH = "FRESH"
    TESTED = "TESTED"
    MITIGATED = "MITIGATED"
    INVALIDATED = "INVALIDATED"


@dataclass(slots=True)
class Zone:
    zone_id: str
    symbol: str
    timeframe: str
    zone_type: ZoneType
    upper_price: float
    lower_price: float
    created_at: datetime
    origin_time: datetime
    freshness: float = 100.0
    test_count: int = 0
    mitigation_status: MitigationStatus = MitigationStatus.FRESH
    invalidation_status: bool = False
    strength: float = 0.0
    score: float = 0.0
    source_timeframe: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    score_reasons: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.symbol = str(self.symbol).strip()
        self.timeframe = str(self.timeframe).upper().strip()
        self.source_timeframe = (self.source_timeframe or self.timeframe).upper().strip()
        if not self.zone_id or not self.symbol or not self.timeframe:
            raise ValueError("zone_id, symbol and timeframe are required")
        if not isinstance(self.zone_type, ZoneType):
            self.zone_type = ZoneType(str(self.zone_type).upper())
        if not isinstance(self.mitigation_status, MitigationStatus):
            self.mitigation_status = MitigationStatus(str(self.mitigation_status).upper())
        for name in ("upper_price", "lower_price", "freshness", "strength", "score"):
            value = float(getattr(self, name))
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
            setattr(self, name, value)
        if self.lower_price <= 0 or self.upper_price <= self.lower_price:
            raise ValueError("zone prices must be positive and upper_price > lower_price")
        if self.test_count < 0:
            raise ValueError("test_count cannot be negative")
        self.freshness = min(100.0, max(0.0, self.freshness))
        self.score = min(100.0, max(0.0, self.score))
        self.created_at = self._utc(self.created_at)
        self.origin_time = self._utc(self.origin_time)

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if not isinstance(value, datetime):
            raise ValueError("zone times must be datetime values")
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

    @property
    def width(self) -> float:
        return self.upper_price - self.lower_price

    @property
    def active(self) -> bool:
        return not self.invalidation_status and self.mitigation_status != MitigationStatus.INVALIDATED

    def to_dict(self) -> dict[str, Any]:
        return {"zone_id": self.zone_id, "symbol": self.symbol, "timeframe": self.timeframe,
                "zone_type": self.zone_type.value, "upper_price": self.upper_price, "lower_price": self.lower_price,
                "created_at": self.created_at.isoformat(), "origin_time": self.origin_time.isoformat(),
                "freshness": self.freshness, "test_count": self.test_count,
                "mitigation_status": self.mitigation_status.value, "invalidation_status": self.invalidation_status,
                "strength": self.strength, "score": self.score, "source_timeframe": self.source_timeframe,
                "metadata": self.metadata, "score_reasons": self.score_reasons}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Zone":
        values = dict(data)
        for key in ("created_at", "origin_time"):
            if isinstance(values.get(key), str):
                values[key] = datetime.fromisoformat(values[key].replace("Z", "+00:00"))
        return cls(**values)
