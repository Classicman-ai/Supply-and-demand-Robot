from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass
class SimulatedPosition:
    symbol: str
    side: str
    entry_time: object
    entry: float
    stop_loss: float
    take_profit: float
    volume: float
    risk_reward: float


class HistoricalPlaybackEngine:
    """
    Deterministic historical candle playback.

    IMPORTANT:
    This is a simulation layer.
    It never calls raise RuntimeError('LIVE_ORDER_SEND_BLOCKED_IN_BACKTEST') # mt5.order_send().
    """

    VERSION = "1.0.0"

    def __init__(
        self,
        symbol: str,
        candles: pd.DataFrame,
        initial_balance: float = 10000.0,
    ):
        self.symbol = symbol
        self.candles = candles.reset_index(drop=True)
        self.initial_balance = float(initial_balance)
        self.balance = float(initial_balance)
        self.position: Optional[SimulatedPosition] = None
        self.trades = []

    def run(self, signal_provider=None):
        """
        signal_provider(row_index, dataframe) must return either None
        or a dictionary containing:

            side
            entry
            stop_loss
            take_profit
            volume
            risk_reward

        The actual Supply & Demand strategy adapter will be connected
        here without changing the playback engine.
        """

        if signal_provider is None:
            raise RuntimeError(
                "No strategy provider connected. "
                "Backtest playback engine is installed, but no "
                "trading strategy has been executed."
            )

        for i in range(len(self.candles)):
            row = self.candles.iloc[i]

            if self.position is not None:
                self._manage_position(row)

                if self.position is not None:
                    continue

            signal = signal_provider(i, self.candles)

            if not signal:
                continue

            self._open(signal, row)

        return self.trades

    def _open(self, signal, row):
        side = str(signal["side"]).upper()
        entry = float(signal["entry"])
        sl = float(signal["stop_loss"])
        tp = float(signal["take_profit"])
        volume = float(signal.get("volume", 0.01))

        if side not in ("BUY", "SELL"):
            return

        if side == "BUY":
            risk = entry - sl
            reward = tp - entry
        else:
            risk = sl - entry
            reward = entry - tp

        if risk <= 0 or reward <= 0:
            return

        rr = reward / risk

        if rr < 3.0:
            return

        self.position = SimulatedPosition(
            symbol=self.symbol,
            side=side,
            entry_time=row["time"],
            entry=entry,
            stop_loss=sl,
            take_profit=tp,
            volume=volume,
            risk_reward=rr,
        )

    def _manage_position(self, row):
        p = self.position

        high = float(row["high"])
        low = float(row["low"])

        exit_price = None
        reason = None

        if p.side == "BUY":
            sl_hit = low <= p.stop_loss
            tp_hit = high >= p.take_profit

            # Conservative same-candle rule:
            # if both are touched and ordering is unknowable,
            # assume SL first.
            if sl_hit:
                exit_price = p.stop_loss
                reason = "STOP_LOSS"
            elif tp_hit:
                exit_price = p.take_profit
                reason = "TAKE_PROFIT"

        else:
            sl_hit = high >= p.stop_loss
            tp_hit = low <= p.take_profit

            if sl_hit:
                exit_price = p.stop_loss
                reason = "STOP_LOSS"
            elif tp_hit:
                exit_price = p.take_profit
                reason = "TAKE_PROFIT"

        if exit_price is None:
            return

        risk_distance = (
            abs(p.entry - p.stop_loss)
        )

        if p.side == "BUY":
            result_r = (exit_price - p.entry) / risk_distance
        else:
            result_r = (p.entry - exit_price) / risk_distance

        trade = {
            "symbol": p.symbol,
            "side": p.side,
            "entry_time": str(p.entry_time),
            "exit_time": str(row["time"]),
            "entry": p.entry,
            "stop_loss": p.stop_loss,
            "take_profit": p.take_profit,
            "exit_price": exit_price,
            "volume": p.volume,
            "risk_reward": p.risk_reward,
            "result_r": result_r,
            "profit": result_r,
            "exit_reason": reason,
            "metadata": {
                "engine": "HISTORICAL_PLAYBACK",
                "version": self.VERSION,
            },
        }

        self.trades.append(trade)
        self.position = None
