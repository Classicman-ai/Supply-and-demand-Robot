
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, Any


@dataclass
class HistoricalAccount:
    """
    Hypothetical historical trading account.

    This is BACKTEST STATE ONLY.

    It does not alter the live MT5 account and does not
    redefine RiskManager policy.
    """

    initial_balance: float = 100000.0
    balance: float = 100000.0
    equity: float = 100000.0
    currency: str = "USD"

    open_positions: int = 0
    trades_today: int = 0

    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0

    peak_equity: float = 100000.0
    max_drawdown: float = 0.0

    current_date: str | None = None

    def begin_trade_day(self, timestamp: datetime) -> None:

        day = timestamp.date().isoformat()

        if self.current_date != day:

            self.current_date = day
            self.trades_today = 0

    def reserve_position(self) -> None:

        self.open_positions += 1

    def release_position(self) -> None:

        self.open_positions = max(
            0,
            self.open_positions - 1
        )

    def record_trade(
        self,
        pnl: float,
        timestamp: datetime,
    ) -> None:

        self.begin_trade_day(timestamp)

        self.balance += float(pnl)
        self.equity = self.balance

        self.total_trades += 1
        self.trades_today += 1

        if pnl > 0:
            self.winning_trades += 1

        elif pnl < 0:
            self.losing_trades += 1

        if self.equity > self.peak_equity:
            self.peak_equity = self.equity

        drawdown = self.peak_equity - self.equity

        if drawdown > self.max_drawdown:
            self.max_drawdown = drawdown

    def snapshot(self) -> Dict[str, Any]:

        return asdict(self)

    @property
    def drawdown_percent(self) -> float:

        if self.peak_equity <= 0:
            return 0.0

        return (
            self.max_drawdown
            / self.peak_equity
            * 100.0
        )
