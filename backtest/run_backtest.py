from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import MetaTrader5 as mt5

from .historical_data import HistoricalDataEngine
from .trade_ledger import BacktestLedger
from .playback_engine import HistoricalPlaybackEngine


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "backtest" / "data"
RESULTS = ROOT / "backtest" / "results"
DB = RESULTS / "backtest_history.sqlite3"


def main():
    YEARS = 10
    SYMBOL = "XAUUSD"

    print("=" * 70)
    print("SUPPLY_DEMAND_MT5 — HISTORICAL BACKTEST PREPARATION")
    print("=" * 70)
    print("YEARS:", YEARS)
    print("REQUESTED SYMBOL:", SYMBOL)
    print("LIVE SUPERVISOR: UNTOUCHED")
    print("MT5 ORDER SEND: DISABLED")
    print()

    engine = HistoricalDataEngine(SYMBOL)

    if not engine.connect():
        raise SystemExit(
            "MT5 INITIALIZATION FAILED — BACKTEST ABORTED"
        )

    try:
        resolved = engine.resolve_symbol()
        account = engine.account_info()

        print("RESOLVED SYMBOL:", resolved)
        print("MT5 ACCOUNT:", account)

        # M5 is the initial playback/execution dataset.
        candles = engine.download(
            mt5.TIMEFRAME_M5,
            years=YEARS,
        )

        output = DATA / f"{resolved}_M5_{YEARS}Y.csv"
        engine.save(candles, output)

        print("HISTORICAL DATA SAVED:", output)
        print("CANDLES:", len(candles))

        if len(candles):
            print("START:", candles.iloc[0]["time"])
            print("END:", candles.iloc[-1]["time"])

        print()
        print("DATA ACQUISITION: PASS")
        print("PLAYBACK ENGINE: INSTALLED")
        print("TRADE LEDGER: INSTALLED")
        print("NO LIVE ORDER SENT")
        print()
        print(
            "NEXT STEP: connect the existing Supply & Demand "
            "strategy engine to HistoricalPlaybackEngine."
        )

    finally:
        engine.disconnect()


if __name__ == "__main__":
    main()
