"""
SUPPLY & DEMAND MT5
MULTI-TIMEFRAME ZONE CONFLUENCE + BAYESIAN PROBABILITY ENGINE
===============================================================

Version:
    1.1.0

Purpose:
    Combine validated Supply/Demand zones across:

        D1 -> H4 -> H1 -> M15 -> M5

    and calculate Bayesian posterior probabilities for:

        BULLISH
        BEARISH
        NEUTRAL

Rules:
    - REAL MT5 DATA ONLY
    - NO SIMULATION
    - NO HARDCODED MARKET PRICES
    - READ-ONLY
    - NO TRADE EXECUTION
    - NO MT5 execution imports
    - NO order placement
    - NO SMC
    - NO ICT

Architecture:

    REAL MT5 DATA
          |
          v
    SUPPLY/DEMAND DETECTION
          |
          v
    ZONE VALIDATION
          |
          v
    MULTI-TIMEFRAME CONFLUENCE
          |
          v
    BAYESIAN PROBABILITY
          |
          v
    ANALYTICAL DECISION

The Bayesian layer does not execute trades.
It only updates the probability of each directional hypothesis
given the observed market evidence.

Output:
    Pure Python dictionaries.
"""

from __future__ import annotations

from datetime import datetime, timezone
from math import exp
from typing import Any, Dict, List, Optional


