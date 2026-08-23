
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class HistoricalRiskState:
    """
    Historical replacement for live MT5 account/trading state.

    This class does NOT redefine RiskManager rules.
    It only supplies historical state that live MT5 normally provides.
    """

    balance: float
    equity: float
    open_positions: int
    trades_today: int
    trade_allowed: bool = True
    trade_expert: bool = True
    symbol: str = ""
    volume_min: Optional[float] = None
    volume_max: Optional[float] = None
    volume_step: Optional[float] = None
    timestamp: Optional[datetime] = None


class HistoricalRiskAdapter:
    """
    Thin historical environment adapter for the REAL RiskManager.

    DESIGN RULE:
        Historical Risk Adapter = Live RiskManager contract
        with historical state substituted for live MT5 state.

    This class intentionally contains no alternative risk policy.
    """

    ENGINE_NAME = "HISTORICAL RISK ADAPTER"
    VERSION = "1.0.0"

    def __init__(
        self,
        risk_manager: Any,
        state: HistoricalRiskState,
    ) -> None:

        self.risk_manager = risk_manager
        self.state = state

    def account_state(self) -> Dict[str, Any]:

        return {
            "status": "OK",
            "login": None,
            "server": "HISTORICAL",
            "balance": float(self.state.balance),
            "equity": float(self.state.equity),
            "margin": 0.0,
            "margin_free": float(self.state.equity),
            "trade_allowed": bool(
                self.state.trade_allowed
            ),
            "trade_expert": bool(
                self.state.trade_expert
            ),
            "historical": True,
            "timestamp": self.state.timestamp,
        }

    def trading_state(self) -> Dict[str, Any]:

        return {
            "open_positions":
                int(self.state.open_positions),
            "trades_today":
                int(self.state.trades_today),
            "timestamp":
                self.state.timestamp,
        }

    def calculate_risk_reward(
        self,
        side: str,
        entry: float,
        stop_loss: float,
        take_profit: float,
    ) -> float:

        # Delegate directly to the REAL RiskManager.
        return self.risk_manager.calculate_risk_reward(
            side,
            entry,
            stop_loss,
            take_profit,
        )

    def validate_trade_contract(
        self,
        symbol: str,
        side: str,
        entry: float,
        stop_loss: float,
        take_profit: float,
        volume: float,
    ) -> Dict[str, Any]:

        """
        Contract representation only.

        The adapter does not invent another risk policy.

        The actual RiskManager.validate_trade() remains the
        authoritative validation implementation.
        """

        return {
            "adapter": self.ENGINE_NAME,
            "adapter_version": self.VERSION,
            "symbol": symbol,
            "side": str(side).upper(),
            "entry": float(entry),
            "stop_loss": float(stop_loss),
            "take_profit": float(take_profit),
            "volume": float(volume),
            "historical_state": self.account_state(),
            "trading_state": self.trading_state(),
            "delegates_to_real_risk_manager": True,
        }
