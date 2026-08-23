"""
SUPPLY & DEMAND MT5
FORECAST LIFECYCLE / AUTOMATIC RESOLUTION ENGINE
=================================================

Version: 1.0.0

Purpose:
    Manage the complete lifecycle of Bayesian forecasts.

Rules:
    - REAL MT5 DATA ONLY
    - READ-ONLY
    - NO ORDER PLACEMENT
    - NO EXECUTION IMPORTS
    - NO SIMULATION
    - NO HARDCODED MARKET PRICES

Lifecycle:
    FORECAST RECORDED
        -> PENDING
        -> RESOLVED
        -> CALIBRATION UPDATED
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForecastLifecycleEngine:

    ENGINE_NAME = "FORECAST LIFECYCLE / AUTOMATIC RESOLUTION ENGINE"
    VERSION = "1.0.0"

    READ_ONLY_TRADING = True
    EXECUTION_ENABLED = False
    SIMULATION_ENABLED = False

    VALID_OUTCOMES = ("BULLISH", "BEARISH", "NEUTRAL")

    def __init__(
        self,
        calibration_engine: Any,
        market_data: Any,
        neutral_band_percent: float = 0.05,
    ) -> None:

        if calibration_engine is None:
            raise ValueError("calibration_engine is required.")

        if market_data is None:
            raise ValueError("market_data is required.")

        self.calibration_engine = calibration_engine
        self.market_data = market_data
        self.neutral_band_percent = float(neutral_band_percent)

        if self.neutral_band_percent < 0:
            raise ValueError(
                "neutral_band_percent cannot be negative."
            )

    # ==============================================================
    # RESOLVE FROM REAL MT5 PRICE
    # ==============================================================

    def resolve_from_price(
        self,
        forecast_id: int,
        observed_price: float,
    ) -> Dict[str, Any]:

        observed_price = float(observed_price)

        if observed_price <= 0:
            raise ValueError("observed_price must be positive.")

        forecast = self.calibration_engine.get_forecast(
            int(forecast_id)
        )

        if forecast is None:
            raise ValueError(
                f"Forecast {forecast_id} does not exist."
            )

        if forecast.get("resolved_outcome"):
            raise ValueError(
                f"Forecast {forecast_id} is already resolved."
            )

        forecast_price = float(forecast["price"])

        change_percent = (
            (observed_price - forecast_price)
            / forecast_price
        ) * 100.0

        outcome = self._classify_outcome(
            change_percent
        )

        return self.calibration_engine.resolve_forecast(
            forecast_id=int(forecast_id),
            outcome=outcome,
            outcome_return=change_percent,
        ) | {
            "observed_price": observed_price,
            "forecast_price": forecast_price,
            "change_percent": round(
                change_percent,
                6,
            ),
            "neutral_band_percent":
                self.neutral_band_percent,
        }

    # ==============================================================
    # RESOLVE USING REAL MT5 DATA
    # ==============================================================

    def resolve_from_mt5(
        self,
        forecast_id: int,
        timeframe: str = "M5",
    ) -> Dict[str, Any]:

        forecast = self.calibration_engine.get_forecast(
            int(forecast_id)
        )

        if forecast is None:
            raise ValueError(
                f"Forecast {forecast_id} does not exist."
            )

        symbol = str(
            forecast["symbol"]
        ).strip()

        if not symbol:
            raise ValueError(
                "Forecast does not contain a valid symbol."
            )

        data = self.market_data.get_top_down_data(
            symbol,
            1,
        )

        candles = data.get(
            timeframe,
            [],
        )

        if not candles:
            raise RuntimeError(
                f"No real MT5 {timeframe} data available "
                f"for {symbol}."
            )

        latest = candles[-1]

        if "close" not in latest:
            raise RuntimeError(
                "Latest MT5 candle does not contain close price."
            )

        observed_price = float(
            latest["close"]
        )

        result = self.resolve_from_price(
            forecast_id,
            observed_price,
        )

        result["source"] = "REAL_MT5"
        result["symbol"] = symbol
        result["timeframe"] = timeframe
        result["market_timestamp"] = str(
            latest.get(
                "time",
                latest.get(
                    "timestamp",
                    "",
                ),
            )
        )

        return result

    # ==============================================================
    # LIFECYCLE STATUS
    # ==============================================================

    def get_status(
        self,
        forecast_id: int,
    ) -> Dict[str, Any]:

        forecast = self.calibration_engine.get_forecast(
            int(forecast_id)
        )

        if forecast is None:
            return {
                "status": "NOT_FOUND",
                "forecast_id": int(forecast_id),
            }

        resolved = forecast.get(
            "resolved_outcome"
        )

        if resolved:
            lifecycle = "RESOLVED"
        else:
            lifecycle = "PENDING"

        return {
            "status": lifecycle,
            "forecast_id": int(forecast_id),
            "symbol": forecast.get("symbol"),
            "forecast_price": forecast.get("price"),
            "posterior_bias": forecast.get(
                "posterior_bias"
            ),
            "decision": forecast.get(
                "decision"
            ),
            "resolved_outcome": resolved,
            "outcome_return": forecast.get(
                "outcome_return"
            ),
            "outcome_timestamp": forecast.get(
                "outcome_timestamp"
            ),
            "neutral_band_percent":
                self.neutral_band_percent,
            "execution_enabled":
                self.EXECUTION_ENABLED,
        }

    # ==============================================================
    # CLASSIFICATION
    # ==============================================================

    def _classify_outcome(
        self,
        change_percent: float,
    ) -> str:

        if abs(change_percent) <= self.neutral_band_percent:
            return "NEUTRAL"

        if change_percent > 0:
            return "BULLISH"

        return "BEARISH"

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
            "neutral_band_percent":
                self.neutral_band_percent,
            "valid_outcomes":
                list(self.VALID_OUTCOMES),
            "timestamp":
                datetime.now(
                    timezone.utc
                ).isoformat(),
        }


__all__ = [
    "ForecastLifecycleEngine",
]
