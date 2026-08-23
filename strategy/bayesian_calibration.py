"""
SUPPLY & DEMAND MT5
BAYESIAN CALIBRATION / EVIDENCE HISTORY ENGINE
================================================

Version:
    1.1.0

Purpose:
    Persist Bayesian forecasts and evaluate their outcomes
    against subsequently observed REAL market prices.

Rules:
    - REAL MARKET OBSERVATIONS ONLY
    - NO SIMULATION
    - READ-ONLY WITH RESPECT TO TRADING
    - NO TRADE EXECUTION
    - NO ORDER PLACEMENT
    - NO MT5 EXECUTION IMPORTS
    - NO HARDCODED MARKET PRICES

The engine records Bayesian forecasts and later resolves them
using an externally supplied observed market price.

Outcome classification:

    price > forecast_price + neutral_band
        -> BULLISH

    price < forecast_price - neutral_band
        -> BEARISH

    otherwise
        -> NEUTRAL
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class BayesianCalibrationEngine:

    ENGINE_NAME = "BAYESIAN CALIBRATION / EVIDENCE HISTORY ENGINE"
    VERSION = "1.1.0"

    READ_ONLY_TRADING = True
    EXECUTION_ENABLED = False
    SIMULATION_ENABLED = False

    HYPOTHESES = (
        "BULLISH",
        "BEARISH",
        "NEUTRAL",
    )

    OUTCOMES = (
        "BULLISH",
        "BEARISH",
        "NEUTRAL",
        "UNRESOLVED",
    )

    DEFAULT_NEUTRAL_BAND_PERCENT = 0.05
    CALIBRATION_MINIMUM_OBSERVATIONS = 100

    def __init__(
        self,
        database_path: str = "data/bayesian_calibration.db",
        neutral_band_percent: float = DEFAULT_NEUTRAL_BAND_PERCENT,
    ) -> None:

        if neutral_band_percent < 0:
            raise ValueError(
                "neutral_band_percent cannot be negative."
            )

        self.database_path = Path(database_path)

        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.neutral_band_percent = float(
            neutral_band_percent
        )

        self._initialize_database()

    # ==============================================================
    # DATABASE
    # ==============================================================

    def _connect(self) -> sqlite3.Connection:

        connection = sqlite3.connect(
            str(self.database_path)
        )

        connection.row_factory = sqlite3.Row

        return connection

    def _initialize_database(self) -> None:

        with self._connect() as connection:

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS bayesian_forecasts (
                    forecast_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    price REAL NOT NULL,
                    deterministic_bias TEXT NOT NULL,
                    posterior_bias TEXT NOT NULL,
                    bullish_probability REAL NOT NULL,
                    bearish_probability REAL NOT NULL,
                    neutral_probability REAL NOT NULL,
                    bayesian_confidence REAL NOT NULL,
                    probability_margin REAL NOT NULL,
                    confluence_score REAL NOT NULL,
                    decision TEXT NOT NULL,
                    evidence_strength REAL NOT NULL,
                    resolved_outcome TEXT,
                    outcome_return REAL,
                    outcome_timestamp TEXT,
                    metadata TEXT
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_bayesian_forecasts_symbol
                ON bayesian_forecasts(symbol)
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_bayesian_forecasts_bias
                ON bayesian_forecasts(posterior_bias)
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_bayesian_forecasts_timestamp
                ON bayesian_forecasts(timestamp)
                """
            )

            connection.commit()

    # ==============================================================
    # RECORD FORECAST
    # ==============================================================

    def record_forecast(
        self,
        analysis: Dict[str, Any],
    ) -> Dict[str, Any]:

        if not isinstance(analysis, dict):
            raise TypeError(
                "analysis must be a dictionary."
            )

        symbol = str(
            analysis.get("symbol", "")
        ).strip()

        if not symbol:
            raise ValueError(
                "analysis must contain a symbol."
            )

        price = float(
            analysis.get(
                "current_price",
                0.0,
            )
        )

        if price <= 0:
            raise ValueError(
                "analysis must contain a positive current_price."
            )

        bayesian = analysis.get(
            "bayesian",
            {},
        )

        posterior = analysis.get(
            "bayesian_probability",
            bayesian.get(
                "posterior_probability",
                {},
            ),
        )

        for hypothesis in self.HYPOTHESES:

            if hypothesis not in posterior:
                raise ValueError(
                    "Missing Bayesian posterior: "
                    f"{hypothesis}"
                )

        bullish = float(
            posterior["BULLISH"]
        )

        bearish = float(
            posterior["BEARISH"]
        )

        neutral = float(
            posterior["NEUTRAL"]
        )

        probabilities = (
            bullish,
            bearish,
            neutral,
        )

        if any(
            probability < 0 or probability > 1
            for probability in probabilities
        ):
            raise ValueError(
                "Bayesian probabilities must be between 0 and 1."
            )

        total = sum(probabilities)

        if abs(total - 1.0) > 0.01:
            raise ValueError(
                "Bayesian posterior probabilities "
                "must sum approximately to 1.0."
            )

        timestamp = self._normalize_timestamp(
            analysis.get("analysis_timestamp")
        )

        metadata = {
            "warnings": analysis.get(
                "warnings",
                [],
            ),
            "conflicts": analysis.get(
                "conflicts",
                [],
            ),
            "proximity": analysis.get(
                "proximity",
                {},
            ),
            "confluence": analysis.get(
                "confluence",
                {},
            ),
        }

        with self._connect() as connection:

            cursor = connection.execute(
                """
                INSERT INTO bayesian_forecasts (
                    timestamp,
                    symbol,
                    price,
                    deterministic_bias,
                    posterior_bias,
                    bullish_probability,
                    bearish_probability,
                    neutral_probability,
                    bayesian_confidence,
                    probability_margin,
                    confluence_score,
                    decision,
                    evidence_strength,
                    metadata
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    timestamp,
                    symbol,
                    price,
                    str(
                        analysis.get(
                            "deterministic_bias",
                            "NEUTRAL",
                        )
                    ),
                    str(
                        analysis.get(
                            "bias",
                            "NEUTRAL",
                        )
                    ),
                    bullish,
                    bearish,
                    neutral,
                    float(
                        analysis.get(
                            "bayesian_confidence",
                            bayesian.get(
                                "confidence",
                                0.0,
                            ),
                        )
                    ),
                    float(
                        bayesian.get(
                            "probability_margin",
                            0.0,
                        )
                    ),
                    float(
                        analysis.get(
                            "confidence",
                            0.0,
                        )
                    ),
                    str(
                        analysis.get(
                            "decision",
                            "NO_TRADE",
                        )
                    ),
                    float(
                        analysis.get(
                            "bayesian_evidence_strength",
                            bayesian.get(
                                "evidence_strength",
                                0.0,
                            ),
                        )
                    ),
                    json.dumps(
                        metadata,
                        default=str,
                    ),
                ),
            )

            forecast_id = cursor.lastrowid

            connection.commit()

        return {
            "status": "RECORDED",
            "forecast_id": forecast_id,
            "symbol": symbol,
            "timestamp": timestamp,
            "price": price,
            "posterior_probability": {
                "BULLISH": round(
                    bullish,
                    6,
                ),
                "BEARISH": round(
                    bearish,
                    6,
                ),
                "NEUTRAL": round(
                    neutral,
                    6,
                ),
            },
            "posterior_bias": analysis.get(
                "bias",
                "NEUTRAL",
            ),
            "decision": analysis.get(
                "decision",
                "NO_TRADE",
            ),
        }

    # ==============================================================
    # RESOLVE USING OBSERVED PRICE
    # ==============================================================

    def resolve_forecast_from_price(
        self,
        forecast_id: int,
        observed_price: float,
        neutral_band_percent: Optional[float] = None,
    ) -> Dict[str, Any]:

        observed_price = float(
            observed_price
        )

        if observed_price <= 0:
            raise ValueError(
                "observed_price must be greater than zero."
            )

        forecast = self.get_forecast(
            forecast_id
        )

        if forecast is None:
            raise ValueError(
                f"Forecast {forecast_id} does not exist."
            )

        if forecast.get("resolved_outcome") is not None:
            raise ValueError(
                f"Forecast {forecast_id} is already resolved."
            )

        forecast_price = float(
            forecast["price"]
        )

        band_percent = (
            self.neutral_band_percent
            if neutral_band_percent is None
            else float(neutral_band_percent)
        )

        if band_percent < 0:
            raise ValueError(
                "neutral_band_percent cannot be negative."
            )

        change_percent = (
            (observed_price - forecast_price)
            / forecast_price
            * 100.0
        )

        if change_percent > band_percent:

            outcome = "BULLISH"

        elif change_percent < -band_percent:

            outcome = "BEARISH"

        else:

            outcome = "NEUTRAL"

        result = self.resolve_forecast(
            forecast_id=forecast_id,
            outcome=outcome,
            outcome_return=change_percent,
            observed_price=observed_price,
        )

        result["forecast_price"] = forecast_price
        result["observed_price"] = observed_price
        result["change_percent"] = round(
            change_percent,
            6,
        )
        result["neutral_band_percent"] = band_percent

        return result

    # ==============================================================
    # RESOLVE FORECAST
    # ==============================================================

    def resolve_forecast(
        self,
        forecast_id: int,
        outcome: str,
        outcome_return: Optional[float] = None,
        observed_price: Optional[float] = None,
    ) -> Dict[str, Any]:

        if outcome not in self.HYPOTHESES:
            raise ValueError(
                "outcome must be BULLISH, BEARISH, or NEUTRAL."
            )

        forecast_id = int(
            forecast_id
        )

        outcome_timestamp = datetime.now(
            timezone.utc
        ).isoformat()

        with self._connect() as connection:

            cursor = connection.execute(
                """
                UPDATE bayesian_forecasts
                SET
                    resolved_outcome = ?,
                    outcome_return = ?,
                    outcome_timestamp = ?
                WHERE forecast_id = ?
                  AND resolved_outcome IS NULL
                """,
                (
                    outcome,
                    outcome_return,
                    outcome_timestamp,
                    forecast_id,
                ),
            )

            connection.commit()

            if cursor.rowcount == 0:

                row = connection.execute(
                    """
                    SELECT *
                    FROM bayesian_forecasts
                    WHERE forecast_id = ?
                    """,
                    (forecast_id,),
                ).fetchone()

                if row is None:
                    raise ValueError(
                        f"Forecast {forecast_id} does not exist."
                    )

                raise ValueError(
                    f"Forecast {forecast_id} is already resolved."
                )

        return {
            "status": "RESOLVED",
            "forecast_id": forecast_id,
            "outcome": outcome,
            "outcome_return": outcome_return,
            "observed_price": observed_price,
            "outcome_timestamp": outcome_timestamp,
        }

    # ==============================================================
    # RETRIEVE FORECAST
    # ==============================================================

    def get_forecast(
        self,
        forecast_id: int,
    ) -> Optional[Dict[str, Any]]:

        with self._connect() as connection:

            row = connection.execute(
                """
                SELECT *
                FROM bayesian_forecasts
                WHERE forecast_id = ?
                """,
                (int(forecast_id),),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_dict(row)

    def get_recent_forecasts(
        self,
        symbol: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:

        limit = max(
            1,
            int(limit),
        )

        with self._connect() as connection:

            if symbol:

                rows = connection.execute(
                    """
                    SELECT *
                    FROM bayesian_forecasts
                    WHERE symbol = ?
                    ORDER BY forecast_id DESC
                    LIMIT ?
                    """,
                    (
                        str(symbol).strip(),
                        limit,
                    ),
                ).fetchall()

            else:

                rows = connection.execute(
                    """
                    SELECT *
                    FROM bayesian_forecasts
                    ORDER BY forecast_id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()

        return [
            self._row_to_dict(row)
            for row in rows
        ]

    # ==============================================================
    # CALIBRATION
    # ==============================================================

    def calculate_calibration(
        self,
        symbol: Optional[str] = None,
    ) -> Dict[str, Any]:

        with self._connect() as connection:

            if symbol:

                rows = connection.execute(
                    """
                    SELECT *
                    FROM bayesian_forecasts
                    WHERE symbol = ?
                      AND resolved_outcome IS NOT NULL
                    ORDER BY forecast_id ASC
                    """,
                    (str(symbol).strip(),),
                ).fetchall()

            else:

                rows = connection.execute(
                    """
                    SELECT *
                    FROM bayesian_forecasts
                    WHERE resolved_outcome IS NOT NULL
                    ORDER BY forecast_id ASC
                    """
                ).fetchall()

        total = len(rows)

        if total == 0:

            return {
                "status": "INSUFFICIENT_DATA",
                "observations": 0,
                "accuracy": None,
                "brier_score": None,
                "calibration_buckets": [],
                "calibration_ready": False,
                "minimum_recommended_observations":
                    self.CALIBRATION_MINIMUM_OBSERVATIONS,
                "message":
                    "No resolved Bayesian observations available.",
            }

        correct = 0
        brier_total = 0.0

        buckets = {
            "0.50-0.55": [],
            "0.55-0.60": [],
            "0.60-0.65": [],
            "0.65-0.70": [],
            "0.70-0.75": [],
            "0.75-0.80": [],
            "0.80-1.00": [],
        }

        for row in rows:

            posterior = {
                "BULLISH":
                    float(
                        row["bullish_probability"]
                    ),
                "BEARISH":
                    float(
                        row["bearish_probability"]
                    ),
                "NEUTRAL":
                    float(
                        row["neutral_probability"]
                    ),
            }

            predicted = max(
                posterior,
                key=posterior.get,
            )

            actual = row[
                "resolved_outcome"
            ]

            if predicted == actual:
                correct += 1

            for hypothesis in self.HYPOTHESES:

                target = (
                    1.0
                    if hypothesis == actual
                    else 0.0
                )

                probability = posterior[
                    hypothesis
                ]

                brier_total += (
                    probability - target
                ) ** 2

            highest = max(
                posterior.values()
            )

            bucket = self._probability_bucket(
                highest
            )

            if bucket:

                buckets[bucket].append(
                    (
                        highest,
                        predicted == actual,
                    )
                )

        accuracy = correct / total

        brier_score = (
            brier_total
            / total
            / len(self.HYPOTHESES)
        )

        calibration_buckets = []

        for bucket_name, observations in buckets.items():

            if not observations:

                calibration_buckets.append(
                    {
                        "bucket": bucket_name,
                        "observations": 0,
                        "average_forecast_probability": None,
                        "empirical_accuracy": None,
                    }
                )

                continue

            average_probability = (
                sum(
                    probability
                    for probability, _ in observations
                )
                / len(observations)
            )

            empirical_accuracy = (
                sum(
                    1
                    for _, correct_flag in observations
                    if correct_flag
                )
                / len(observations)
            )

            calibration_buckets.append(
                {
                    "bucket": bucket_name,
                    "observations": len(
                        observations
                    ),
                    "average_forecast_probability":
                        round(
                            average_probability,
                            6,
                        ),
                    "empirical_accuracy":
                        round(
                            empirical_accuracy,
                            6,
                        ),
                }
            )

        return {
            "status": "CALCULATED",
            "symbol": symbol,
            "observations": total,
            "correct_predictions": correct,
            "accuracy": round(
                accuracy,
                6,
            ),
            "brier_score": round(
                brier_score,
                6,
            ),
            "calibration_buckets":
                calibration_buckets,
            "calibration_ready":
                total >= self.CALIBRATION_MINIMUM_OBSERVATIONS,
            "minimum_recommended_observations":
                self.CALIBRATION_MINIMUM_OBSERVATIONS,
        }

    # ==============================================================
    # STATISTICS
    # ==============================================================

    def get_statistics(
        self,
        symbol: Optional[str] = None,
    ) -> Dict[str, Any]:

        with self._connect() as connection:

            if symbol:

                row = connection.execute(
                    """
                    SELECT
                        COUNT(*) AS total,
                        SUM(
                            CASE
                                WHEN resolved_outcome IS NOT NULL
                                THEN 1
                                ELSE 0
                            END
                        ) AS resolved
                    FROM bayesian_forecasts
                    WHERE symbol = ?
                    """,
                    (str(symbol).strip(),),
                ).fetchone()

            else:

                row = connection.execute(
                    """
                    SELECT
                        COUNT(*) AS total,
                        SUM(
                            CASE
                                WHEN resolved_outcome IS NOT NULL
                                THEN 1
                                ELSE 0
                            END
                        ) AS resolved
                    FROM bayesian_forecasts
                    """
                ).fetchone()

        total = int(
            row["total"] or 0
        )

        resolved = int(
            row["resolved"] or 0
        )

        return {
            "engine": self.ENGINE_NAME,
            "version": self.VERSION,
            "symbol": symbol,
            "total_forecasts": total,
            "resolved_forecasts": resolved,
            "unresolved_forecasts":
                total - resolved,
            "calibration_ready":
                resolved >= self.CALIBRATION_MINIMUM_OBSERVATIONS,
            "minimum_recommended_observations":
                self.CALIBRATION_MINIMUM_OBSERVATIONS,
            "neutral_band_percent":
                self.neutral_band_percent,
            "execution_enabled":
                self.EXECUTION_ENABLED,
            "simulation_enabled":
                self.SIMULATION_ENABLED,
        }

    # ==============================================================
    # HELPERS
    # ==============================================================

    @staticmethod
    def _normalize_timestamp(
        timestamp: Any,
    ) -> str:

        if timestamp is None:

            return datetime.now(
                timezone.utc
            ).isoformat()

        if isinstance(
            timestamp,
            datetime,
        ):

            if timestamp.tzinfo is None:

                timestamp = timestamp.replace(
                    tzinfo=timezone.utc
                )

            return timestamp.isoformat()

        return str(timestamp)

    @staticmethod
    def _probability_bucket(
        probability: float,
    ) -> Optional[str]:

        if probability < 0.50:
            return None

        if probability < 0.55:
            return "0.50-0.55"

        if probability < 0.60:
            return "0.55-0.60"

        if probability < 0.65:
            return "0.60-0.65"

        if probability < 0.70:
            return "0.65-0.70"

        if probability < 0.75:
            return "0.70-0.75"

        if probability < 0.80:
            return "0.75-0.80"

        return "0.80-1.00"

    @staticmethod
    def _row_to_dict(
        row: sqlite3.Row,
    ) -> Dict[str, Any]:

        result = dict(row)

        if result.get("metadata"):

            try:
                result["metadata"] = json.loads(
                    result["metadata"]
                )
            except json.JSONDecodeError:
                pass

        return result


__all__ = [
    "BayesianCalibrationEngine",
]
