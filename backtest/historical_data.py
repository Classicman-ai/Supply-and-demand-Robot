from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import MetaTrader5 as mt5
import pandas as pd


class HistoricalDataEngine:
    """
    Reads historical market data from the currently attached MT5 terminal.

    This module is READ-ONLY.
    It does not send orders and does not modify the live supervisor.
    """

    VERSION = "1.0.0"

    def __init__(self, symbol: str = "XAUUSD"):
        self.requested_symbol = symbol
        self.resolved_symbol: Optional[str] = None

    def connect(self) -> bool:
        return bool(mt5.initialize())

    def disconnect(self) -> None:
        try:
            mt5.shutdown()
        except Exception:
            pass

    def resolve_symbol(self) -> str:
        candidates = [
            self.requested_symbol,
            self.requested_symbol + "m",
            self.requested_symbol + ".",
        ]

        for candidate in candidates:
            info = mt5.symbol_info(candidate)
            if info is not None:
                if not info.visible:
                    mt5.symbol_select(candidate, True)
                self.resolved_symbol = candidate
                return candidate

        symbols = mt5.symbols_get()
        if symbols:
            target = self.requested_symbol.upper()
            ranked = []

            for s in symbols:
                name = str(s.name).upper()

                if name == target:
                    ranked.append((0, s.name))
                elif name.startswith(target):
                    ranked.append((1, s.name))
                elif target in name:
                    ranked.append((2, s.name))

            if ranked:
                ranked.sort(key=lambda x: x[0])
                self.resolved_symbol = ranked[0][1]
                mt5.symbol_select(self.resolved_symbol, True)
                return self.resolved_symbol

        raise RuntimeError(
            f"Unable to resolve historical symbol: {self.requested_symbol}"
        )

    def account_info(self) -> dict:
        a = mt5.account_info()
        if a is None:
            return {"status": "ERROR", "error": str(mt5.last_error())}

        return {
            "status": "OK",
            "login": int(a.login),
            "server": str(a.server),
            "company": str(a.company),
            "currency": str(a.currency),
        }

    def download(
        self,
        timeframe,
        years: int = 10,
        chunk_days: int = 30,
    ):
        """
        Download MT5 historical candles safely in chunks.

        This method is strictly historical-data acquisition.
        It NEVER calls mt5.order_send().
        """

        if not self.symbol:
            raise RuntimeError("HISTORICAL_SYMBOL_NOT_RESOLVED")

        if not mt5.symbol_select(self.symbol, True):
            raise RuntimeError(
                f"Unable to select historical symbol {self.symbol}. "
                f"MT5 error: {mt5.last_error()}"
            )

        symbol_info = mt5.symbol_info(self.symbol)
        if symbol_info is None:
            raise RuntimeError(
                f"Historical symbol information unavailable for {self.symbol}. "
                f"MT5 error: {mt5.last_error()}"
            )

        now = datetime.now(timezone.utc)
        requested_start = now - timedelta(days=int(years * 365.25))

        # First discover the actual oldest M5 bar exposed by this terminal.
        probe = mt5.copy_rates_from(
            self.symbol,
            timeframe,
            datetime(1970, 1, 1, tzinfo=timezone.utc),
            1,
        )

        if probe is None:
            raise RuntimeError(
                f"Historical probe failed for {self.symbol}. "
                f"MT5 error: {mt5.last_error()}"
            )

        # MT5 can return an empty array when the requested historical
        # range is outside the terminal's available history.
        if len(probe) == 0:
            probe = mt5.copy_rates_from_pos(
                self.symbol,
                timeframe,
                0,
                1,
            )

        if probe is None or len(probe) == 0:
            raise RuntimeError(
                f"No historical data available for {self.symbol}. "
                f"MT5 error: {mt5.last_error()}"
            )

        newest_probe_time = int(probe[0]["time"])

        # Discover available history progressively backwards.
        # copy_rates_from_pos gives us a reliable terminal-side history
        # position without assuming the broker has a full 10 years.
        discovery = mt5.copy_rates_from_pos(
            self.symbol,
            timeframe,
            0,
            100000,
        )

        if discovery is None or len(discovery) == 0:
            raise RuntimeError(
                f"No historical data returned for {self.symbol}. "
                f"MT5 error: {mt5.last_error()}"
            )

        available_newest = int(discovery["time"][-1])
        available_oldest = int(discovery["time"][0])

        requested_timestamp = int(requested_start.timestamp())

        # MT5 history returned by copy_rates_from_pos is chronological.
        # Use the oldest available bar exposed by the terminal when it is
        # newer than our requested 10-year boundary.
        actual_start_timestamp = max(
            requested_timestamp,
            available_oldest,
        )

        actual_end_timestamp = min(
            int(now.timestamp()),
            available_newest,
        )

        if actual_start_timestamp >= actual_end_timestamp:
            raise RuntimeError(
                f"Insufficient historical range for {self.symbol}. "
                f"oldest={available_oldest}, newest={available_newest}, "
                f"requested_start={requested_timestamp}"
            )

        start_dt = datetime.fromtimestamp(
            actual_start_timestamp,
            tz=timezone.utc,
        )
        end_dt = datetime.fromtimestamp(
            actual_end_timestamp,
            tz=timezone.utc,
        )

        print(
            f"HISTORICAL RANGE: "
            f"{start_dt.isoformat()} -> {end_dt.isoformat()}"
        )
        print(
            f"REQUESTED YEARS: {years}"
        )
        print(
            f"TERMINAL DISCOVERY BARS: {len(discovery)}"
        )

        frames = []
        cursor = start_dt

        chunk_delta = timedelta(days=int(chunk_days))

        while cursor < end_dt:
            chunk_end = min(cursor + chunk_delta, end_dt)

            rates = mt5.copy_rates_range(
                self.symbol,
                timeframe,
                cursor,
                chunk_end,
            )

            if rates is None:
                error = mt5.last_error()
                raise RuntimeError(
                    f"Historical chunk request failed: "
                    f"{cursor.isoformat()} -> {chunk_end.isoformat()} | "
                    f"MT5 error: {error}"
                )

            if len(rates):
                frames.append(
                    pd.DataFrame(rates)
                )

            cursor = chunk_end

        if not frames:
            raise RuntimeError(
                f"No historical data returned for {self.symbol}. "
                f"MT5 error: {mt5.last_error()}"
            )

        data = pd.concat(frames, ignore_index=True)

        if "time" not in data.columns:
            raise RuntimeError(
                "Historical dataset missing required 'time' column."
            )

        data["time"] = pd.to_datetime(
            data["time"],
            unit="s",
            utc=True,
        )

        data = (
            data
            .drop_duplicates(subset=["time"])
            .sort_values("time")
            .reset_index(drop=True)
        )

        # Keep only the requested window.
        data = data[
            (data["time"] >= pd.Timestamp(start_dt))
            & (data["time"] <= pd.Timestamp(end_dt))
        ].reset_index(drop=True)

        if data.empty:
            raise RuntimeError(
                f"Historical dataset became empty after normalization "
                f"for {self.symbol}."
            )

        print(
            f"IMPORTED M5 BARS: {len(data)}"
        )
        print(
            f"ACTUAL START: {data['time'].iloc[0]}"
        )
        print(
            f"ACTUAL END: {data['time'].iloc[-1]}"
        )

        # Persist the raw normalized historical dataset.
        data_dir = Path("data") / "backtest"
        data_dir.mkdir(parents=True, exist_ok=True)

        output = (
            data_dir
            / f"{self.symbol}_M5_{years}Y.parquet"
        )

        try:
            data.to_parquet(output, index=False)
            print(f"STORED DATASET: {output}")
        except Exception as exc:
            # Parquet may not be installed. CSV remains a valid persistent
            # fallback and does not affect the live supervisor.
            output = (
                data_dir
                / f"{self.symbol}_M5_{years}Y.csv"
            )
            data.to_csv(output, index=False)
            print(
                f"PARQUET UNAVAILABLE — CSV FALLBACK: {exc}"
            )
            print(f"STORED DATASET: {output}")

        return data

    def save(df: pd.DataFrame, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index=False)
