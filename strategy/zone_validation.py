"""
SUPPLY & DEMAND MT5
ZONE VALIDATION ENGINE
============================================================

Version:
    1.0.0

Purpose:
    Validate Supply and Demand zones using REAL normalized
    market data supplied by the MarketData layer.

Architecture:
    MarketData -> SupplyDemandEngine -> ZoneValidationEngine

Rules:
    - ANALYSIS ONLY
    - NO MT5 IMPORT
    - NO MT5 CONNECTION
    - NO SIMULATION
    - NO HARDCODED MARKET PRICES
    - NO ORDER EXECUTION
    - NO POSITION MANAGEMENT

Features:
    - Zone age
    - Freshness
    - Touch / retest detection
    - Mitigation
    - Invalidation
    - Current price location
    - Proximal / distal distance
    - Zone width
    - Penetration
    - Rejection
    - Departure quality
    - Base quality
    - Directional quality
    - Zone strength
    - Opposing-zone conflict
    - Validation score
    - Quality grade
    - Diagnostic reasons
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class ZoneValidationEngine:
    """
    Pure analytical Supply & Demand zone validator.

    This class has NO MT5 dependency and NO execution ability.
    """

    ENGINE_NAME = "SUPPLY & DEMAND ZONE VALIDATION ENGINE"
    VERSION = "1.0.0"

    READ_ONLY = True
    EXECUTION_ENABLED = False
    SIMULATION_ENABLED = False

    STATUSES = (
        "FRESH",
        "TESTED",
        "MITIGATED",
        "INVALIDATED",
        "ACTIVE",
    )

    LOCATION_STATES = (
        "ABOVE",
        "BELOW",
        "INSIDE",
        "AT_PROXIMAL",
        "AT_DISTAL",
    )

    GRADES = (
        "A+",
        "A",
        "B",
        "C",
        "INVALID",
    )

    def __init__(
        self,
        touch_tolerance: float = 0.001,
        invalidation_buffer: float = 0.0,
        minimum_score: float = 60.0,
    ) -> None:

        if touch_tolerance < 0:
            raise ValueError(
                "touch_tolerance must be >= 0."
            )

        if invalidation_buffer < 0:
            raise ValueError(
                "invalidation_buffer must be >= 0."
            )

        if not 0 <= minimum_score <= 100:
            raise ValueError(
                "minimum_score must be between 0 and 100."
            )

        self.touch_tolerance = float(touch_tolerance)
        self.invalidation_buffer = float(
            invalidation_buffer
        )
        self.minimum_score = float(minimum_score)

    # ==============================================================
    # PUBLIC API
    # ==============================================================

    def validate_zone(
        self,
        zone: Dict[str, Any],
        candles: List[Dict[str, Any]],
        current_price: Optional[float] = None,
        opposing_zones: Optional[
            List[Dict[str, Any]]
        ] = None,
    ) -> Dict[str, Any]:
        """
        Validate one Supply/Demand zone.

        No market data is retrieved here.
        All market information must be supplied by the caller.
        """

        self._validate_zone_input(zone)

        if not isinstance(candles, list):
            raise TypeError(
                "candles must be a list."
            )

        validated = self._validate_candles(
            candles
        )

        if not validated:
            raise ValueError(
                "No valid candles supplied."
            )

        zone_type = str(
            zone["zone_type"]
        ).upper()

        proximal = float(
            zone["proximal_price"]
        )

        distal = float(
            zone["distal_price"]
        )

        lower = min(
            proximal,
            distal,
        )

        upper = max(
            proximal,
            distal,
        )

        if current_price is None:
            current_price = float(
                validated[-1]["close"]
            )
        else:
            current_price = float(
                current_price
            )

        zone_start_timestamp = self._zone_start_timestamp(
            zone
        )

        zone_end_timestamp = self._zone_end_timestamp(
            zone
        )

        candles_after_zone = [
            candle
            for candle in validated
            if int(candle["timestamp"])
            > zone_end_timestamp
        ]

        age = len(
            candles_after_zone
        )

        touches = self._count_touches(
            lower,
            upper,
            candles_after_zone,
        )

        penetration = self._calculate_penetration(
            lower,
            upper,
            candles_after_zone,
            zone_type,
        )

        rejection = self._calculate_rejection(
            lower,
            upper,
            candles_after_zone,
            zone_type,
        )

        invalidated = self._is_invalidated(
            lower,
            upper,
            candles_after_zone,
            zone_type,
        )

        if invalidated:
            status = "INVALIDATED"

        elif touches == 0:
            status = "FRESH"

        elif touches == 1:
            status = "TESTED"

        else:
            status = "MITIGATED"

        location = self._price_location(
            current_price,
            lower,
            upper,
        )

        distance_to_proximal = abs(
            current_price - proximal
        )

        distance_to_distal = abs(
            current_price - distal
        )

        zone_width = upper - lower

        width_percent = (
            zone_width / current_price * 100.0
            if current_price > 0
            else 0.0
        )

        departure_quality = self._departure_quality(
            zone
        )

        base_quality = self._base_quality(
            zone
        )

        directional_quality = self._directional_quality(
            zone
        )

        opposing_analysis = self._opposing_zone_analysis(
            current_price,
            zone,
            opposing_zones or [],
        )

        score = self._calculate_score(
            zone_strength=float(
                zone.get("strength", 0.0)
            ),
            status=status,
            touches=touches,
            penetration=penetration,
            rejection=rejection,
            departure_quality=departure_quality,
            base_quality=base_quality,
            directional_quality=directional_quality,
            opposing_conflict=opposing_analysis[
                "conflict"
            ],
            invalidated=invalidated,
        )

        grade = self._grade(
            score,
            invalidated,
        )

        reasons = self._build_reasons(
            zone_type=zone_type,
            status=status,
            location=location,
            touches=touches,
            penetration=penetration,
            rejection=rejection,
            score=score,
            grade=grade,
            opposing_analysis=opposing_analysis,
        )

        warnings = self._build_warnings(
            invalidated=invalidated,
            status=status,
            location=location,
            opposing_analysis=opposing_analysis,
            rejection=rejection,
            penetration=penetration,
        )

        return {
            "zone_id": zone.get(
                "zone_id"
            ),

            "symbol": zone.get(
                "symbol"
            ),

            "timeframe": zone.get(
                "timeframe"
            ),

            "zone_type": zone_type,

            "status": status,

            "grade": grade,

            "validated": bool(
                grade != "INVALID"
                and score >= self.minimum_score
            ),

            "score": round(
                score,
                2,
            ),

            "current_price": current_price,

            "location": location,

            "proximal_price": proximal,

            "distal_price": distal,

            "zone_low": lower,

            "zone_high": upper,

            "zone_width": round(
                zone_width,
                8,
            ),

            "zone_width_percent": round(
                width_percent,
                6,
            ),

            "distance_to_proximal": round(
                distance_to_proximal,
                8,
            ),

            "distance_to_distal": round(
                distance_to_distal,
                8,
            ),

            "age_candles": age,

            "touch_count": touches,

            "penetration_percent": round(
                penetration,
                2,
            ),

            "rejection_percent": round(
                rejection,
                2,
            ),

            "departure_quality": round(
                departure_quality,
                2,
            ),

            "base_quality": round(
                base_quality,
                2,
            ),

            "directional_quality": round(
                directional_quality,
                2,
            ),

            "zone_strength": float(
                zone.get(
                    "strength",
                    0.0,
                )
            ),

            "opposing_zone_analysis":
                opposing_analysis,

            "reasons": reasons,

            "warnings": warnings,

            "analysis_timestamp":
                datetime.now(
                    timezone.utc
                ),
        }

    # ==============================================================
    # BATCH VALIDATION
    # ==============================================================

    def validate_zones(
        self,
        zones: List[Dict[str, Any]],
        candles: List[Dict[str, Any]],
        current_price: Optional[float] = None,
        opposing_zones: Optional[
            List[Dict[str, Any]]
        ] = None,
    ) -> List[Dict[str, Any]]:

        if not isinstance(
            zones,
            list,
        ):
            raise TypeError(
                "zones must be a list."
            )

        results = []

        for zone in zones:

            results.append(
                self.validate_zone(
                    zone=zone,
                    candles=candles,
                    current_price=current_price,
                    opposing_zones=opposing_zones,
                )
            )

        results.sort(
            key=lambda item: (
                -float(item["score"]),
                item["zone_id"] or "",
            )
        )

        return results

    # ==============================================================
    # INPUT VALIDATION
    # ==============================================================

    @staticmethod
    def _validate_zone_input(
        zone: Dict[str, Any],
    ) -> None:

        if not isinstance(
            zone,
            dict,
        ):
            raise TypeError(
                "zone must be a dictionary."
            )

        required = (
            "zone_type",
            "proximal_price",
            "distal_price",
        )

        for field in required:

            if field not in zone:
                raise ValueError(
                    f"Zone missing required field: {field}"
                )

        zone_type = str(
            zone["zone_type"]
        ).upper()

        if zone_type not in (
            "DEMAND",
            "SUPPLY",
        ):
            raise ValueError(
                f"Unsupported zone type: {zone_type}"
            )

        proximal = float(
            zone["proximal_price"]
        )

        distal = float(
            zone["distal_price"]
        )

        if proximal == distal:
            raise ValueError(
                "Zone proximal and distal prices "
                "cannot be equal."
            )

    @staticmethod
    def _validate_candles(
        candles: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:

        result = []

        for candle in candles:

            if not isinstance(
                candle,
                dict,
            ):
                continue

            required = (
                "open",
                "high",
                "low",
                "close",
                "timestamp",
            )

            if any(
                field not in candle
                for field in required
            ):
                continue

            try:
                item = dict(candle)

                item["open"] = float(
                    candle["open"]
                )

                item["high"] = float(
                    candle["high"]
                )

                item["low"] = float(
                    candle["low"]
                )

                item["close"] = float(
                    candle["close"]
                )

                raw_timestamp = candle["timestamp"]

                if hasattr(
                    raw_timestamp,
                    "timestamp",
                ):
                    raw_timestamp = raw_timestamp.timestamp()

                item["timestamp"] = int(
                    raw_timestamp
                )

            except (
                TypeError,
                ValueError,
            ):
                continue

            if item["high"] < item["low"]:
                continue

            if not (
                item["low"]
                <= item["open"]
                <= item["high"]
            ):
                continue

            if not (
                item["low"]
                <= item["close"]
                <= item["high"]
            ):
                continue

            result.append(item)

        result.sort(
            key=lambda x: x["timestamp"]
        )

        return result

    # ==============================================================
    # ZONE TIMING
    # ==============================================================

    @staticmethod
    def _zone_start_timestamp(
        zone: Dict[str, Any],
    ) -> int:

        value = zone.get(
            "base_start_time"
        )

        if isinstance(
            value,
            datetime,
        ):
            return int(
                value.timestamp()
            )

        return int(
            zone.get(
                "base_start_timestamp",
                zone.get(
                    "departure_start_timestamp",
                    0,
                ),
            )
        )

    @staticmethod
    def _zone_end_timestamp(
        zone: Dict[str, Any],
    ) -> int:

        value = zone.get(
            "departure_end_time"
        )

        if isinstance(
            value,
            datetime,
        ):
            return int(
                value.timestamp()
            )

        return int(
            zone.get(
                "departure_end_timestamp",
                zone.get(
                    "timestamp",
                    0,
                ),
            )
        )

    # ==============================================================
    # TOUCH DETECTION
    # ==============================================================

    def _count_touches(
        self,
        lower: float,
        upper: float,
        candles: List[Dict[str, Any]],
    ) -> int:

        if not candles:
            return 0

        tolerance = (
            (upper - lower)
            * self.touch_tolerance
        )

        touches = 0

        for candle in candles:

            high = float(
                candle["high"]
            )

            low = float(
                candle["low"]
            )

            if (
                high >= lower - tolerance
                and low <= upper + tolerance
            ):
                touches += 1

        return touches

    # ==============================================================
    # PENETRATION
    # ==============================================================

    def _calculate_penetration(
        self,
        lower: float,
        upper: float,
        candles: List[Dict[str, Any]],
        zone_type: str,
    ) -> float:

        width = upper - lower

        if width <= 0 or not candles:
            return 0.0

        max_penetration = 0.0

        for candle in candles:

            if zone_type == "DEMAND":

                if candle["low"] < lower:
                    penetration = (
                        lower - candle["low"]
                    ) / width * 100.0
                else:
                    penetration = 0.0

            else:

                if candle["high"] > upper:
                    penetration = (
                        candle["high"] - upper
                    ) / width * 100.0
                else:
                    penetration = 0.0

            max_penetration = max(
                max_penetration,
                penetration,
            )

        return min(
            100.0,
            max_penetration,
        )

    # ==============================================================
    # REJECTION
    # ==============================================================

    def _calculate_rejection(
        self,
        lower: float,
        upper: float,
        candles: List[Dict[str, Any]],
        zone_type: str,
    ) -> float:

        if not candles:
            return 0.0

        reactions = 0
        valid_reactions = 0

        for candle in candles:

            high = float(
                candle["high"]
            )

            low = float(
                candle["low"]
            )

            close = float(
                candle["close"]
            )

            if (
                high < lower
                or low > upper
            ):
                continue

            valid_reactions += 1

            if zone_type == "DEMAND":

                midpoint = (
                    lower + upper
                ) / 2.0

                if close >= midpoint:
                    reactions += 1

            else:

                midpoint = (
                    lower + upper
                ) / 2.0

                if close <= midpoint:
                    reactions += 1

        if valid_reactions == 0:
            return 0.0

        return (
            reactions
            / valid_reactions
            * 100.0
        )

    # ==============================================================
    # INVALIDATION
    # ==============================================================

    def _is_invalidated(
        self,
        lower: float,
        upper: float,
        candles: List[Dict[str, Any]],
        zone_type: str,
    ) -> bool:

        if not candles:
            return False

        buffer = (
            (upper - lower)
            * self.invalidation_buffer
        )

        for candle in candles:

            close = float(
                candle["close"]
            )

            if zone_type == "DEMAND":

                if close < lower - buffer:
                    return True

            else:

                if close > upper + buffer:
                    return True

        return False

    # ==============================================================
    # PRICE LOCATION
    # ==============================================================

    @staticmethod
    def _price_location(
        price: float,
        lower: float,
        upper: float,
    ) -> str:

        width = upper - lower

        if width <= 0:
            return "OUTSIDE"

        tolerance = width * 0.01

        if abs(price - lower) <= tolerance:
            return "AT_DISTAL"

        if abs(price - upper) <= tolerance:
            return "AT_PROXIMAL"

        if lower < price < upper:
            return "INSIDE"

        if price > upper:
            return "ABOVE"

        return "BELOW"

    # ==============================================================
    # QUALITY COMPONENTS
    # ==============================================================

    @staticmethod
    def _departure_quality(
        zone: Dict[str, Any],
    ) -> float:

        return min(
            100.0,
            max(
                0.0,
                float(
                    zone.get(
                        "strength",
                        0.0,
                    )
                ),
            ),
        )

    @staticmethod
    def _base_quality(
        zone: Dict[str, Any],
    ) -> float:

        count = int(
            zone.get(
                "base_candles",
                0,
            )
        )

        if count <= 0:
            return 0.0

        if count == 1:
            return 100.0

        if count == 2:
            return 95.0

        if count == 3:
            return 85.0

        if count == 4:
            return 75.0

        return max(
            50.0,
            100.0 - count * 5.0,
        )

    @staticmethod
    def _directional_quality(
        zone: Dict[str, Any],
    ) -> float:

        departure = int(
            zone.get(
                "departure_candles",
                0,
            )
        )

        if departure <= 0:
            return 0.0

        strength = float(
            zone.get(
                "strength",
                0.0,
            )
        )

        return min(
            100.0,
            max(
                0.0,
                strength,
            ),
        )

    # ==============================================================
    # OPPOSING ZONE ANALYSIS
    # ==============================================================

    @staticmethod
    def _opposing_zone_analysis(
        current_price: float,
        zone: Dict[str, Any],
        opposing_zones: List[Dict[str, Any]],
    ) -> Dict[str, Any]:

        zone_type = str(
            zone["zone_type"]
        ).upper()

        opposing_type = (
            "SUPPLY"
            if zone_type == "DEMAND"
            else "DEMAND"
        )

        candidates = []

        for other in opposing_zones:

            if not isinstance(
                other,
                dict,
            ):
                continue

            if str(
                other.get(
                    "zone_type",
                    "",
                )
            ).upper() != opposing_type:
                continue

            try:
                low = min(
                    float(
                        other["proximal_price"]
                    ),
                    float(
                        other["distal_price"]
                    ),
                )

                high = max(
                    float(
                        other["proximal_price"]
                    ),
                    float(
                        other["distal_price"]
                    ),
                )

            except (
                KeyError,
                TypeError,
                ValueError,
            ):
                continue

            if (
                low
                <= current_price
                <= high
            ):

                candidates.append(
                    {
                        "zone_id": other.get(
                            "zone_id"
                        ),
                        "timeframe": other.get(
                            "timeframe"
                        ),
                        "distance": 0.0,
                    }
                )

                continue

            distance = min(
                abs(
                    current_price - low
                ),
                abs(
                    current_price - high
                ),
            )

            candidates.append(
                {
                    "zone_id": other.get(
                        "zone_id"
                    ),
                    "timeframe": other.get(
                        "timeframe"
                    ),
                    "distance": distance,
                }
            )

        candidates.sort(
            key=lambda x: x["distance"]
        )

        conflict = any(
            item["distance"] == 0.0
            for item in candidates
        )

        nearest = (
            candidates[0]
            if candidates
            else None
        )

        return {
            "opposing_type": opposing_type,
            "conflict": conflict,
            "nearest": nearest,
            "count": len(candidates),
        }

    # ==============================================================
    # SCORE
    # ==============================================================

    @staticmethod
    def _calculate_score(
        zone_strength: float,
        status: str,
        touches: int,
        penetration: float,
        rejection: float,
        departure_quality: float,
        base_quality: float,
        directional_quality: float,
        opposing_conflict: bool,
        invalidated: bool,
    ) -> float:

        if invalidated:
            return 0.0

        score = 0.0

        score += min(
            25.0,
            zone_strength * 0.25,
        )

        score += (
            departure_quality * 0.20
        )

        score += (
            base_quality * 0.15
        )

        score += (
            directional_quality * 0.15
        )

        if status == "FRESH":
            score += 15.0

        elif status == "TESTED":
            score += 10.0

        elif status == "MITIGATED":
            score += 3.0

        score += min(
            10.0,
            rejection * 0.10,
        )

        score -= min(
            20.0,
            penetration * 0.20,
        )

        if opposing_conflict:
            score -= 20.0

        return max(
            0.0,
            min(
                100.0,
                score,
            ),
        )

    # ==============================================================
    # GRADE
    # ==============================================================

    @staticmethod
    def _grade(
        score: float,
        invalidated: bool,
    ) -> str:

        if invalidated:
            return "INVALID"

        if score >= 90:
            return "A+"

        if score >= 80:
            return "A"

        if score >= 70:
            return "B"

        if score >= 60:
            return "C"

        return "INVALID"

    # ==============================================================
    # REASONS
    # ==============================================================

    @staticmethod
    def _build_reasons(
        zone_type: str,
        status: str,
        location: str,
        touches: int,
        penetration: float,
        rejection: float,
        score: float,
        grade: str,
        opposing_analysis: Dict[str, Any],
    ) -> List[str]:

        reasons = []

        reasons.append(
            f"{zone_type} zone classified as {grade}."
        )

        reasons.append(
            f"Zone status: {status}."
        )

        reasons.append(
            f"Current price location: {location}."
        )

        reasons.append(
            f"Detected touches: {touches}."
        )

        reasons.append(
            f"Maximum penetration: "
            f"{penetration:.2f}%."
        )

        reasons.append(
            f"Reaction/rejection: "
            f"{rejection:.2f}%."
        )

        reasons.append(
            f"Validation score: "
            f"{score:.2f}/100."
        )

        if opposing_analysis["conflict"]:
            reasons.append(
                "Current price conflicts with an "
                "opposing zone."
            )
        else:
            reasons.append(
                "No active opposing-zone conflict "
                "at current price."
            )

        return reasons

    @staticmethod
    def _build_warnings(
        invalidated: bool,
        status: str,
        location: str,
        opposing_analysis: Dict[str, Any],
        rejection: float,
        penetration: float,
    ) -> List[str]:

        warnings = []

        if invalidated:
            warnings.append(
                "ZONE INVALIDATED."
            )

        if status == "MITIGATED":
            warnings.append(
                "Zone has multiple historical touches."
            )

        if location == "INSIDE":
            warnings.append(
                "Price is currently inside the zone."
            )

        if opposing_analysis["conflict"]:
            warnings.append(
                "Opposing zone conflict detected."
            )

        if penetration >= 50:
            warnings.append(
                "Significant zone penetration detected."
            )

        if rejection < 20:
            warnings.append(
                "Weak rejection evidence."
            )

        return warnings


__all__ = [
    "ZoneValidationEngine",
]
