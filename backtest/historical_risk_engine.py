
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from backtest.historical_account import (
    HistoricalAccount,
)

from backtest.historical_position_sizer import (
    HistoricalPositionSizer,
    HistoricalSymbolSpec,
)


@dataclass
class HistoricalRiskConfig:

    normal_risk_percent: float = 2.0
    a_plus_risk_percent: float = 3.0

    starting_balance: float = 100000.0

    def risk_percent_for_grade(
        self,
        grade: str | None,
    ) -> float:

        normalized = str(
            grade or ""
        ).strip().upper()

        if normalized in {
            "A+",
            "A_PLUS",
            "APLUS",
        }:

            return self.a_plus_risk_percent

        return self.normal_risk_percent


class HistoricalRiskEngine:

    """
    Historical risk environment.

    IMPORTANT:

    This engine does not replace RiskManager.

    It supplies:
        account state
        historical trade count
        historical open positions
        position size
        risk amount

    The REAL RiskManager remains authoritative for
    validation.
    """

    def __init__(
        self,
        risk_manager: Any,
        account: HistoricalAccount | None = None,
        symbol_spec: HistoricalSymbolSpec | None = None,
        config: HistoricalRiskConfig | None = None,
    ) -> None:

        self.risk_manager = risk_manager

        self.config = (
            config
            or HistoricalRiskConfig()
        )

        self.account = (
            account
            or HistoricalAccount(
                initial_balance=
                    self.config.starting_balance,
                balance=
                    self.config.starting_balance,
                equity=
                    self.config.starting_balance,
                peak_equity=
                    self.config.starting_balance,
            )
        )

        self.symbol_spec = (
            symbol_spec
            or HistoricalSymbolSpec()
        )

        self.sizer = HistoricalPositionSizer(
            self.symbol_spec
        )

    def prepare_trade(
        self,
        *,
        trade_number: int,
        trade_id: str,
        timestamp: datetime,
        session: str,
        symbol: str,
        side: str,
        entry: float,
        stop_loss: float,
        take_profit: float,
        grade: str | None = None,
    ) -> dict[str, Any]:

        self.account.begin_trade_day(
            timestamp
        )

        risk_percent = (
            self.config.risk_percent_for_grade(
                grade
            )
        )

        sizing = self.sizer.calculate(
            equity=self.account.equity,
            risk_percent=risk_percent,
            entry=entry,
            stop_loss=stop_loss,
        )

        return {
            "trade_number": int(
                trade_number
            ),
            "trade_id": str(
                trade_id
            ),
            "timestamp": timestamp.isoformat(),
            "session": str(session),
            "symbol": str(symbol),
            "side": str(side).upper(),

            "grade": grade,

            "account_balance":
                float(self.account.balance),

            "account_equity":
                float(self.account.equity),

            "risk_percent":
                float(risk_percent),

            "risk_amount":
                float(
                    sizing["risk_amount"]
                ),

            "entry":
                float(entry),

            "stop_loss":
                float(stop_loss),

            "take_profit":
                float(take_profit),

            "sl_distance":
                float(
                    sizing["sl_distance"]
                ),

            "volume":
                float(
                    sizing["volume"]
                ),

            "volume_raw":
                float(
                    sizing["raw_volume"]
                ),

            "historical_open_positions":
                int(
                    self.account.open_positions
                ),

            "historical_trades_today":
                int(
                    self.account.trades_today
                ),
        }

    def register_approved_trade(
        self,
    ) -> None:

        self.account.reserve_position()

    def register_closed_trade(
        self,
        pnl: float,
        timestamp: datetime,
    ) -> None:

        self.account.release_position()

        self.account.record_trade(
            pnl=pnl,
            timestamp=timestamp,
        )
