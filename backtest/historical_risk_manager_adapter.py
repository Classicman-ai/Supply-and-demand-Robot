from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from risk.risk_manager import RiskManager

from backtest.historical_account import HistoricalAccount
from backtest.historical_position_sizer import HistoricalSymbolSpec


class HistoricalRiskManagerAdapter(RiskManager):
    """
    Historical environment adapter around the REAL RiskManager.

    IMPORTANT:
    - Inherits the real RiskManager.
    - Does NOT replace validate_trade().
    - Does NOT modify RiskManager source.
    - Supplies historical account/position/trade/symbol state.
    - No MT5 order_send().
    - No live position access.
    """

    VERSION = "1.0.0-HISTORICAL-RISK-ADAPTER"

    def __init__(
        self,
        *,
        account: HistoricalAccount,
        symbol_specs: dict[str, HistoricalSymbolSpec],
        market_data: Any = None,
    ) -> None:

        self.historical_account = account
        self.symbol_specs = {
            str(k): v
            for k, v in symbol_specs.items()
        }

        # Preserve the real RiskManager initialization.
        super().__init__(
            market_data=market_data
        )

    # ==============================================================
    # HISTORICAL ACCOUNT
    # ==============================================================

    def get_account(self) -> dict[str, Any]:

        snapshot = self.historical_account.snapshot()

        return {
            "status": "OK",

            "login": 0,
            "server": "HISTORICAL-BACKTEST",

            "balance": float(
                snapshot.get(
                    "balance",
                    0.0,
                )
            ),

            "equity": float(
                snapshot.get(
                    "equity",
                    0.0,
                )
            ),

            "margin": 0.0,
            "margin_free": float(
                snapshot.get(
                    "equity",
                    0.0,
                )
            ),

            "trade_allowed": True,
            "trade_expert": True,

            "currency": snapshot.get(
                "currency",
                "USD",
            ),

            "historical": True,
        }

    # ==============================================================
    # HISTORICAL OPEN POSITIONS
    # ==============================================================

    def open_positions(self) -> list:

        count = int(
            getattr(
                self.historical_account,
                "open_positions",
                0,
            )
        )

        return [
            {
                "historical": True,
                "ticket": f"HIST-POS-{i + 1:06d}",
            }
            for i in range(count)
        ]

    # ==============================================================
    # HISTORICAL DAILY TRADE COUNT
    # ==============================================================

    def trades_today(self) -> int:

        return int(
            getattr(
                self.historical_account,
                "trades_today",
                0,
            )
        )

    # ==============================================================
    # HISTORICAL SYMBOL RESOLUTION
    # ==============================================================

    def _resolve_historical_symbol(
        self,
        symbol: str,
    ) -> str:

        requested = str(symbol).strip()

        if requested in self.symbol_specs:
            return requested

        requested_upper = requested.upper()

        for candidate in self.symbol_specs:

            if candidate.upper() == requested_upper:
                return candidate

        return requested

    # ==============================================================
    # HISTORICAL BROKER VOLUME VALIDATION
    # ==============================================================

    def validate_volume(
        self,
        symbol: str,
        volume: float,
    ) -> dict[str, Any]:

        try:
            volume = float(volume)
        except Exception:

            return {
                "approved": False,
                "reason": "INVALID_VOLUME",
                "volume": 0.0,
            }

        if volume <= 0:

            return {
                "approved": False,
                "reason": "INVALID_VOLUME",
                "volume": 0.0,
            }

        resolved = self._resolve_historical_symbol(
            symbol
        )

        spec = self.symbol_specs.get(
            resolved
        )

        if spec is None:

            return {
                "approved": False,
                "reason": "SYMBOL_INFORMATION_UNAVAILABLE",
                "volume": 0.0,
            }

        minimum = float(
            spec.volume_min
        )

        maximum = float(
            spec.volume_max
        )

        step = float(
            spec.volume_step
        )

        if step <= 0:

            return {
                "approved": False,
                "reason": "INVALID_VOLUME_STEP",
                "volume": 0.0,
            }

        if volume < minimum:

            return {
                "approved": False,
                "reason": "VOLUME_BELOW_BROKER_MINIMUM",
                "volume": volume,
                "volume_min": minimum,
            }

        if volume > maximum:

            return {
                "approved": False,
                "reason": "VOLUME_ABOVE_BROKER_MAXIMUM",
                "volume": volume,
                "volume_max": maximum,
            }

        steps = round(
            volume / step
        )

        normalized = steps * step

        decimals = 0

        step_text = str(step)

        if "." in step_text:

            decimals = len(
                step_text.rstrip("0")
                .split(".")[-1]
            )

        normalized = round(
            normalized,
            decimals,
        )

        if (
            normalized < minimum
            or normalized > maximum
        ):

            return {
                "approved": False,
                "reason": "VOLUME_OUTSIDE_BROKER_RANGE",
                "volume": volume,
                "normalized_volume": normalized,
                "volume_min": minimum,
                "volume_max": maximum,
                "volume_step": step,
            }

        tolerance = max(
            step * 0.001,
            1e-12,
        )

        if abs(
            normalized - volume
        ) > tolerance:

            return {
                "approved": False,
                "reason": "VOLUME_NOT_ALIGNED_TO_BROKER_STEP",
                "volume": volume,
                "normalized_volume": normalized,
                "volume_step": step,
            }

        return {
            "approved": True,
            "symbol": resolved,
            "volume": normalized,
            "volume_min": minimum,
            "volume_max": maximum,
            "volume_step": step,
            "historical": True,
        }


__all__ = [
    "HistoricalRiskManagerAdapter",
]