class ZoneConfluenceEngine:
    """
    Multi-timeframe Supply/Demand confluence analyzer
    with Bayesian posterior probability estimation.

    Execution remains permanently disabled.
    """

    ENGINE_NAME = (
        "MULTI-TIMEFRAME ZONE CONFLUENCE + BAYESIAN ENGINE"
    )

    VERSION = "1.1.0"

    READ_ONLY = True
    EXECUTION_ENABLED = False
    SIMULATION_ENABLED = False

    TIMEFRAME_ORDER = (
        "D1",
        "H4",
        "H1",
        "M15",
        "M5",
    )

    TIMEFRAME_WEIGHTS = {
        "D1": 5.0,
        "H4": 4.0,
        "H1": 3.0,
        "M15": 2.0,
        "M5": 1.0,
    }

    # Bayesian priors.
    #
    # No directional preference is hardcoded.
    # The three hypotheses begin equally weighted.
    BAYESIAN_PRIORS = {
        "BULLISH": 1.0 / 3.0,
        "BEARISH": 1.0 / 3.0,
        "NEUTRAL": 1.0 / 3.0,
    }

    def __init__(
        self,
        proximity_threshold_percent: float = 1.0,
        minimum_confluence_score: float = 60.0,
        minimum_bayesian_probability: float = 0.60,
        bayesian_temperature: float = 1.0,
    ) -> None:

        if proximity_threshold_percent <= 0:
            raise ValueError(
                "proximity_threshold_percent must be greater than zero."
            )

        if not 0 <= minimum_confluence_score <= 100:
            raise ValueError(
                "minimum_confluence_score must be between 0 and 100."
            )

        if not 0.0 <= minimum_bayesian_probability <= 1.0:
            raise ValueError(
                "minimum_bayesian_probability must be between 0 and 1."
            )

        if bayesian_temperature <= 0:
            raise ValueError(
                "bayesian_temperature must be greater than zero."
            )

        self.proximity_threshold_percent = float(
            proximity_threshold_percent
        )

        self.minimum_confluence_score = float(
            minimum_confluence_score
        )

        self.minimum_bayesian_probability = float(
            minimum_bayesian_probability
        )

        self.bayesian_temperature = float(
            bayesian_temperature
        )

    # ==============================================================
    # PUBLIC API
    # ==============================================================

    def analyze(
        self,
        validated_zones: Dict[str, List[Dict[str, Any]]],
        market_data: Dict[str, List[Dict[str, Any]]],
        symbol: str,
    ) -> Dict[str, Any]:
        """
        Analyze validated zones across all supplied timeframes.

        No trading action is performed.
        """

        symbol = str(symbol).strip()

        if not symbol:
            raise ValueError(
                "symbol cannot be empty."
            )

        if not isinstance(
            validated_zones,
            dict,
        ):
            raise TypeError(
                "validated_zones must be a dictionary."
            )

        if not isinstance(
            market_data,
            dict,
        ):
            raise TypeError(
                "market_data must be a dictionary."
            )

        current_price = self._extract_current_price(
            market_data
        )

        timeframe_analysis: Dict[str, Dict[str, Any]] = {}

        for timeframe in self.TIMEFRAME_ORDER:

            zones = validated_zones.get(
                timeframe,
                [],
            )

            timeframe_analysis[timeframe] = (
                self._analyze_timeframe(
                    zones,
                    timeframe,
                    current_price,
                )
            )

        best_demand = self._best_zone(
            timeframe_analysis,
            "DEMAND",
        )

        best_supply = self._best_zone(
            timeframe_analysis,
            "SUPPLY",
        )

        demand_score = self._side_score(
            timeframe_analysis,
            "DEMAND",
        )

        supply_score = self._side_score(
            timeframe_analysis,
            "SUPPLY",
        )

        alignment = self._calculate_alignment(
            timeframe_analysis
        )

        conflicts = self._detect_conflicts(
            timeframe_analysis
        )

        proximity = self._calculate_proximity(
            best_demand,
            best_supply,
            current_price,
        )

        confluence_score = self._calculate_confluence_score(
            demand_score=demand_score,
            supply_score=supply_score,
            alignment=alignment,
            conflicts=conflicts,
            proximity=proximity,
        )

        deterministic_bias = self._determine_bias(
            demand_score,
            supply_score,
            alignment,
            conflicts,
        )

        bayesian = self._calculate_bayesian_probability(
            timeframe_analysis=timeframe_analysis,
            demand_score=demand_score,
            supply_score=supply_score,
            alignment=alignment,
            conflicts=conflicts,
            proximity=proximity,
            deterministic_bias=deterministic_bias,
        )

        bias = bayesian["posterior_bias"]

        decision = self._determine_decision(
            bias=bias,
            confluence_score=confluence_score,
            conflicts=conflicts,
            best_demand=best_demand,
            best_supply=best_supply,
            current_price=current_price,
            bayesian=bayesian,
        )

        reasons = self._build_reasons(
            bias=bias,
            decision=decision,
            demand_score=demand_score,
            supply_score=supply_score,
            alignment=alignment,
            confluence_score=confluence_score,
            bayesian=bayesian,
        )

        warnings = self._build_warnings(
            conflicts,
            best_demand,
            best_supply,
            current_price,
            bayesian,
        )

        return {
            "engine": self.ENGINE_NAME,
            "version": self.VERSION,
            "symbol": symbol,

            "analysis_timestamp": datetime.now(
                timezone.utc
            ),

            "current_price": current_price,

            # Bayesian result becomes the primary analytical bias.
            "bias": bias,

            # Original deterministic bias retained for transparency.
            "deterministic_bias": deterministic_bias,

            "decision": decision,

            "confidence": round(
                confluence_score,
                2,
            ),

            "demand_score": round(
                demand_score,
                2,
            ),

            "supply_score": round(
                supply_score,
                2,
            ),

            "best_demand": best_demand,

            "best_supply": best_supply,

            "timeframes": timeframe_analysis,

            "confluence": {
                "d1_h4_alignment":
                    alignment["D1_H4"],

                "h4_h1_alignment":
                    alignment["H4_H1"],

                "h1_m15_alignment":
                    alignment["H1_M15"],

                "m15_m5_alignment":
                    alignment["M15_M5"],

                "overall":
                    alignment["overall"],
            },

            "proximity": proximity,

            "conflicts": conflicts,

            # ======================================================
            # BAYESIAN OUTPUT
            # ======================================================

            "bayesian": bayesian,

            "bayesian_probability": (
                bayesian["posterior_probability"]
            ),

            "bayesian_confidence": (
                bayesian["confidence"]
            ),

            "bayesian_evidence_strength": (
                bayesian["evidence_strength"]
            ),

            "reasons": reasons,

            "warnings": warnings,

            "read_only": self.READ_ONLY,

            "execution_enabled":
                self.EXECUTION_ENABLED,

            "simulation_enabled":
                self.SIMULATION_ENABLED,
        }

    # ==============================================================
    # CURRENT PRICE
    # ==============================================================

    @staticmethod
    def _extract_current_price(
        market_data: Dict[str, List[Dict[str, Any]]],
    ) -> float:

        for timeframe in (
            "M5",
            "M15",
            "H1",
            "H4",
            "D1",
        ):

            candles = market_data.get(
                timeframe,
                [],
            )

            if not candles:
                continue

            latest = candles[-1]

            if "close" in latest:

                price = float(
                    latest["close"]
                )

                if price > 0:
                    return price

        raise ValueError(
            "Unable to determine current market price."
        )

    # ==============================================================
    # TIMEFRAME ANALYSIS
    # ==============================================================

    def _analyze_timeframe(
        self,
        zones: List[Dict[str, Any]],
        timeframe: str,
        current_price: float,
    ) -> Dict[str, Any]:

        valid = [
            zone
            for zone in zones
            if isinstance(zone, dict)
            and zone.get("validated") is True
        ]

        demands = [
            zone
            for zone in valid
            if zone.get("zone_type") == "DEMAND"
        ]

        supplies = [
            zone
            for zone in valid
            if zone.get("zone_type") == "SUPPLY"
        ]

        demand_best = self._select_best_zone(
            demands,
            current_price,
        )

        supply_best = self._select_best_zone(
            supplies,
            current_price,
        )

        return {
            "timeframe": timeframe,

            "total_validated": len(valid),

            "demand_count": len(demands),

            "supply_count": len(supplies),

            "best_demand": demand_best,

            "best_supply": supply_best,

            "direction": self._timeframe_direction(
                demand_best,
                supply_best,
                current_price,
            ),
        }

    # ==============================================================
    # BEST ZONE
    # ==============================================================

    @staticmethod
    def _select_best_zone(
        zones: List[Dict[str, Any]],
        current_price: float,
    ) -> Optional[Dict[str, Any]]:

        if not zones:
            return None

        def score(zone: Dict[str, Any]) -> float:

            validation_score = float(
                zone.get(
                    "score",
                    0.0,
                )
            )

            strength = float(
                zone.get(
                    "zone_strength",
                    zone.get(
                        "strength",
                        0.0,
                    ),
                )
            )

            grade_bonus = {
                "A+": 10.0,
                "A": 7.0,
                "B+": 4.0,
                "B": 2.0,
            }.get(
                zone.get("grade"),
                0.0,
            )

            low = float(
                zone.get(
                    "zone_low",
                    zone.get(
                        "distal_price",
                        0.0,
                    ),
                )
            )

            high = float(
                zone.get(
                    "zone_high",
                    zone.get(
                        "proximal_price",
                        0.0,
                    ),
                )
            )

            midpoint = (
                low + high
            ) / 2.0

            distance = abs(
                current_price - midpoint
            )

            proximity_penalty = (
                distance
                / max(current_price, 1.0)
                * 10.0
            )

            return (
                validation_score
                + strength * 0.10
                + grade_bonus
                - proximity_penalty
            )

        return max(
            zones,
            key=score,
        )

    # ==============================================================
    # TIMEFRAME DIRECTION
    # ==============================================================

    @staticmethod
    def _timeframe_direction(
        demand: Optional[Dict[str, Any]],
        supply: Optional[Dict[str, Any]],
        current_price: float,
    ) -> str:

        if demand is None and supply is None:
            return "NEUTRAL"

        demand_score = (
            float(demand.get("score", 0.0))
            if demand
            else 0.0
        )

        supply_score = (
            float(supply.get("score", 0.0))
            if supply
            else 0.0
        )

        if demand_score > supply_score + 5:
            return "BULLISH"

        if supply_score > demand_score + 5:
            return "BEARISH"

        return "MIXED"

    # ==============================================================
    # SIDE SCORE
    # ==============================================================

    def _side_score(
        self,
        timeframe_analysis: Dict[str, Dict[str, Any]],
        side: str,
    ) -> float:

        total = 0.0
        maximum = 0.0

        for timeframe in self.TIMEFRAME_ORDER:

            weight = self.TIMEFRAME_WEIGHTS[
                timeframe
            ]

            maximum += 100.0 * weight

            zone = timeframe_analysis[
                timeframe
            ].get(
                f"best_{side.lower()}",
            )

            if zone is None:
                continue

            score = float(
                zone.get(
                    "score",
                    0.0,
                )
            )

            total += score * weight

        if maximum <= 0:
            return 0.0

        return min(
            100.0,
            (total / maximum) * 100.0,
        )

    # ==============================================================
    # ALIGNMENT
    # ==============================================================

    @staticmethod
    def _pair_alignment(
        first: str,
        second: str,
    ) -> float:

        if (
            first in ("NEUTRAL", "MIXED")
            or second in ("NEUTRAL", "MIXED")
        ):
            return 50.0

        if first == second:
            return 100.0

        return 0.0

    def _calculate_alignment(
        self,
        timeframe_analysis: Dict[str, Dict[str, Any]],
    ) -> Dict[str, float]:

        directions = {
            tf: timeframe_analysis[tf][
                "direction"
            ]
            for tf in self.TIMEFRAME_ORDER
        }

        d1_h4 = self._pair_alignment(
            directions["D1"],
            directions["H4"],
        )

        h4_h1 = self._pair_alignment(
            directions["H4"],
            directions["H1"],
        )

        h1_m15 = self._pair_alignment(
            directions["H1"],
            directions["M15"],
        )

        m15_m5 = self._pair_alignment(
            directions["M15"],
            directions["M5"],
        )

        overall = (
            d1_h4
            + h4_h1
            + h1_m15
            + m15_m5
        ) / 4.0

        return {
            "D1_H4": round(d1_h4, 2),
            "H4_H1": round(h4_h1, 2),
            "H1_M15": round(h1_m15, 2),
            "M15_M5": round(m15_m5, 2),
            "overall": round(overall, 2),
        }

    # ==============================================================
    # CONFLICTS
    # ==============================================================

    @staticmethod
    def _detect_conflicts(
        timeframe_analysis: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:

        conflicts = []

        for timeframe in (
            "D1",
            "H4",
            "H1",
            "M15",
            "M5",
        ):

            direction = timeframe_analysis[
                timeframe
            ]["direction"]

            if direction == "MIXED":

                conflicts.append(
                    {
                        "timeframe": timeframe,
                        "type": "INTERNAL_CONFLICT",
                        "description":
                            "Demand and supply strength are closely balanced.",
                    }
                )

        directions = [
            timeframe_analysis[tf]["direction"]
            for tf in (
                "D1",
                "H4",
                "H1",
                "M15",
                "M5",
            )
        ]

        bullish = directions.count("BULLISH")
        bearish = directions.count("BEARISH")

        if bullish > 0 and bearish > 0:

            conflicts.append(
                {
                    "timeframe": "MULTI_TIMEFRAME",
                    "type": "DIRECTIONAL_CONFLICT",
                    "description":
                        "Higher and lower timeframes are not directionally aligned.",
                }
            )

        return conflicts

    # ==============================================================
    # PROXIMITY
    # ==============================================================

    @staticmethod
    def _zone_distance(
        zone: Optional[Dict[str, Any]],
        current_price: float,
    ) -> Optional[float]:

        if zone is None:
            return None

        low = float(
            zone.get(
                "zone_low",
                zone.get(
                    "distal_price",
                    0.0,
                ),
            )
        )

        high = float(
            zone.get(
                "zone_high",
                zone.get(
                    "proximal_price",
                    0.0,
                ),
            )
        )

        if low <= current_price <= high:
            return 0.0

        if current_price < low:
            return low - current_price

        return current_price - high

    def _calculate_proximity(
        self,
        demand: Optional[Dict[str, Any]],
        supply: Optional[Dict[str, Any]],
        current_price: float,
    ) -> Dict[str, Any]:

        demand_distance = self._zone_distance(
            demand,
            current_price,
        )

        supply_distance = self._zone_distance(
            supply,
            current_price,
        )

        def percent(
            distance: Optional[float],
        ) -> Optional[float]:

            if distance is None:
                return None

            return round(
                distance
                / max(current_price, 1.0)
                * 100.0,
                4,
            )

        return {
            "demand_distance": demand_distance,
            "demand_distance_percent":
                percent(demand_distance),

            "supply_distance": supply_distance,
            "supply_distance_percent":
                percent(supply_distance),
        }

    # ==============================================================
    # CONFLUENCE SCORE
    # ==============================================================

    @staticmethod
    def _calculate_confluence_score(
        demand_score: float,
        supply_score: float,
        alignment: Dict[str, float],
        conflicts: List[Dict[str, Any]],
        proximity: Dict[str, Any],
    ) -> float:

        directional_strength = max(
            demand_score,
            supply_score,
        )

        alignment_score = float(
            alignment["overall"]
        )

        conflict_penalty = min(
            30.0,
            len(conflicts) * 10.0,
        )

        proximity_values = [
            value
            for key, value in proximity.items()
            if key.endswith("_percent")
            and value is not None
        ]

        if proximity_values:

            nearest = min(
                proximity_values
            )

            proximity_score = max(
                0.0,
                100.0 - nearest * 20.0,
            )

        else:
            proximity_score = 0.0

        raw = (
            directional_strength * 0.45
            + alignment_score * 0.35
            + proximity_score * 0.20
            - conflict_penalty
        )

        return round(
            max(
                0.0,
                min(
                    100.0,
                    raw,
                ),
            ),
            2,
        )

    # ==============================================================
    # DETERMINISTIC BIAS
    # ==============================================================

    @staticmethod
    def _determine_bias(
        demand_score: float,
        supply_score: float,
        alignment: Dict[str, float],
        conflicts: List[Dict[str, Any]],
    ) -> str:

        difference = (
            demand_score
            - supply_score
        )

        if (
            abs(difference) < 10.0
            or alignment["overall"] < 50.0
        ):
            return "NEUTRAL"

        if difference > 0:
            return "BULLISH"

        return "BEARISH"

    # ==============================================================
    # BAYESIAN PROBABILITY
    # ==============================================================

    def _calculate_bayesian_probability(
        self,
        timeframe_analysis: Dict[str, Dict[str, Any]],
        demand_score: float,
        supply_score: float,
        alignment: Dict[str, float],
        conflicts: List[Dict[str, Any]],
        proximity: Dict[str, Any],
        deterministic_bias: str,
    ) -> Dict[str, Any]:
        """
        Bayesian posterior estimator.

        The engine starts from neutral priors and updates them
        using independent evidence factors.

        Evidence is converted into likelihood ratios.

        Posterior(H | E) is proportional to:

            Prior(H) * Likelihood(E | H)

        Because several evidence factors are used, log-likelihood
        accumulation is used internally for numerical stability.
        """

        hypotheses = (
            "BULLISH",
            "BEARISH",
            "NEUTRAL",
        )

        log_scores = {}

        for hypothesis in hypotheses:

            prior = self.BAYESIAN_PRIORS[
                hypothesis
            ]

            log_score = self._safe_log(
                prior
            )

            # ------------------------------------------------------
            # 1. Demand vs Supply Evidence
            # ------------------------------------------------------

            directional_difference = (
                demand_score
                - supply_score
            )

            directional_strength = min(
                1.0,
                abs(
                    directional_difference
                ) / 100.0,
            )

            if hypothesis == "BULLISH":

                likelihood = (
                    0.50
                    + 0.45
                    * (
                        max(
                            directional_difference,
                            0.0,
                        ) / 100.0
                    )
                )

            elif hypothesis == "BEARISH":

                likelihood = (
                    0.50
                    + 0.45
                    * (
                        max(
                            -directional_difference,
                            0.0,
                        ) / 100.0
                    )
                )

            else:

                likelihood = (
                    0.50
                    + 0.40
                    * (
                        1.0
                        - directional_strength
                    )
                )

            log_score += self._safe_log(
                likelihood
            )

            # ------------------------------------------------------
            # 2. Multi-Timeframe Alignment
            # ------------------------------------------------------

            alignment_strength = (
                alignment["overall"] / 100.0
            )

            if hypothesis == "BULLISH":

                bullish_count = sum(
                    1
                    for tf in self.TIMEFRAME_ORDER
                    if timeframe_analysis[tf][
                        "direction"
                    ] == "BULLISH"
                )

                evidence = (
                    bullish_count
                    / len(self.TIMEFRAME_ORDER)
                )

                likelihood = (
                    0.50
                    + 0.45
                    * evidence
                    * alignment_strength
                )

            elif hypothesis == "BEARISH":

                bearish_count = sum(
                    1
                    for tf in self.TIMEFRAME_ORDER
                    if timeframe_analysis[tf][
                        "direction"
                    ] == "BEARISH"
                )

                evidence = (
                    bearish_count
                    / len(self.TIMEFRAME_ORDER)
                )

                likelihood = (
                    0.50
                    + 0.45
                    * evidence
                    * alignment_strength
                )

            else:

                mixed_count = sum(
                    1
                    for tf in self.TIMEFRAME_ORDER
                    if timeframe_analysis[tf][
                        "direction"
                    ] in (
                        "MIXED",
                        "NEUTRAL",
                    )
                )

                evidence = (
                    mixed_count
                    / len(self.TIMEFRAME_ORDER)
                )

                likelihood = (
                    0.50
                    + 0.40
                    * evidence
                )

            log_score += self._safe_log(
                likelihood
            )

            # ------------------------------------------------------
            # 3. Proximity Evidence
            # ------------------------------------------------------

            demand_distance = (
                proximity.get(
                    "demand_distance_percent"
                )
            )

            supply_distance = (
                proximity.get(
                    "supply_distance_percent"
                )
            )

            if hypothesis == "BULLISH":

                proximity_evidence = (
                    self._proximity_evidence(
                        demand_distance
                    )
                )

                likelihood = (
                    0.50
                    + 0.40
                    * proximity_evidence
                )

            elif hypothesis == "BEARISH":

                proximity_evidence = (
                    self._proximity_evidence(
                        supply_distance
                    )
                )

                likelihood = (
                    0.50
                    + 0.40
                    * proximity_evidence
                )

            else:

                distances = [
                    x
                    for x in (
                        demand_distance,
                        supply_distance,
                    )
                    if x is not None
                ]

                if distances:

                    nearest = min(
                        distances
                    )

                    neutrality = min(
                        1.0,
                        nearest / 3.0,
                    )

                else:

                    neutrality = 0.5

                likelihood = (
                    0.50
                    + 0.30
                    * neutrality
                )

            log_score += self._safe_log(
                likelihood
            )

            # ------------------------------------------------------
            # 4. Conflict Evidence
            # ------------------------------------------------------

            conflict_count = len(
                conflicts
            )

            conflict_strength = min(
                1.0,
                conflict_count / 3.0,
            )

            if hypothesis in (
                "BULLISH",
                "BEARISH",
            ):

                likelihood = (
                    0.85
                    - 0.40
                    * conflict_strength
                )

            else:

                likelihood = (
                    0.50
                    + 0.45
                    * conflict_strength
                )

            log_score += self._safe_log(
                likelihood
            )

            # ------------------------------------------------------
            # 5. Deterministic Bias Agreement
            # ------------------------------------------------------

            if hypothesis == deterministic_bias:

                likelihood = 0.75

            elif (
                deterministic_bias == "NEUTRAL"
                and hypothesis == "NEUTRAL"
            ):

                likelihood = 0.75

            elif (
                deterministic_bias == "NEUTRAL"
            ):

                likelihood = 0.55

            else:

                likelihood = 0.35

            log_score += self._safe_log(
                likelihood
            )

            log_scores[hypothesis] = (
                log_score
            )

        # ----------------------------------------------------------
        # Normalize posterior probabilities.
        # ----------------------------------------------------------

        max_log = max(
            log_scores.values()
        )

        exponential_scores = {
            hypothesis:
                exp(
                    (
                        value
                        - max_log
                    )
                    / self.bayesian_temperature
                )
            for hypothesis, value
            in log_scores.items()
        }

        denominator = sum(
            exponential_scores.values()
        )

        posterior = {
            hypothesis:
                exponential_scores[hypothesis]
                / denominator
            for hypothesis in hypotheses
        }

        posterior_bias = max(
            posterior,
            key=posterior.get,
        )

        highest_probability = posterior[
            posterior_bias
        ]

        second_probability = sorted(
            posterior.values(),
            reverse=True,
        )[1]

        probability_margin = (
            highest_probability
            - second_probability
        )

        evidence_strength = (
            highest_probability
            * 100.0
        )

        confidence = (
            highest_probability
            * 100.0
        )

        return {
            "method": "BAYESIAN_POSTERIOR",

            "prior_probability": {
                key: round(value, 6)
                for key, value
                in self.BAYESIAN_PRIORS.items()
            },

            "posterior_probability": {
                key: round(value, 6)
                for key, value
                in posterior.items()
            },

            "posterior_bias":
                posterior_bias,

            "confidence":
                round(confidence, 2),

            "evidence_strength":
                round(evidence_strength, 2),

            "probability_margin":
                round(
                    probability_margin,
                    6,
                ),

            "highest_probability":
                round(
                    highest_probability,
                    6,
                ),

            "second_highest_probability":
                round(
                    second_probability,
                    6,
                ),

            "deterministic_bias":
                deterministic_bias,

            "bayesian_threshold":
                self.minimum_bayesian_probability,

            "temperature":
                self.bayesian_temperature,

            "hypothesis":
                posterior_bias,

            "sufficient_probability":
                highest_probability
                >= self.minimum_bayesian_probability,

            "interpretation":
                self._interpret_bayesian_result(
                    posterior,
                    probability_margin,
                ),
        }

    # ==============================================================
    # BAYESIAN HELPERS
    # ==============================================================

    @staticmethod
    def _safe_log(
        value: float,
    ) -> float:

        value = max(
            min(
                float(value),
                0.999999,
            ),
            0.000001,
        )

        # Natural logarithm without importing
        # additional statistical libraries.
        from math import log

        return log(value)

    @staticmethod
    def _proximity_evidence(
        distance_percent: Optional[float],
    ) -> float:

        if distance_percent is None:
            return 0.0

        if distance_percent <= 0:
            return 1.0

        if distance_percent >= 3.0:
            return 0.0

        return max(
            0.0,
            1.0
            - (
                distance_percent
                / 3.0
            ),
        )

    @staticmethod
    def _interpret_bayesian_result(
        posterior: Dict[str, float],
        margin: float,
    ) -> str:

        bullish = posterior[
            "BULLISH"
        ]

        bearish = posterior[
            "BEARISH"
        ]

        neutral = posterior[
            "NEUTRAL"
        ]

        if (
            bullish >= 0.75
            and bullish > bearish
            and bullish > neutral
        ):

            return (
                "Strong posterior bullish evidence."
            )

        if (
            bearish >= 0.75
            and bearish > bullish
            and bearish > neutral
        ):

            return (
                "Strong posterior bearish evidence."
            )

        if (
            neutral >= 0.60
            and neutral > bullish
            and neutral > bearish
        ):

            return (
                "Posterior evidence favors neutrality."
            )

        if margin < 0.10:

            return (
                "Posterior probabilities are closely "
                "balanced; directional evidence is weak."
            )

        if bullish > bearish:

            return (
                "Posterior evidence favors bullish "
                "conditions, but probability is not "
                "strong enough for high-certainty classification."
            )

        if bearish > bullish:

            return (
                "Posterior evidence favors bearish "
                "conditions, but probability is not "
                "strong enough for high-certainty classification."
            )

        return (
            "Posterior evidence remains inconclusive."
        )

    # ==============================================================
    # DECISION
    # ==============================================================

    def _determine_decision(
        self,
        bias: str,
        confluence_score: float,
        conflicts: List[Dict[str, Any]],
        best_demand: Optional[Dict[str, Any]],
        best_supply: Optional[Dict[str, Any]],
        current_price: float,
        bayesian: Dict[str, Any],
    ) -> str:

        probability = (
            bayesian[
                "posterior_probability"
            ].get(
                bias,
                0.0,
            )
        )

        if bias == "NEUTRAL":
            return "NO_TRADE"

        if confluence_score < (
            self.minimum_confluence_score
        ):
            return "NO_TRADE"

        if conflicts:
            return "NO_TRADE"

        if probability < (
            self.minimum_bayesian_probability
        ):
            return "NO_TRADE"

        if bias == "BULLISH":

            if best_demand is None:
                return "NO_TRADE"

            return "BULLISH_BIAS"

        if bias == "BEARISH":

            if best_supply is None:
                return "NO_TRADE"

            return "BEARISH_BIAS"

        return "NO_TRADE"

    # ==============================================================
    # BEST ZONE
    # ==============================================================

    @staticmethod
    def _best_zone(
        timeframe_analysis: Dict[str, Dict[str, Any]],
        side: str,
    ) -> Optional[Dict[str, Any]]:

        candidates = []

        key = f"best_{side.lower()}"

        for timeframe in (
            "D1",
            "H4",
            "H1",
            "M15",
            "M5",
        ):

            zone = timeframe_analysis[
                timeframe
            ].get(key)

            if zone is not None:

                item = dict(zone)

                item["_timeframe_weight"] = (
                    ZoneConfluenceEngine
                    .TIMEFRAME_WEIGHTS[
                        timeframe
                    ]
                )

                candidates.append(item)

        if not candidates:
            return None

        return max(
            candidates,
            key=lambda z: (
                float(
                    z.get(
                        "score",
                        0.0,
                    )
                )
                * float(
                    z[
                        "_timeframe_weight"
                    ]
                )
            ),
        )

    # ==============================================================
    # REASONS
    # ==============================================================

    @staticmethod
    def _build_reasons(
        bias: str,
        decision: str,
        demand_score: float,
        supply_score: float,
        alignment: Dict[str, float],
        confluence_score: float,
        bayesian: Dict[str, Any],
    ) -> List[str]:

        posterior = (
            bayesian[
                "posterior_probability"
            ]
        )

        reasons = [
            f"Bayesian posterior bias: {bias}.",

            (
                "Bayesian probabilities: "
                f"BULLISH={posterior['BULLISH']:.4f}, "
                f"BEARISH={posterior['BEARISH']:.4f}, "
                f"NEUTRAL={posterior['NEUTRAL']:.4f}."
            ),

            (
                "Bayesian confidence: "
                f"{bayesian['confidence']:.2f}%."
            ),

            f"Demand score: {demand_score:.2f}/100.",

            f"Supply score: {supply_score:.2f}/100.",

            (
                "Multi-timeframe alignment: "
                f"{alignment['overall']:.2f}/100."
            ),

            (
                "Overall confluence score: "
                f"{confluence_score:.2f}/100."
            ),

            (
                "Bayesian interpretation: "
                f"{bayesian['interpretation']}"
            ),

            f"Strategy decision: {decision}.",
        ]

        return reasons

    # ==============================================================
    # WARNINGS
    # ==============================================================

    @staticmethod
    def _build_warnings(
        conflicts: List[Dict[str, Any]],
        demand: Optional[Dict[str, Any]],
        supply: Optional[Dict[str, Any]],
        current_price: float,
        bayesian: Dict[str, Any],
    ) -> List[str]:

        warnings = []

        if conflicts:

            warnings.append(
                "Multi-timeframe or internal zone conflict detected."
            )

        if demand is None:

            warnings.append(
                "No validated demand zone available."
            )

        if supply is None:

            warnings.append(
                "No validated supply zone available."
            )

        if demand is not None:

            demand_distance = abs(
                current_price
                - float(
                    demand.get(
                        "proximal_price",
                        current_price,
                    )
                )
            )

            if demand_distance > (
                current_price * 0.03
            ):

                warnings.append(
                    "Best demand zone is relatively far from current price."
                )

        if supply is not None:

            supply_distance = abs(
                current_price
                - float(
                    supply.get(
                        "proximal_price",
                        current_price,
                    )
                )
            )

            if supply_distance > (
                current_price * 0.03
            ):

                warnings.append(
                    "Best supply zone is relatively far from current price."
                )

        if (
            bayesian["confidence"]
            < 60.0
        ):

            warnings.append(
                "Bayesian posterior confidence is below 60%."
            )

        if (
            bayesian["probability_margin"]
            < 0.10
        ):

            warnings.append(
                "Bayesian posterior probabilities are closely balanced."
            )

        return warnings


__all__ = [
    "ZoneConfluenceEngine",
]
