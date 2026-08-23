"""
SUPPLY & DEMAND MT5
AUTOMATIC FORECAST GENERATION / LIFECYCLE REGISTRATION ENGINE
===============================================================

Version: 1.0.0

Purpose:
    Execute the complete read-only analytical forecast pipeline:

        REAL MT5 DATA
            ->
        SUPPLY / DEMAND
            ->
        ZONE VALIDATION
            ->
        ZONE CONFLUENCE
            ->
        BAYESIAN FORECAST
            ->
        CALIBRATION RECORD
            ->
        LIFECYCLE REGISTRATION

Rules:
    - REAL MT5 DATA ONLY
    - READ-ONLY
    - NO ORDER PLACEMENT
    - NO EXECUTION IMPORTS
    - NO SIMULATION
    - NO HARDCODED MARKET PRICES

This engine creates analytical forecasts only.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict


class AutomaticForecastEngine:

    ENGINE_NAME = (
        "AUTOMATIC FORECAST GENERATION / "
        "LIFECYCLE REGISTRATION ENGINE"
    )

    VERSION = "1.0.0"

    READ_ONLY_TRADING = True
    EXECUTION_ENABLED = False
    SIMULATION_ENABLED = False

    def __init__(
        self,
        market_data: Any,
        supply_demand: Any,
        zone_validation: Any,
        zone_confluence: Any,
        calibration: Any,
        lifecycle: Any,
    ) -> None:

        dependencies = {
            "market_data": market_data,
            "supply_demand": supply_demand,
            "zone_validation": zone_validation,
            "zone_confluence": zone_confluence,
            "calibration": calibration,
            "lifecycle": lifecycle,
        }

        for name, dependency in dependencies.items():
            if dependency is None:
                raise ValueError(
                    f"{name} dependency is required."
                )

        self.market_data = market_data
        self.supply_demand = supply_demand
        self.zone_validation = zone_validation
        self.zone_confluence = zone_confluence
        self.calibration = calibration
        self.lifecycle = lifecycle

    # ==============================================================
    # ENGINE STATUS
    # ==============================================================

    def get_engine_status(self) -> Dict[str, Any]:

        return {
            "engine": self.ENGINE_NAME,
            "version": self.VERSION,
            "read_only_trading":
                self.READ_ONLY_TRADING,
            "execution_enabled":
                self.EXECUTION_ENABLED,
            "simulation_enabled":
                self.SIMULATION_ENABLED,
            "timestamp":
                datetime.now(
                    timezone.utc
                ).isoformat(),
        }

    # ==============================================================
    # GENERATE FORECAST
    # ==============================================================

    def generate_forecast(
        self,
        symbol: str,
        bars: int = 200,
    ) -> Dict[str, Any]:

        symbol = str(symbol).strip().upper()

        if not symbol:
            raise ValueError(
                "symbol is required."
            )

        bars = max(1, int(bars))

        # ----------------------------------------------------------
        # 1. REAL MT5 DATA
        # ----------------------------------------------------------

        data = self.market_data.get_top_down_data(
            symbol,
            bars,
        )

        timeframe_order = tuple(
            self.zone_confluence.TIMEFRAME_ORDER
        )

        missing = [
            timeframe
            for timeframe in timeframe_order
            if not data.get(timeframe)
        ]

        if missing:
            raise RuntimeError(
                "Missing real MT5 timeframe data: "
                + ", ".join(missing)
            )

        # ----------------------------------------------------------
        # 2. RAW SUPPLY / DEMAND ZONES
        # ----------------------------------------------------------

        raw_zones = {
            timeframe:
                self.supply_demand.detect_zones(
                    data[timeframe],
                    symbol,
                    timeframe,
                )
            for timeframe in timeframe_order
        }

        # ----------------------------------------------------------
        # 3. VALIDATED ZONES
        # ----------------------------------------------------------

        validated_zones = {
            timeframe:
                self.zone_validation.validate_zones(
                    raw_zones[timeframe],
                    data[timeframe],
                )
            for timeframe in timeframe_order
        }

        # ----------------------------------------------------------
        # 4. MULTI-TIMEFRAME CONFLUENCE / BAYESIAN ANALYSIS
        # ----------------------------------------------------------

        analysis = self.zone_confluence.analyze(
            validated_zones,
            data,
            symbol,
        )

        if not isinstance(analysis, dict):
            raise RuntimeError(
                "ZoneConfluenceEngine returned "
                "an invalid analysis."
            )

        # ----------------------------------------------------------
        # 5. RECORD BAYESIAN FORECAST
        # ----------------------------------------------------------

        forecast = self.calibration.record_forecast(
            analysis
        )

        forecast_id = forecast["forecast_id"]

        # ----------------------------------------------------------
        # 6. LIFECYCLE STATUS
        # ----------------------------------------------------------

        lifecycle_status = self.lifecycle.get_status(
            forecast_id
        )

        # ----------------------------------------------------------
        # 7. RETURN COMPLETE PIPELINE RESULT
        # ----------------------------------------------------------

        return {
            "status": "FORECAST_GENERATED",

            "engine": self.ENGINE_NAME,
            "version": self.VERSION,

            "symbol": symbol,

            "forecast_id": forecast_id,

            "current_price":
                analysis.get(
                    "current_price"
                ),

            "deterministic_bias":
                analysis.get(
                    "deterministic_bias"
                ),

            "bayesian_bias":
                analysis.get(
                    "bias"
                ),

            "posterior_probability":
                analysis.get(
                    "bayesian_probability"
                ),

            "bayesian_confidence":
                analysis.get(
                    "bayesian_confidence"
                ),

            "decision":
                analysis.get(
                    "decision"
                ),

            "confluence":
                analysis.get(
                    "confluence"
                ),

            "proximity":
                analysis.get(
                    "proximity"
                ),

            "conflicts":
                analysis.get(
                    "conflicts"
                ),

            "warnings":
                analysis.get(
                    "warnings"
                ),

            "execution_enabled":
                self.EXECUTION_ENABLED,

            "forecast":
                forecast,

            "lifecycle":
                lifecycle_status,

            "data_counts": {
                timeframe:
                    len(data[timeframe])
                for timeframe in timeframe_order
            },

            "raw_zone_counts": {
                timeframe:
                    len(raw_zones[timeframe])
                for timeframe in timeframe_order
            },

            "validated_zone_counts": {
                timeframe:
                    len(validated_zones[timeframe])
                for timeframe in timeframe_order
            },

            "timestamp":
                datetime.now(
                    timezone.utc
                ).isoformat(),
        }


__all__ = [
    "AutomaticForecastEngine",
]
