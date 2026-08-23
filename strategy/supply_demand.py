"""
SUPPLY & DEMAND MT5
SUPPLY & DEMAND ZONE ENGINE
============================================================

Version:
    1.0.0

Purpose:
    Detect pure Supply and Demand zones from REAL MT5 OHLC data.

Rules:
    - REAL MT5 DATA ONLY
    - NO SIMULATION
    - NO HARDCODED MARKET PRICES
    - READ-ONLY
    - NO TRADE EXECUTION
    - NO SMC
    - NO ICT

Zone model:

    DEMAND:
        Base -> strong bullish departure

    SUPPLY:
        Base -> strong bearish departure

The engine identifies:
    - Base candles
    - Departure candles
    - Zone boundaries
    - Zone strength
    - Freshness
    - Touch count
    - Zone status

Input:
    Normalized candles returned by MarketData.

Output:
    Pure Python dictionaries.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class SupplyDemandEngine:
    """
    Pure Supply & Demand zone detection engine.

    This class does NOT connect to MT5 directly.

    MarketData owns the MT5 connection.
    """

    ENGINE_NAME = "SUPPLY & DEMAND ZONE ENGINE"
    VERSION = "1.0.0"

    READ_ONLY = True
    EXECUTION_ENABLED = False
    SIMULATION_ENABLED = False

    ZONE_TYPES = (
        "DEMAND",
        "SUPPLY",
    )

    def __init__(
        self,
        min_base_candles: int = 1,
        max_base_candles: int = 4,
        departure_candles: int = 3,
        departure_multiplier: float = 1.5,
        max_zone_age_candles: Optional[int] = None,
    ) -> None:

        if min_base_candles <= 0:
            raise ValueError(
                "min_base_candles must be greater than zero."
            )

        if max_base_candles < min_base_candles:
            raise ValueError(
                "max_base_candles must be >= min_base_candles."
            )

        if departure_candles <= 0:
            raise ValueError(
                "departure_candles must be greater than zero."
            )

        if departure_multiplier <= 0:
            raise ValueError(
                "departure_multiplier must be greater than zero."
            )

        self.min_base_candles = min_base_candles
        self.max_base_candles = max_base_candles
        self.departure_candles = departure_candles
        self.departure_multiplier = departure_multiplier
        self.max_zone_age_candles = max_zone_age_candles

    # ==============================================================
    # PUBLIC API
    # ==============================================================

    def detect_zones(
        self,
        candles: List[Dict[str, Any]],
        symbol: str,
        timeframe: str,
    ) -> List[Dict[str, Any]]:
        """
        Detect Supply and Demand zones.

        Candles must be normalized MarketData candles.

        Expected fields:

            time
            timestamp
            open
            high
            low
            close
        """

        if not isinstance(candles, list):
            raise TypeError(
                "candles must be a list."
            )

        if not candles:
            return []

        symbol = str(symbol).strip()

        timeframe = str(
            timeframe
        ).strip().upper()

        if not symbol:
            raise ValueError(
                "symbol cannot be empty."
            )

        if not timeframe:
            raise ValueError(
                "timeframe cannot be empty."
            )

        validated = self._validate_candles(
            candles
        )

        if len(validated) < (
            self.min_base_candles
            + self.departure_candles
            + 1
        ):
            return []

        zones: List[Dict[str, Any]] = []

        i = self.min_base_candles

        while i < len(validated) - self.departure_candles:

            for base_length in range(
                self.min_base_candles,
                self.max_base_candles + 1,
            ):

                base_start = i - base_length
                base_end = i - 1

                if base_start < 0:
                    continue

                base = validated[
                    base_start:base_end + 1
                ]

                departure = validated[
                    i:i + self.departure_candles
                ]

                if len(departure) < self.departure_candles:
                    continue

                demand = self._detect_demand(
                    base,
                    departure,
                    symbol,
                    timeframe,
                    base_start,
                    base_end,
                    i,
                )

                if demand is not None:
                    zones.append(demand)

                supply = self._detect_supply(
                    base,
                    departure,
                    symbol,
                    timeframe,
                    base_start,
                    base_end,
                    i,
                )

                if supply is not None:
                    zones.append(supply)

            i += 1

        return self._deduplicate_zones(
            zones
        )

    # ==============================================================
    # DEMAND
    # ==============================================================

    def _detect_demand(
        self,
        base: List[Dict[str, Any]],
        departure: List[Dict[str, Any]],
        symbol: str,
        timeframe: str,
        base_start: int,
        base_end: int,
        departure_start: int,
    ) -> Optional[Dict[str, Any]]:

        if not self._base_is_valid(base):
            return None

        base_high = max(
            float(c["high"])
            for c in base
        )

        base_low = min(
            float(c["low"])
            for c in base
        )

        base_range = base_high - base_low

        if base_range <= 0:
            return None

        departure_high = max(
            float(c["high"])
            for c in departure
        )

        departure_low = min(
            float(c["low"])
            for c in departure
        )

        departure_close = float(
            departure[-1]["close"]
        )

        bullish_move = (
            departure_close - base_high
        )

        departure_range = (
            departure_high - departure_low
        )

        if departure_range <= 0:
            return None

        if bullish_move <= (
            base_range
            * self.departure_multiplier
        ):
            return None

        bullish_candles = sum(
            1
            for candle in departure
            if float(candle["close"])
            > float(candle["open"])
        )

        if bullish_candles == 0:
            return None

        strength = self._calculate_strength(
            base_range,
            departure_range,
            bullish_candles,
            len(departure),
        )

        return self._build_zone(
            zone_type="DEMAND",
            symbol=symbol,
            timeframe=timeframe,
            base=base,
            departure=departure,
            base_start=base_start,
            base_end=base_end,
            departure_start=departure_start,
            proximal=base_high,
            distal=base_low,
            strength=strength,
        )

    # ==============================================================
    # SUPPLY
    # ==============================================================

    def _detect_supply(
        self,
        base: List[Dict[str, Any]],
        departure: List[Dict[str, Any]],
        symbol: str,
        timeframe: str,
        base_start: int,
        base_end: int,
        departure_start: int,
    ) -> Optional[Dict[str, Any]]:

        if not self._base_is_valid(base):
            return None

        base_high = max(
            float(c["high"])
            for c in base
        )

        base_low = min(
            float(c["low"])
            for c in base
        )

        base_range = base_high - base_low

        if base_range <= 0:
            return None

        departure_high = max(
            float(c["high"])
            for c in departure
        )

        departure_low = min(
            float(c["low"])
            for c in departure
        )

        departure_close = float(
            departure[-1]["close"]
        )

        bearish_move = (
            base_low - departure_close
        )

        departure_range = (
            departure_high - departure_low
        )

        if departure_range <= 0:
            return None

        if bearish_move <= (
            base_range
            * self.departure_multiplier
        ):
            return None

        bearish_candles = sum(
            1
            for candle in departure
            if float(candle["close"])
            < float(candle["open"])
        )

        if bearish_candles == 0:
            return None

        strength = self._calculate_strength(
            base_range,
            departure_range,
            bearish_candles,
            len(departure),
        )

        return self._build_zone(
            zone_type="SUPPLY",
            symbol=symbol,
            timeframe=timeframe,
            base=base,
            departure=departure,
            base_start=base_start,
            base_end=base_end,
            departure_start=departure_start,
            proximal=base_low,
            distal=base_high,
            strength=strength,
        )

    # ==============================================================
    # BASE VALIDATION
    # ==============================================================

    @staticmethod
    def _base_is_valid(
        base: List[Dict[str, Any]],
    ) -> bool:

        if not base:
            return False

        ranges = []

        for candle in base:

            high = float(
                candle["high"]
            )

            low = float(
                candle["low"]
            )

            open_price = float(
                candle["open"]
            )

            close_price = float(
                candle["close"]
            )

            if high < low:
                return False

            if open_price < low:
                return False

            if open_price > high:
                return False

            if close_price < low:
                return False

            if close_price > high:
                return False

            candle_range = high - low

            if candle_range <= 0:
                return False

            ranges.append(
                candle_range
            )

        average_range = sum(
            ranges
        ) / len(ranges)

        if average_range <= 0:
            return False

        # Base should be relatively compact.
        largest = max(ranges)

        if largest > average_range * 3.0:
            return False

        return True

    # ==============================================================
    # STRENGTH
    # ==============================================================

    @staticmethod
    def _calculate_strength(
        base_range: float,
        departure_range: float,
        directional_candles: int,
        total_departure_candles: int,
    ) -> float:

        if base_range <= 0:
            return 0.0

        departure_ratio = (
            departure_range
            / base_range
        )

        directional_ratio = (
            directional_candles
            / total_departure_candles
        )

        raw = (
            departure_ratio * 20.0
            + directional_ratio * 80.0
        )

        return round(
            min(100.0, raw),
            2,
        )

    # ==============================================================
    # ZONE CREATION
    # ==============================================================

    def _build_zone(
        self,
        zone_type: str,
        symbol: str,
        timeframe: str,
        base: List[Dict[str, Any]],
        departure: List[Dict[str, Any]],
        base_start: int,
        base_end: int,
        departure_start: int,
        proximal: float,
        distal: float,
        strength: float,
    ) -> Dict[str, Any]:

        created = departure[0].get(
            "time"
        )

        if isinstance(
            created,
            datetime,
        ):
            created_at = created
        else:
            created_at = datetime.now(
                timezone.utc
            )

        return {
            "zone_id": (
                f"{symbol}-"
                f"{timeframe}-"
                f"{zone_type}-"
                f"{departure[0]['timestamp']}"
            ),

            "symbol": symbol,

            "timeframe": timeframe,

            "zone_type": zone_type,

            "proximal_price": float(
                proximal
            ),

            "distal_price": float(
                distal
            ),

            "base_start": base_start,

            "base_end": base_end,

            "base_candles": len(base),

            "departure_start": departure_start,

            "departure_end": (
                departure_start
                + len(departure)
                - 1
            ),

            "departure_candles": len(
                departure
            ),

            "base_start_time": base[0][
                "time"
            ],

            "base_end_time": base[-1][
                "time"
            ],

            "departure_start_time": departure[0][
                "time"
            ],

            "departure_end_time": departure[-1][
                "time"
            ],

            "strength": float(
                strength
            ),

            "freshness": "FRESH",

            "touch_count": 0,

            "status": "ACTIVE",

            "created_at": created_at,

            "invalidated": False,
        }

    # ==============================================================
    # VALIDATION
    # ==============================================================

    @staticmethod
    def _validate_candles(
        candles: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:

        required = (
            "open",
            "high",
            "low",
            "close",
            "timestamp",
        )

        validated = []

        for candle in candles:

            if not isinstance(
                candle,
                dict,
            ):
                continue

            if any(
                field not in candle
                for field in required
            ):
                continue

            try:
                open_price = float(
                    candle["open"]
                )

                high = float(
                    candle["high"]
                )

                low = float(
                    candle["low"]
                )

                close = float(
                    candle["close"]
                )

                timestamp = int(
                    candle["timestamp"]
                )

            except (
                TypeError,
                ValueError,
            ):
                continue

            if high < low:
                continue

            if open_price < low or open_price > high:
                continue

            if close < low or close > high:
                continue

            item = dict(candle)

            item["open"] = open_price
            item["high"] = high
            item["low"] = low
            item["close"] = close
            item["timestamp"] = timestamp

            validated.append(item)

        validated.sort(
            key=lambda c: c["timestamp"]
        )

        return validated

    # ==============================================================
    # DEDUPLICATION
    # ==============================================================

    @staticmethod
    def _deduplicate_zones(
        zones: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:

        if not zones:
            return []

        unique: Dict[str, Dict[str, Any]] = {}

        for zone in zones:

            key = (
                zone["zone_type"],
                zone["symbol"],
                zone["timeframe"],
                zone["base_start_time"],
                zone["base_end_time"],
            )

            existing = unique.get(key)

            if existing is None:
                unique[key] = zone
                continue

            if zone["strength"] > existing["strength"]:
                unique[key] = zone

        result = list(
            unique.values()
        )

        result.sort(
            key=lambda z: z[
                "departure_start_time"
            ]
        )

        return result


__all__ = [
    "SupplyDemandEngine",
]
