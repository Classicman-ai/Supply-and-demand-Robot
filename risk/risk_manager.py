"""
RISK MANAGEMENT ENGINE
======================

Execution/risk validation layer for SUPPLY_DEMAND_MT5.

IMPORTANT DESIGN RULES
----------------------

1. No hard-coded maximum percentage risk per trade.
2. No artificial maximum RRR.
3. RRR is derived from:
       Entry -> Stop distance
       Entry -> Best structural TP
4. TP should come from the strategy:
       - relevant swing
       - opposing supply
       - opposing demand
       - other validated structural liquidity target
5. Explicit order volume is accepted from the strategy/execution layer.
6. Broker volume_min / volume_max / volume_step remain enforced.
7. MT5 account permissions remain enforced.
8. Minimum RRR may still be enforced if configured.
9. This module does NOT bypass broker restrictions or MT5 trading permissions.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
import math

import MetaTrader5 as mt5

try:
    import config
except Exception:
    config = None


class RiskManager:

    ENGINE_NAME = "RISK MANAGEMENT ENGINE"
    VERSION = "2.0.0"

    MAX_OPEN_TRADES = int(
        getattr(config, "MAX_OPEN_TRADES", 1)
        if config is not None
        else 1
    )

    MAX_TRADES_PER_DAY = int(
        getattr(config, "MAX_TRADES_PER_DAY", 3)
        if config is not None
        else 3
    )

    MIN_RISK_REWARD = float(
        getattr(config, "MIN_RISK_REWARD", 3.0)
        if config is not None
        else 3.0
    )

    ENFORCE_MIN_RR = bool(
        getattr(config, "ENFORCE_MIN_RR", True)
        if config is not None
        else True
    )

    def __init__(self, market_data: Any = None) -> None:
        self.market_data = market_data
        self.last_result: Optional[Dict[str, Any]] = None

    # --------------------------------------------------------
    # ACCOUNT
    # --------------------------------------------------------

    def get_account(self) -> Dict[str, Any]:

        account = mt5.account_info()

        if account is None:
            return {
                "status": "ERROR",
                "error": str(mt5.last_error()),
            }

        data = account._asdict()

        return {
            "status": "OK",
            "login": data.get("login"),
            "server": data.get("server"),
            "balance": float(data.get("balance", 0.0)),
            "equity": float(data.get("equity", 0.0)),
            "margin": float(data.get("margin", 0.0)),
            "margin_free": float(data.get("margin_free", 0.0)),
            "trade_allowed": bool(data.get("trade_allowed", False)),
            "trade_expert": bool(data.get("trade_expert", False)),
        }

    # --------------------------------------------------------
    # POSITION SIZE
    # --------------------------------------------------------

    def validate_volume(
        self,
        symbol: str,
        volume: float,
    ) -> Dict[str, Any]:

        try:
            volume = float(volume)
        except Exception:
            return {
                "approved": False,
                "reason": "INVALID_VOLUME",
                "volume": 0.0,
            }

        if not math.isfinite(volume) or volume <= 0:
            return {
                "approved": False,
                "reason": "INVALID_VOLUME",
                "volume": 0.0,
            }

        requested_symbol = str(symbol).strip()
        resolved_symbol = requested_symbol

        try:
            if self.market_data is not None:
                resolved_symbol = (
                    self.market_data.resolve_symbol(requested_symbol)
                    or requested_symbol
                )
            else:
                info_candidate = mt5.symbol_info(requested_symbol)
                if info_candidate is None:
                    symbols = mt5.symbols_get()
                    if symbols:
                        target = requested_symbol.upper()
                        candidates = [
                            x.name for x in symbols
                            if x and x.name.upper() == target
                        ]
                        if candidates:
                            resolved_symbol = candidates[0]
        except Exception:
            resolved_symbol = requested_symbol

        symbol = resolved_symbol
        info = mt5.symbol_info(symbol)

        if info is None:
            try:
                mt5.symbol_select(symbol, True)
                info = mt5.symbol_info(symbol)
            except Exception:
                info = None

        if info is None:
            return {
                "approved": False,
                "reason": "SYMBOL_INFORMATION_UNAVAILABLE",
                "volume": 0.0,
            }

        minimum = float(info.volume_min)
        maximum = float(info.volume_max)
        step = float(info.volume_step)

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

        # Verify the requested volume is aligned to broker step.
        steps = round(volume / step)
        normalized = steps * step

        decimals = 0

        if "." in str(step):
            decimals = len(
                str(step).rstrip("0").split(".")[-1]
            )

        normalized = round(normalized, decimals)

        if normalized < minimum or normalized > maximum:
            return {
                "approved": False,
                "reason": "VOLUME_OUTSIDE_BROKER_RANGE",
                "volume": volume,
                "normalized_volume": normalized,
                "volume_min": minimum,
                "volume_max": maximum,
                "volume_step": step,
            }

        tolerance = max(step * 0.001, 1e-12)

        if abs(normalized - volume) > tolerance:
            return {
                "approved": False,
                "reason": "VOLUME_NOT_ALIGNED_TO_BROKER_STEP",
                "volume": volume,
                "normalized_volume": normalized,
                "volume_step": step,
            }

        return {
            "approved": True,
            "symbol": symbol,
            "volume": normalized,
            "volume_min": minimum,
            "volume_max": maximum,
            "volume_step": step,
        }

    # --------------------------------------------------------
    # R:R
    # --------------------------------------------------------

    def calculate_risk_reward(
        self,
        side: str,
        entry: float,
        stop_loss: float,
        take_profit: float,
    ) -> float:

        side = str(side).upper()

        entry = float(entry)
        stop_loss = float(stop_loss)
        take_profit = float(take_profit)

        if side == "BUY":

            risk = entry - stop_loss
            reward = take_profit - entry

        elif side == "SELL":

            risk = stop_loss - entry
            reward = entry - take_profit

        else:
            return 0.0

        if risk <= 0 or reward <= 0:
            return 0.0

        return reward / risk

    # --------------------------------------------------------
    # STRUCTURAL RRR
    # --------------------------------------------------------

    def calculate_strategy_rrr(
        self,
        side: str,
        entry: float,
        stop_loss: float,
        best_tp: float,
    ) -> Dict[str, Any]:

        rr = self.calculate_risk_reward(
            side,
            entry,
            stop_loss,
            best_tp,
        )

        if rr <= 0:
            return {
                "valid": False,
                "reason": "INVALID_STRUCTURAL_TARGET",
            }

        return {
            "valid": True,
            "side": str(side).upper(),
            "entry": float(entry),
            "stop_loss": float(stop_loss),
            "best_tp": float(best_tp),
            "risk_distance": abs(
                float(entry) - float(stop_loss)
            ),
            "reward_distance": abs(
                float(best_tp) - float(entry)
            ),
            "rrr": rr,
            "max_rrr": rr,
            "rrr_source": "BEST_STRUCTURAL_TP",
        }

    # --------------------------------------------------------
    # POSITION / DAILY LIMITS
    # --------------------------------------------------------

    def open_positions(self) -> list:

        positions = mt5.positions_get()

        if positions is None:
            return []

        return list(positions)

    def trades_today(self) -> int:

        now = datetime.now()

        start = datetime(
            now.year,
            now.month,
            now.day,
        )

        deals = mt5.history_deals_get(
            start,
            now,
        )

        if deals is None:
            return 0

        count = 0

        for deal in deals:

            data = deal._asdict()

            if data.get("entry") == mt5.DEAL_ENTRY_IN:
                count += 1

        return count

    # --------------------------------------------------------
    # CENTRAL VALIDATION
    # --------------------------------------------------------

    def validate_trade(
        self,
        symbol: str,
        side: str,
        entry: Optional[float],
        stop_loss: float,
        take_profit: float,
        volume: float,
    ) -> Dict[str, Any]:

        errors = []

        side = str(side).upper()

        requested_symbol = str(symbol).strip()
        resolved_symbol = requested_symbol

        try:
            if self.market_data is not None:
                resolved_symbol = (
                    self.market_data.resolve_symbol(requested_symbol)
                    or requested_symbol
                )
        except Exception:
            resolved_symbol = requested_symbol

        symbol = resolved_symbol

        if side not in ("BUY", "SELL"):
            errors.append("INVALID_SIDE")

        if entry is None:

            tick = mt5.symbol_info_tick(symbol)

            if tick is None:

                errors.append(
                    "CURRENT_PRICE_UNAVAILABLE"
                )

            else:

                entry = (
                    float(tick.ask)
                    if side == "BUY"
                    else float(tick.bid)
                )

        if entry is None:
            errors.append("ENTRY_UNAVAILABLE")

        if not errors:

            if side == "BUY":

                if stop_loss >= entry:
                    errors.append(
                        "BUY_STOP_MUST_BE_BELOW_ENTRY"
                    )

                if take_profit <= entry:
                    errors.append(
                        "BUY_TP_MUST_BE_ABOVE_ENTRY"
                    )

            elif side == "SELL":

                if stop_loss <= entry:
                    errors.append(
                        "SELL_STOP_MUST_BE_ABOVE_ENTRY"
                    )

                if take_profit >= entry:
                    errors.append(
                        "SELL_TP_MUST_BE_BELOW_ENTRY"
                    )

        rr = 0.0

        if not errors:

            rr = self.calculate_risk_reward(
                side,
                float(entry),
                float(stop_loss),
                float(take_profit),
            )

            if (
                self.ENFORCE_MIN_RR
                and rr < self.MIN_RISK_REWARD
            ):
                errors.append(
                    f"RR_BELOW_MINIMUM:{rr:.4f}"
                )

        # Position count
        positions = self.open_positions()

        if len(positions) >= self.MAX_OPEN_TRADES:
            errors.append(
                "MAX_OPEN_TRADES_REACHED"
            )

        # Daily count
        today = self.trades_today()

        if today >= self.MAX_TRADES_PER_DAY:
            errors.append(
                "MAX_TRADES_PER_DAY_REACHED"
            )

        # Account permission
        account = self.get_account()

        if account.get("status") != "OK":

            errors.append(
                "ACCOUNT_INFORMATION_UNAVAILABLE"
            )

        else:

            if not account["trade_allowed"]:
                errors.append(
                    "ACCOUNT_TRADING_NOT_ALLOWED"
                )

            if not account["trade_expert"]:
                errors.append(
                    "EA_TRADING_NOT_ALLOWED"
                )

        # Broker volume validation
        volume_result = self.validate_volume(
            symbol,
            volume,
        )

        if not volume_result.get("approved"):
            errors.append(
                volume_result.get(
                    "reason",
                    "INVALID_VOLUME",
                )
            )

        result = {
            "approved": len(errors) == 0,
            "engine": self.ENGINE_NAME,
            "version": self.VERSION,
            "symbol": symbol,
            "side": side,
            "entry": entry,
            "stop_loss": float(stop_loss),
            "take_profit": float(take_profit),
            "volume": float(volume),
            "risk_reward": rr,

            # Explicitly report that there is no
            # application-level maximum risk percentage.
            "risk_cap": None,
            "risk_cap_enabled": False,

            "max_open_trades": self.MAX_OPEN_TRADES,
            "open_positions": len(positions),

            "max_trades_per_day":
                self.MAX_TRADES_PER_DAY,

            "trades_today": today,

            "minimum_risk_reward":
                self.MIN_RISK_REWARD,

            "enforce_min_rr":
                self.ENFORCE_MIN_RR,

            "broker_volume":
                volume_result,

            "errors": errors,
        }

        self.last_result = result

        return result

    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:

        account = self.get_account()

        return {
            "engine": self.ENGINE_NAME,
            "version": self.VERSION,

            "risk_cap": None,
            "risk_cap_enabled": False,

            "max_open_trades":
                self.MAX_OPEN_TRADES,

            "max_trades_per_day":
                self.MAX_TRADES_PER_DAY,

            "minimum_risk_reward":
                self.MIN_RISK_REWARD,

            "enforce_min_rr":
                self.ENFORCE_MIN_RR,

            "account":
                account,

            "open_positions":
                len(self.open_positions()),

            "trades_today":
                self.trades_today(),
        }
