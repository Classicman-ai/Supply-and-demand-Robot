from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class BacktestLedger:
    VERSION = "1.0.0"

    def __init__(self, database: Path):
        self.database = Path(database)
        self.database.parent.mkdir(parents=True, exist_ok=True)

        self.connection = sqlite3.connect(str(self.database))
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS backtest_runs (
                run_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                start_time TEXT,
                end_time TEXT,
                years REAL,
                initial_balance REAL,
                final_balance REAL,
                total_trades INTEGER,
                winning_trades INTEGER,
                losing_trades INTEGER,
                win_rate REAL,
                net_profit REAL,
                profit_factor REAL,
                expectancy_r REAL,
                max_drawdown REAL,
                notes TEXT
            )
            """
        )

        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS backtest_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                ticket TEXT,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                entry_time TEXT,
                exit_time TEXT,
                entry REAL,
                stop_loss REAL,
                take_profit REAL,
                exit_price REAL,
                volume REAL,
                risk_reward REAL,
                result_r REAL,
                profit REAL,
                exit_reason TEXT,
                metadata TEXT
            )
            """
        )

        self.connection.commit()

    def record_trade(self, run_id: str, trade: dict[str, Any]) -> None:
        self.connection.execute(
            """
            INSERT INTO backtest_trades (
                run_id,
                ticket,
                symbol,
                side,
                entry_time,
                exit_time,
                entry,
                stop_loss,
                take_profit,
                exit_price,
                volume,
                risk_reward,
                result_r,
                profit,
                exit_reason,
                metadata
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                str(trade.get("ticket", "")),
                trade.get("symbol"),
                trade.get("side"),
                trade.get("entry_time"),
                trade.get("exit_time"),
                trade.get("entry"),
                trade.get("stop_loss"),
                trade.get("take_profit"),
                trade.get("exit_price"),
                trade.get("volume"),
                trade.get("risk_reward"),
                trade.get("result_r"),
                trade.get("profit"),
                trade.get("exit_reason"),
                json.dumps(trade.get("metadata", {}), default=str),
            ),
        )
        self.connection.commit()

    def record_run(self, run: dict[str, Any]) -> None:
        self.connection.execute(
            """
            INSERT OR REPLACE INTO backtest_runs (
                run_id,
                created_at,
                symbol,
                timeframe,
                start_time,
                end_time,
                years,
                initial_balance,
                final_balance,
                total_trades,
                winning_trades,
                losing_trades,
                win_rate,
                net_profit,
                profit_factor,
                expectancy_r,
                max_drawdown,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run["run_id"],
                run["created_at"],
                run["symbol"],
                run["timeframe"],
                run.get("start_time"),
                run.get("end_time"),
                run.get("years"),
                run.get("initial_balance"),
                run.get("final_balance"),
                run.get("total_trades"),
                run.get("winning_trades"),
                run.get("losing_trades"),
                run.get("win_rate"),
                run.get("net_profit"),
                run.get("profit_factor"),
                run.get("expectancy_r"),
                run.get("max_drawdown"),
                run.get("notes"),
            ),
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()
