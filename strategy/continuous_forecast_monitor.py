"""
SUPPLY & DEMAND MT5
CONTINUOUS FORECAST MONITOR / AUTOMATIC RESOLUTION ENGINE
============================================================

Version: 1.0.0

Purpose:
    Monitor pending Bayesian forecasts and automatically resolve
    them using fresh REAL MT5 market data after the configured
    observation horizon.

Rules:
    - REAL MT5 DATA ONLY
    - READ-ONLY
    - NO ORDER PLACEMENT
    - NO EXECUTION IMPORTS
    - NO SIMULATION
    - NO HARDCODED MARKET PRICES

This engine does NOT create trades.
It only observes and resolves analytical forecasts.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List


class ContinuousForecastMonitor:

    ENGINE_NAME = (
        "CONTINUOUS FORECAST MONITOR / "
        "AUTOMATIC RESOLUTION ENGINE"
    )

    VERSION = "1.0.0"

    READ_ONLY_TRADING = True
    EXECUTION_ENABLED = False
    SIMULATION_ENABLED = False

    DEFAULT_TIMEFRAME = "M5"
    DEFAULT_HORIZON_MINUTES = 15

    def __init__(
        self,
        calibration_engine: Any,
        lifecycle_engine: Any,
        market_data: Any,
        horizon_minutes: int = DEFAULT_HORIZON_MINUTES,
        timeframe: str = DEFAULT_TIMEFRAME,
    ) -> None:

        if calibration_engine is None:
            raise ValueError(
                "calibration_engine is required."
            )

        if lifecycle_engine is None:
            raise ValueError(
                "lifecycle_engine is required."
            )

        if market_data is None:
            raise ValueError(
                "market_data is required."
            )

        self.calibration_engine = calibration_engine
        self.lifecycle_engine = lifecycle_engine
        self.market_data = market_data

        self.horizon_minutes = int(
            horizon_minutes
        )

        if self.horizon_minutes <= 0:
            raise ValueError(
                "horizon_minutes must be positive."
            )

        self.timeframe = str(
            timeframe
        ).upper().strip()

        if not self.timeframe:
            raise ValueError(
                "timeframe is required."
            )

    # ==============================================================
    # STATUS
    # ==============================================================

    def get_engine_status(
        self,
    ) -> Dict[str, Any]:

        return {
            "engine": self.ENGINE_NAME,
            "version": self.VERSION,
            "read_only_trading":
                self.READ_ONLY_TRADING,
            "execution_enabled":
                self.EXECUTION_ENABLED,
            "simulation_enabled":
                self.SIMULATION_ENABLED,
            "timeframe":
                self.timeframe,
            "horizon_minutes":
                self.horizon_minutes,
            "timestamp":
                datetime.now(
                    timezone.utc
                ).isoformat(),
        }

    # ==============================================================
    # PENDING FORECASTS
    # ==============================================================

    def get_pending_forecasts(
        self,
        symbol: str | None = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:

        forecasts = (
            self.calibration_engine
            .get_recent_forecasts(
                symbol=symbol,
                limit=limit,
            )
        )

        return [
            forecast
            for forecast in forecasts
            if not forecast.get(
                "resolved_outcome"
            )
        ]

    # ==============================================================
    # FORECAST AGE
    # ==============================================================

    @staticmethod
    def _forecast_age_minutes(
        timestamp: str,
    ) -> float:

        forecast_time = datetime.fromisoformat(
            str(timestamp)
        )

        if forecast_time.tzinfo is None:
            forecast_time = forecast_time.replace(
                tzinfo=timezone.utc
            )

        now = datetime.now(
            timezone.utc
        )

        return (
            now - forecast_time
        ).total_seconds() / 60.0

    # ==============================================================
    # PROCESS ONE FORECAST
    # ==============================================================

    def process_forecast(
        self,
        forecast_id: int,
    ) -> Dict[str, Any]:

        forecast = (
            self.calibration_engine
            .get_forecast(
                int(forecast_id)
            )
        )

        if forecast is None:
            return {
                "status": "NOT_FOUND",
                "forecast_id": int(
                    forecast_id
                ),
            }

        if forecast.get(
            "resolved_outcome"
        ):

            return {
                "status": "ALREADY_RESOLVED",
                "forecast_id": int(
                    forecast_id
                ),
                "outcome":
                    forecast.get(
                        "resolved_outcome"
                    ),
            }

        age_minutes = (
            self._forecast_age_minutes(
                forecast["timestamp"]
            )
        )

        if age_minutes < self.horizon_minutes:

            return {
                "status": "WAITING",
                "forecast_id": int(
                    forecast_id
                ),
                "age_minutes":
                    round(
                        age_minutes,
                        3,
                    ),
                "required_minutes":
                    self.horizon_minutes,
                "remaining_minutes":
                    round(
                        self.horizon_minutes
                        - age_minutes,
                        3,
                    ),
            }

        # ----------------------------------------------------------
        # Resolve only from REAL MT5 data
        # ----------------------------------------------------------

        result = (
            self.lifecycle_engine
            .resolve_from_mt5(
                forecast_id=int(
                    forecast_id
                ),
                timeframe=self.timeframe,
            )
        )

        result["age_minutes"] = round(
            age_minutes,
            3,
        )

        result["horizon_minutes"] = (
            self.horizon_minutes
        )

        return result

    # ==============================================================
    # PROCESS ALL PENDING
    # ==============================================================

    def process_pending(
        self,
        symbol: str | None = None,
        limit: int = 100,
    ) -> Dict[str, Any]:

        pending = self.get_pending_forecasts(
            symbol=symbol,
            limit=limit,
        )

        results = []

        for forecast in pending:

            results.append(
                self.process_forecast(
                    forecast["forecast_id"]
                )
            )

        resolved = sum(
            1
            for result in results
            if result.get("status")
            == "RESOLVED"
        )

        waiting = sum(
            1
            for result in results
            if result.get("status")
            == "WAITING"
        )

        return {
            "status": "MONITOR_COMPLETE",
            "symbol": symbol,
            "pending_before": len(
                pending
            ),
            "resolved": resolved,
            "waiting": waiting,
            "results": results,
            "execution_enabled":
                self.EXECUTION_ENABLED,
            "timestamp":
                datetime.now(
                    timezone.utc
                ).isoformat(),
        }


__all__ = [
    "ContinuousForecastMonitor",
]
