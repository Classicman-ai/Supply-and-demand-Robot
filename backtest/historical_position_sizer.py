
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class HistoricalSymbolSpec:
    """
    Historical/broker symbol specification used by the
    position-sizing layer.

    Values may later be populated automatically from MT5
    symbol_info() and stored with the historical dataset.
    """

    volume_min: float = 0.01
    volume_max: float = 200.0
    volume_step: float = 0.01

    trade_tick_size: float = 0.01
    trade_tick_value: float = 1.0

    digits: int = 2


class HistoricalPositionSizer:

    """
    Calculates position size from account risk and SL distance.

    This class does NOT decide whether a trade is valid.

    Risk approval remains the responsibility of the REAL
    RiskManager.
    """

    def __init__(
        self,
        symbol_spec: HistoricalSymbolSpec,
    ) -> None:

        self.spec = symbol_spec

    @staticmethod
    def _floor_step(
        value: float,
        step: float,
    ) -> float:

        if step <= 0:
            return value

        units = int(value / step)

        return units * step

    def risk_amount(
        self,
        equity: float,
        risk_percent: float,
    ) -> float:

        return (
            float(equity)
            * float(risk_percent)
            / 100.0
        )

    def calculate(
        self,
        equity: float,
        risk_percent: float,
        entry: float,
        stop_loss: float,
    ) -> dict[str, Any]:

        risk_money = self.risk_amount(
            equity,
            risk_percent,
        )

        distance = abs(
            float(entry)
            - float(stop_loss)
        )

        if distance <= 0:
            raise ValueError(
                "Entry/SL distance must be greater than zero."
            )

        tick_size = float(
            self.spec.trade_tick_size
        )

        tick_value = float(
            self.spec.trade_tick_value
        )

        if tick_size <= 0:
            raise ValueError(
                "Invalid tick size."
            )

        if tick_value <= 0:
            raise ValueError(
                "Invalid tick value."
            )

        loss_per_lot = (
            distance
            / tick_size
            * tick_value
        )

        if loss_per_lot <= 0:
            raise ValueError(
                "Invalid loss per lot."
            )

        raw_volume = (
            risk_money
            / loss_per_lot
        )

        volume = self._floor_step(
            raw_volume,
            self.spec.volume_step,
        )

        volume = max(
            0.0,
            volume,
        )

        if volume > self.spec.volume_max:
            volume = self.spec.volume_max

        result = {
            "equity": float(equity),
            "risk_percent": float(risk_percent),
            "risk_amount": float(risk_money),
            "entry": float(entry),
            "stop_loss": float(stop_loss),
            "sl_distance": float(distance),
            "loss_per_lot": float(loss_per_lot),
            "raw_volume": float(raw_volume),
            "volume": float(volume),
            "volume_min": float(
                self.spec.volume_min
            ),
            "volume_max": float(
                self.spec.volume_max
            ),
            "volume_step": float(
                self.spec.volume_step
            ),
        }

        return result
