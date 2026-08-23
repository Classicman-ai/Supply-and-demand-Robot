"""
SUPPLY & DEMAND MT5
AUTOMATIC FORECAST SCHEDULER / ORCHESTRATOR
============================================

Version: 1.0.0

Purpose:
    Coordinate the complete read-only forecast lifecycle.

Pipeline:
    REAL MT5 DATA
        -> STRATEGY ANALYSIS
        -> FORECAST GENERATION
        -> FORECAST REGISTRATION
        -> CONTINUOUS MONITOR
        -> AUTOMATIC RESOLUTION
        -> CALIBRATION HISTORY

Rules:
    - REAL MT5 DATA ONLY
    - READ-ONLY
    - NO ORDER PLACEMENT
    - NO EXECUTION IMPORTS
    - NO SIMULATION
    - NO HARDCODED MARKET PRICES
    - DUPLICATE FORECAST PROTECTION
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForecastScheduler:

    ENGINE_NAME = (
        "AUTOMATIC FORECAST SCHEDULER / ORCHESTRATOR"
    )
    VERSION = "1.0.0"

    READ_ONLY_TRADING = True
    EXECUTION_ENABLED = False
    SIMULATION_ENABLED = False

    def __init__(
        self,
        market_data: Any,
        forecast_generator: Any,
        calibration_engine: Any,
        lifecycle_engine: Any,
        monitor_engine: Any,
        symbol: str,
        timeframe: str = "M5",
        minimum_interval_minutes: int = 5,
    ) -> None:

        if market_data is None:
            raise ValueError("market_data is required.")

        if forecast_generator is None:
            raise ValueError(
                "forecast_generator is required."
            )

        if calibration_engine is None:
            raise ValueError(
                "calibration_engine is required."
            )

        if lifecycle_engine is None:
            raise ValueError(
                "lifecycle_engine is required."
            )

        if monitor_engine is None:
            raise ValueError(
                "monitor_engine is required."
            )

        self.market_data = market_data
        self.forecast_generator = forecast_generator
        self.calibration_engine = calibration_engine
        self.lifecycle_engine = lifecycle_engine
        self.monitor_engine = monitor_engine

        self.symbol = str(symbol).strip().upper()
        self.timeframe = str(timeframe).strip().upper()

        if not self.symbol:
            raise ValueError("symbol cannot be empty.")

        if not self.timeframe:
            raise ValueError("timeframe cannot be empty.")

        self.minimum_interval_minutes = max(
            1,
            int(minimum_interval_minutes),
        )

        self._last_forecast_timestamp: Optional[datetime] = None
        self._last_market_timestamp: Optional[str] = None
        self._last_forecast_id: Optional[int] = None

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
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "minimum_interval_minutes":
                self.minimum_interval_minutes,
            "timestamp":
                datetime.now(
                    timezone.utc
                ).isoformat(),
        }

    # ==============================================================
    # REAL MT5 DATA
    # ==============================================================

    def _get_latest_market_data(
        self,
    ) -> Dict[str, Any]:

        data = self.market_data.get_top_down_data(
            self.symbol,
            200,
        )

        candles = data.get(
            self.timeframe,
            [],
        )

        if not candles:
            raise RuntimeError(
                f"No REAL MT5 {self.timeframe} "
                f"data available for {self.symbol}."
            )

        latest = candles[-1]

        if "close" not in latest:
            raise RuntimeError(
                "Latest MT5 candle does not contain close."
            )

        price = float(latest["close"])

        if price <= 0:
            raise RuntimeError(
                "Invalid MT5 market price."
            )

        market_timestamp = str(
            latest.get(
                "time",
                latest.get(
                    "timestamp",
                    "",
                ),
            )
        )

        return {
            "data": data,
            "candles": candles,
            "latest": latest,
            "price": price,
            "market_timestamp":
                market_timestamp,
        }

    # ==============================================================
    # DUPLICATE PROTECTION
    # ==============================================================

    def _has_duplicate_forecast(
        self,
        market_timestamp: str,
    ) -> bool:

        recent = self.calibration_engine.get_recent_forecasts(
            symbol=self.symbol,
            limit=20,
        )

        for forecast in recent:

            if str(
                forecast.get("metadata", {})
            ).find(
                market_timestamp
            ) >= 0:
                return True

        return False

    # ==============================================================
    # FORECAST GENERATION
    # ==============================================================

    def process_pending(
        self,
    ) -> Dict[str, Any]:
        """
        Delegate pending forecast resolution to the
        ContinuousForecastMonitor.

        The scheduler orchestrates; the monitor owns
        forecast observation and lifecycle resolution.
        """

        if self.monitor_engine is None:
            return {
                "status": "MONITOR_UNAVAILABLE",
                "symbol": self.symbol,
                "resolved": 0,
                "waiting": 0,
                "results": [],
                "execution_enabled":
                    self.EXECUTION_ENABLED,
            }

        result = self.monitor_engine.process_pending(
            symbol=self.symbol,
            limit=100,
        )

        if not isinstance(result, dict):
            raise RuntimeError(
                "Forecast monitor returned "
                "an invalid result."
            )

        return result

    def generate_forecast(
        self,
    ) -> Dict[str, Any]:

        market = self._get_latest_market_data()

        market_timestamp = market[
            "market_timestamp"
        ]

        if self._has_duplicate_forecast(
            market_timestamp
        ):
            return {
                "status":
                    "DUPLICATE_BLOCKED",
                "symbol":
                    self.symbol,
                "market_timestamp":
                    market_timestamp,
                "price":
                    market["price"],
                "execution_enabled":
                    self.EXECUTION_ENABLED,
            }

        # ==========================================================
        # AUTOMATIC FORECAST ENGINE CONTRACT
        # ==========================================================
        # AutomaticForecastEngine.generate_forecast() is already
        # responsible for:
        #   1. strategy analysis
        #   2. Bayesian recording
        #   3. forecast_id creation
        #   4. lifecycle registration
        #
        # The scheduler MUST consume that result rather than
        # attempting a second calibration record.
        # ==========================================================

        analysis = self.forecast_generator.generate_forecast(
            self.symbol,
            200,
        )

        if not isinstance(analysis, dict):
            raise RuntimeError(
                "Automatic forecast engine returned "
                "an invalid result."
            )

        if analysis.get("status") != "FORECAST_GENERATED":
            raise RuntimeError(
                "Automatic forecast generation failed: "
                + str(analysis)
            )

        forecast_id = analysis.get(
            "forecast_id"
        )

        if forecast_id is None:
            raise RuntimeError(
                "Automatic forecast did not return "
                "a forecast_id."
            )

        forecast_id = int(
            forecast_id
        )

        # The automatic engine already supplies the
        # persisted Bayesian forecast under "forecast".
        record = analysis.get(
            "forecast"
        )

        if not isinstance(record, dict):
            raise RuntimeError(
                "Automatic forecast did not return "
                "its persisted forecast record."
            )

        if int(record.get("forecast_id", -1)) != forecast_id:
            raise RuntimeError(
                "Forecast ID mismatch between "
                "automatic forecast and persisted record."
            )

        metadata = analysis.get(
            "metadata",
            {}
        )

        if not isinstance(metadata, dict):
            metadata = {}

        metadata[
            "scheduler_market_timestamp"
        ] = market_timestamp

        metadata[
            "scheduler_source"
        ] = "REAL_MT5"

        analysis["metadata"] = metadata

        if not analysis.get("symbol"):
            analysis["symbol"] = self.symbol

        if not analysis.get("current_price"):
            analysis[
                "current_price"
            ] = market["price"]

        # Scheduler state only. No second calibration record.
        self._last_forecast_id = forecast_id

        self._last_market_timestamp = (
            market_timestamp
        )

        self._last_forecast_timestamp = (
            datetime.now(timezone.utc)
        )

        return {
            "status":
                "FORECAST_GENERATED",
            "forecast":
                analysis,
            "record":
                record,
            "forecast_id":
                forecast_id,
            "market_timestamp":
                market_timestamp,
            "price":
                market["price"],
            "source":
                "REAL_MT5",
            "execution_enabled":
                self.EXECUTION_ENABLED,
        }

    def run_cycle(
        self,
    ) -> Dict[str, Any]:

        monitor_result = self.process_pending()

        forecast_result = self.generate_forecast()

        return {
            "status":
                "CYCLE_COMPLETE",
            "symbol":
                self.symbol,
            "timeframe":
                self.timeframe,
            "monitor":
                monitor_result,
            "forecast":
                forecast_result,
            "scheduler_state": {
                "last_forecast_id":
                    self._last_forecast_id,
                "last_market_timestamp":
                    self._last_market_timestamp,
                "last_forecast_timestamp":
                    (
                        self._last_forecast_timestamp.isoformat()
                        if self._last_forecast_timestamp
                        else None
                    ),
            },
            "execution_enabled":
                self.EXECUTION_ENABLED,
            "simulation_enabled":
                self.SIMULATION_ENABLED,
            "timestamp":
                datetime.now(
                    timezone.utc
                ).isoformat(),
        }


__all__ = [
    "ForecastScheduler",
]
