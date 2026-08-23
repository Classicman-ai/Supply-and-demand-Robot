
"""
Historical Market Data Adapter
==============================

Historical implementation of the LIVE MarketData contract.

The live strategy expects:

    get_top_down_data(symbol, count=500)

This adapter provides the same interface while ensuring that
historical playback never exposes candles after the current
historical timestamp.

NO MetaTrader5 dependency.
NO order execution.
NO live position access.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


class HistoricalMarketData:

    TIMEFRAMES = (
        "D1",
        "H4",
        "H1",
        "M15",
        "M5",
    )

    FILES = {
        "M5": "XAUUSDm_M5_330D.csv",
        "M15": "XAUUSDm_M15_330D.csv",
        "M30": "XAUUSDm_M30_330D.csv",
        "H1": "XAUUSDm_H1_330D.csv",
        "H4": "XAUUSDm_H4_330D.csv",
        "D1": "XAUUSDm_D1_330D.csv",
    }

    def __init__(
        self,
        root: str | Path,
        symbol: str = "XAUUSDm",
    ) -> None:

        self.root = Path(root)
        self.symbol = symbol

        self.frames: dict[str, pd.DataFrame] = {}
        self.current_timestamp: pd.Timestamp | None = None

        self._load()

    def _load(self) -> None:

        for timeframe in self.TIMEFRAMES:

            filename = self.FILES[timeframe]
            path = self.root / filename

            if not path.exists():
                raise FileNotFoundError(
                    f"Historical data file missing: {path}"
                )

            df = pd.read_csv(path)

            timestamp_column = (
                "timestamp"
                if "timestamp" in df.columns
                else "time"
            )

            if timestamp_column not in df.columns:
                raise ValueError(
                    f"{path} has no timestamp/time column."
                )

            df[timestamp_column] = pd.to_datetime(
                df[timestamp_column],
                utc=True,
            )

            if timestamp_column != "timestamp":
                df = df.rename(
                    columns={
                        timestamp_column: "timestamp"
                    }
                )

            df = (
                df.sort_values("timestamp")
                .drop_duplicates(
                    subset=["timestamp"],
                    keep="last",
                )
                .reset_index(drop=True)
            )

            required = {
                "open",
                "high",
                "low",
                "close",
            }

            missing = required - set(df.columns)

            if missing:
                raise ValueError(
                    f"{path} missing columns: "
                    f"{sorted(missing)}"
                )

            self.frames[timeframe] = df

    def set_timestamp(
        self,
        timestamp: Any,
    ) -> None:

        ts = pd.Timestamp(timestamp)

        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        else:
            ts = ts.tz_convert("UTC")

        self.current_timestamp = ts

    def _require_timestamp(self) -> pd.Timestamp:

        if self.current_timestamp is None:

            raise RuntimeError(
                "HISTORICAL_TIMESTAMP_NOT_SET"
            )

        return self.current_timestamp

    def _rows(
        self,
        timeframe: str,
        count: int = 500,
    ) -> pd.DataFrame:

        if timeframe not in self.frames:
            raise KeyError(
                f"Unknown timeframe: {timeframe}"
            )

        timestamp = self._require_timestamp()

        available = self.frames[timeframe][
            self.frames[timeframe]["timestamp"] <= timestamp
        ]

        return available.tail(int(count))

    @staticmethod
    def _candle(row: pd.Series) -> dict[str, Any]:

        return {
            "timestamp": row["timestamp"],
            "time": row["timestamp"],
            "symbol": row.get("symbol"),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "tick_volume": float(
                row.get("tick_volume", 0)
            ),
            "spread": float(
                row.get("spread", 0)
            ),
            "real_volume": float(
                row.get("real_volume", 0)
            ),
        }

    def get_top_down_data(
        self,
        symbol: str,
        count: int = 500,
    ) -> dict[str, list[dict[str, Any]]]:

        result: dict[str, list[dict[str, Any]]] = {}

        for timeframe in self.TIMEFRAMES:

            rows = self._rows(
                timeframe,
                count,
            )

            result[timeframe] = [
                self._candle(row)
                for _, row in rows.iterrows()
            ]

        return result

    def get_tick(
        self,
        symbol: str | None = None,
    ) -> dict[str, Any]:

        rows = self._rows("M5", 1)

        if rows.empty:
            return {
                "bid": 0.0,
                "ask": 0.0,
                "last": 0.0,
                "status": "ERROR",
            }

        row = rows.iloc[-1]
        price = float(row["close"])

        return {
            "bid": price,
            "ask": price,
            "last": price,
            "time": row["timestamp"],
            "timestamp": row["timestamp"],
            "status": "OK",
        }
