
"""
MT5 EXECUTION ENGINE
====================

Institutional execution gateway for SUPPLY_DEMAND_MT5.

Design principles:
- Fail closed.
- Never execute NO_TRADE.
- Never bypass RiskManager.
- Never invent market/account data.
- Live execution remains disabled unless explicitly enabled
  through configuration.
- All broker constraints are validated before order submission.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
import math

import MetaTrader5 as mt5

try:
    import config
except Exception:
    config = None


class MT5ExecutionEngine:
    """
    MT5 order execution gateway.

    This class owns broker-facing order submission.
    It does not generate trading signals.
    """

    ENGINE_NAME = "MT5 EXECUTION ENGINE"
    VERSION = "1.0.0"

    READ_ONLY_TRADING = False

    EXECUTION_ENABLED = bool(
        getattr(config, "EXECUTION_ENABLED", False)
        if config is not None
        else False
    )

    SIMULATION_ENABLED = bool(
        getattr(config, "SIMULATION_ENABLED", False)
        if config is not None
        else False
    )

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


    def __init__(
        self,
        risk_manager: Any = None,
    ) -> None:
        self.risk_manager = risk_manager
        self.connected = False
        self.last_error: Optional[str] = None
        self.last_result: Optional[Dict[str, Any]] = None

    # --------------------------------------------------------
    # CONNECTION
    # --------------------------------------------------------

    def connect(self) -> bool:
        """Connect to the active MT5 terminal."""
        self.last_error = None

        if mt5.initialize():
            self.connected = True
            return True

        self.connected = False
        self.last_error = f"MT5 initialize failed: {mt5.last_error()}"
        return False

    def disconnect(self) -> None:
        """Disconnect from MT5."""
        if self.connected:
            mt5.shutdown()
        self.connected = False

    def is_connected(self) -> bool:
        return bool(self.connected)

    # --------------------------------------------------------
    # ACCOUNT
    # --------------------------------------------------------

    def get_account_info(self) -> Dict[str, Any]:
        """Read live account information directly from MT5."""
        info = mt5.account_info()

        if info is None:
            return {
                "status": "ERROR",
                "error": f"account_info failed: {mt5.last_error()}",
            }

        data = info._asdict()

        return {
            "status": "OK",
            "login": data.get("login"),
            "server": data.get("server"),
            "company": data.get("company"),
            "currency": data.get("currency"),
            "balance": float(data.get("balance", 0.0)),
            "equity": float(data.get("equity", 0.0)),
            "profit": float(data.get("profit", 0.0)),
            "margin": float(data.get("margin", 0.0)),
            "margin_free": float(data.get("margin_free", 0.0)),
            "margin_level": data.get("margin_level"),
            "leverage": data.get("leverage"),
            "trade_mode": data.get("trade_mode"),
            "trade_allowed": bool(data.get("trade_allowed", False)),
            "trade_expert": bool(data.get("trade_expert", False)),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # --------------------------------------------------------
    # MARKET
    # --------------------------------------------------------

    def get_symbol_info(self, symbol: str) -> Dict[str, Any]:
        requested_symbol = str(symbol).strip()
        resolved_symbol = requested_symbol

        try:
            symbols = mt5.symbols_get()
            if symbols:
                requested_upper = requested_symbol.upper()
                exact = None

                for item in symbols:
                    if item and item.name.upper() == requested_upper:
                        exact = item.name
                        break

                if exact:
                    resolved_symbol = exact
                else:
                    candidates = []
                    for item in symbols:
                        if not item:
                            continue
                        name_upper = item.name.upper()
                        if name_upper.startswith(requested_upper):
                            candidates.append(item.name)

                    if candidates:
                        resolved_symbol = candidates[0]
        except Exception:
            resolved_symbol = requested_symbol

        info = mt5.symbol_info(resolved_symbol)

        if info is None:
            return {
                "status": "ERROR",
                "symbol": requested_symbol,
                "requested_symbol": requested_symbol,
                "resolved_symbol": resolved_symbol,
                "error": f"symbol_info failed: {mt5.last_error()}",
            }

        if not info.visible:
            if not mt5.symbol_select(resolved_symbol, True):
                return {
                    "status": "ERROR",
                    "symbol": symbol,
                    "error": f"symbol_select failed: {mt5.last_error()}",
                }

            info = mt5.symbol_info(resolved_symbol)

        return {
            "status": "OK",
            "symbol": resolved_symbol,
            "requested_symbol": requested_symbol,
            "resolved_symbol": resolved_symbol,
            "digits": int(info.digits),
            "point": float(info.point),
            "trade_tick_size": float(info.trade_tick_size),
            "trade_tick_value": float(info.trade_tick_value),
            "trade_tick_value_profit": float(
                getattr(info, "trade_tick_value_profit", 0.0)
            ),
            "trade_tick_value_loss": float(
                getattr(info, "trade_tick_value_loss", 0.0)
            ),
            "volume_min": float(info.volume_min),
            "volume_max": float(info.volume_max),
            "volume_step": float(info.volume_step),
            "contract_size": float(info.trade_contract_size),
            "trade_mode": int(info.trade_mode),
            "filling_mode": int(info.filling_mode),
            "stops_level": int(info.trade_stops_level),
            "freeze_level": int(info.trade_freeze_level),
        }

    def get_current_tick(self, symbol: str) -> Dict[str, Any]:
        requested_symbol = str(symbol).strip()
        resolved_symbol = requested_symbol

        try:
            symbols = mt5.symbols_get()
            if symbols:
                requested_upper = requested_symbol.upper()
                exact = None

                for item in symbols:
                    if item and item.name.upper() == requested_upper:
                        exact = item.name
                        break

                if exact:
                    resolved_symbol = exact
                else:
                    candidates = []
                    for item in symbols:
                        if not item:
                            continue
                        name_upper = item.name.upper()
                        if name_upper.startswith(requested_upper):
                            candidates.append(item.name)

                    if candidates:
                        resolved_symbol = candidates[0]
        except Exception:
            resolved_symbol = requested_symbol

        tick = mt5.symbol_info_tick(resolved_symbol)

        if tick is None:
            return {
                "status": "ERROR",
                "symbol": requested_symbol,
                "requested_symbol": requested_symbol,
                "resolved_symbol": resolved_symbol,
                "error": f"symbol_info_tick failed: {mt5.last_error()}",
            }

        return {
            "status": "OK",
            "symbol": resolved_symbol,
            "requested_symbol": requested_symbol,
            "resolved_symbol": resolved_symbol,
            "bid": float(tick.bid),
            "ask": float(tick.ask),
            "last": float(tick.last),
            "volume": int(getattr(tick, "volume", 0)),
            "time": int(tick.time),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # --------------------------------------------------------
    # POSITIONS / TRADING LIMITS
    # --------------------------------------------------------

    def get_open_positions(
        self,
        symbol: Optional[str] = None,
    ) -> list:
        positions = (
            mt5.positions_get(symbol=symbol)
            if symbol
            else mt5.positions_get()
        )

        if positions is None:
            return []

        return [
            {
                "ticket": int(p.ticket),
                "symbol": p.symbol,
                "type": int(p.type),
                "volume": float(p.volume),
                "price_open": float(p.price_open),
                "sl": float(p.sl),
                "tp": float(p.tp),
                "profit": float(p.profit),
                "time": int(p.time),
                "magic": int(p.magic),
                "comment": p.comment,
            }
            for p in positions
        ]

    def get_open_position_count(self) -> int:
        return len(self.get_open_positions())

    def get_trade_history_today(self) -> list:
        """
        Return today's MT5 deal history.

        This is used for the hard daily-trade limit.
        """
        now = datetime.now()
        start = datetime(
            now.year,
            now.month,
            now.day,
        )

        deals = mt5.history_deals_get(start, now)

        if deals is None:
            return []

        results = []

        for deal in deals:
            data = deal._asdict()

            # Entry deals only count as new trades.
            entry = data.get("entry")

            if entry == mt5.DEAL_ENTRY_IN:
                results.append(data)

        return results

    def get_trades_today_count(self) -> int:
        return len(self.get_trade_history_today())

    # --------------------------------------------------------
    # VALIDATION
    # --------------------------------------------------------

    @staticmethod
    def _finite(value: Any) -> bool:
        try:
            return math.isfinite(float(value))
        except Exception:
            return False

    def calculate_risk_reward(
        self,
        side: str,
        entry: float,
        stop_loss: float,
        take_profit: float,
    ) -> float:
        side = str(side).upper()

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

    def validate_trade(
        self,
        symbol: str,
        side: str,
        entry: float,
        stop_loss: float,
        take_profit: float,
        volume: float,
    ) -> Dict[str, Any]:

        errors = []

        side = str(side).upper()

        if side not in ("BUY", "SELL"):
            errors.append("INVALID_SIDE")

        for name, value in (
            ("entry", entry),
            ("stop_loss", stop_loss),
            ("take_profit", take_profit),
            ("volume", volume),
        ):
            if not self._finite(value):
                errors.append(f"INVALID_{name.upper()}")

        if errors:
            return {
                "approved": False,
                "errors": errors,
            }

        entry = float(entry)
        stop_loss = float(stop_loss)
        take_profit = float(take_profit)
        volume = float(volume)

        if volume <= 0:
            errors.append("INVALID_VOLUME")

        if side == "BUY":
            if stop_loss >= entry:
                errors.append("BUY_STOP_MUST_BE_BELOW_ENTRY")

            if take_profit <= entry:
                errors.append("BUY_TP_MUST_BE_ABOVE_ENTRY")

        elif side == "SELL":
            if stop_loss <= entry:
                errors.append("SELL_STOP_MUST_BE_ABOVE_ENTRY")

            if take_profit >= entry:
                errors.append("SELL_TP_MUST_BE_BELOW_ENTRY")

        rr = self.calculate_risk_reward(
            side,
            entry,
            stop_loss,
            take_profit,
        )

        if rr < self.MIN_RISK_REWARD:
            errors.append(
                f"RR_BELOW_MINIMUM:{rr:.4f}<"
                f"{self.MIN_RISK_REWARD:.4f}"
            )

        symbol_info = self.get_symbol_info(symbol)

        if symbol_info.get("status") != "OK":
            errors.append("SYMBOL_INFORMATION_UNAVAILABLE")
        else:
            vmin = symbol_info["volume_min"]
            vmax = symbol_info["volume_max"]
            step = symbol_info["volume_step"]

            if volume < vmin:
                errors.append("VOLUME_BELOW_BROKER_MINIMUM")

            if volume > vmax:
                errors.append("VOLUME_ABOVE_BROKER_MAXIMUM")

            if step > 0:
                steps = volume / step
                if abs(steps - round(steps)) > 1e-8:
                    errors.append("VOLUME_INVALID_STEP")

        return {
            "approved": len(errors) == 0,
            "errors": errors,
            "symbol": symbol,
            "side": side,
            "entry": entry,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "volume": volume,
            "risk_reward": rr,
        }

    # --------------------------------------------------------
    # ORDER REQUEST
    # --------------------------------------------------------

    def build_order_request(
        self,
        symbol: str,
        side: str,
        volume: float,
        stop_loss: float,
        take_profit: float,
        magic: int = 260819,
        comment: str = "SUPPLY_DEMAND_MT5",
    ) -> Dict[str, Any]:

        tick = self.get_current_tick(symbol)

        if tick.get("status") != "OK":
            return {
                "status": "ERROR",
                "error": tick.get("error"),
            }

        side = str(side).upper()

        if side == "BUY":
            order_type = mt5.ORDER_TYPE_BUY
            price = tick["ask"]
        elif side == "SELL":
            order_type = mt5.ORDER_TYPE_SELL
            price = tick["bid"]
        else:
            return {
                "status": "ERROR",
                "error": "INVALID_SIDE",
            }

        return {
            "status": "OK",
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": tick.get("resolved_symbol", symbol),
            "requested_symbol": symbol,
            "resolved_symbol": tick.get("resolved_symbol", symbol),
            "volume": float(volume),
            "type": order_type,
            "price": float(price),
            "sl": float(stop_loss),
            "tp": float(take_profit),
            "deviation": 20,
            "magic": int(magic),
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

    # --------------------------------------------------------
    # EXECUTION
    # --------------------------------------------------------

    def execute(
        self,
        symbol: str,
        side: str,
        volume: float,
        stop_loss: float,
        take_profit: float,
        forecast: Optional[Dict[str, Any]] = None,
        magic: int = 260819,
        comment: str = "SUPPLY_DEMAND_MT5",
    ) -> Dict[str, Any]:
        """
        Execute an order only after all hard gates pass.

        This method is fail-closed.
        """

        result_base = {
            "engine": self.ENGINE_NAME,
            "version": self.VERSION,
            "symbol": symbol,
            "side": str(side).upper(),
            "execution_enabled": self.EXECUTION_ENABLED,
            "simulation_enabled": self.SIMULATION_ENABLED,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # ----------------------------------------------------
        # HARD GATE 1
        # ----------------------------------------------------

        if not self.EXECUTION_ENABLED:
            result = {
                **result_base,
                "status": "EXECUTION_BLOCKED",
                "reason": "EXECUTION_ENABLED_FALSE",
            }

            self.last_result = result
            return result

        # ----------------------------------------------------
        # HARD GATE 2
        # ----------------------------------------------------

        if not self.connected:
            if not self.connect():
                result = {
                    **result_base,
                    "status": "EXECUTION_BLOCKED",
                    "reason": "MT5_NOT_CONNECTED",
                    "error": self.last_error,
                }

                self.last_result = result
                return result

        # ----------------------------------------------------
        # HARD GATE 3
        # ----------------------------------------------------

        if forecast is not None:
            decision = str(
                forecast.get("decision", "NO_TRADE")
            ).upper()

            if decision not in ("BUY", "SELL"):
                result = {
                    **result_base,
                    "status": "EXECUTION_BLOCKED",
                    "reason": "FORECAST_NOT_EXECUTABLE",
                    "decision": decision,
                }

                self.last_result = result
                return result

            forecast_symbol = forecast.get("symbol")

            if (
                forecast_symbol
                and forecast_symbol != symbol
            ):
                result = {
                    **result_base,
                    "status": "EXECUTION_BLOCKED",
                    "reason": "FORECAST_SYMBOL_MISMATCH",
                    "forecast_symbol": forecast_symbol,
                }

                self.last_result = result
                return result

        # ----------------------------------------------------
        # ACCOUNT GATE
        # ----------------------------------------------------

        account = self.get_account_info()

        if account.get("status") != "OK":
            result = {
                **result_base,
                "status": "EXECUTION_BLOCKED",
                "reason": "ACCOUNT_INFORMATION_UNAVAILABLE",
                "account": account,
            }

            self.last_result = result
            return result

        if not account["trade_allowed"]:
            result = {
                **result_base,
                "status": "EXECUTION_BLOCKED",
                "reason": "ACCOUNT_TRADING_NOT_ALLOWED",
            }

            self.last_result = result
            return result

        # ----------------------------------------------------
        # POSITION LIMIT
        # ----------------------------------------------------

        open_count = self.get_open_position_count()

        if open_count >= self.MAX_OPEN_TRADES:
            result = {
                **result_base,
                "status": "EXECUTION_BLOCKED",
                "reason": "MAX_OPEN_TRADES_REACHED",
                "open_positions": open_count,
                "maximum": self.MAX_OPEN_TRADES,
            }

            self.last_result = result
            return result

        # ----------------------------------------------------
        # DAILY LIMIT
        # ----------------------------------------------------

        today_count = self.get_trades_today_count()

        if today_count >= self.MAX_TRADES_PER_DAY:
            result = {
                **result_base,
                "status": "EXECUTION_BLOCKED",
                "reason": "MAX_TRADES_PER_DAY_REACHED",
                "trades_today": today_count,
                "maximum": self.MAX_TRADES_PER_DAY,
            }

            self.last_result = result
            return result

        # ----------------------------------------------------
        # RISK MANAGER
        # ----------------------------------------------------

        if self.risk_manager is not None:
            risk_result = self.risk_manager.validate_trade(
                symbol=symbol,
                side=side,
                entry=None,
                stop_loss=stop_loss,
                take_profit=take_profit,
                volume=volume,
            )

            if not risk_result.get("approved", False):
                result = {
                    **result_base,
                    "status": "EXECUTION_BLOCKED",
                    "reason": "RISK_MANAGER_REJECTED",
                    "risk": risk_result,
                }

                self.last_result = result
                return result

        # ----------------------------------------------------
        # MARKET PRICE
        # ----------------------------------------------------

        tick = self.get_current_tick(symbol)

        if tick.get("status") != "OK":
            result = {
                **result_base,
                "status": "EXECUTION_BLOCKED",
                "reason": "CURRENT_TICK_UNAVAILABLE",
            }

            self.last_result = result
            return result

        entry = (
            tick["ask"]
            if str(side).upper() == "BUY"
            else tick["bid"]
        )

        # ----------------------------------------------------
        # ORDER VALIDATION
        # ----------------------------------------------------

        validation = self.validate_trade(
            symbol=symbol,
            side=side,
            entry=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            volume=volume,
        )

        if not validation["approved"]:
            result = {
                **result_base,
                "status": "EXECUTION_BLOCKED",
                "reason": "ORDER_VALIDATION_FAILED",
                "validation": validation,
            }

            self.last_result = result
            return result

        # ----------------------------------------------------
        # SIMULATION GATE
        # ----------------------------------------------------

        if self.SIMULATION_ENABLED:
            result = {
                **result_base,
                "status": "SIMULATED_ORDER",
                "request": {
                    "symbol": symbol,
                    "side": str(side).upper(),
                    "volume": volume,
                    "entry": entry,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                },
                "validation": validation,
            }

            self.last_result = result
            return result

        # ----------------------------------------------------
        # LIVE MT5 ORDER
        # ----------------------------------------------------

        request = self.build_order_request(
            symbol=symbol,
            side=side,
            volume=volume,
            stop_loss=stop_loss,
            take_profit=take_profit,
            magic=magic,
            comment=comment,
        )

        if request.get("status") != "OK":
            result = {
                **result_base,
                "status": "EXECUTION_BLOCKED",
                "reason": "ORDER_REQUEST_BUILD_FAILED",
                "request": request,
            }

            self.last_result = result
            return result

        check = mt5.order_check(request)

        if check is None:
            result = {
                **result_base,
                "status": "EXECUTION_BLOCKED",
                "reason": "MT5_ORDER_CHECK_FAILED",
                "error": str(mt5.last_error()),
                "request": request,
            }

            self.last_result = result
            return result

        check_data = check._asdict()

        # MT5 Python order_check() may return retcode=0 with
        # comment="Done" on a valid pre-trade check. The execution
        # retcodes (10008/10009/10010) apply to order_send(), not
        # necessarily to order_check().
        check_retcode = check_data.get("retcode")
        check_comment = str(check_data.get("comment", "")).strip().lower()

        check_passed = (
            check_retcode in (
                0,
                mt5.TRADE_RETCODE_DONE,
                mt5.TRADE_RETCODE_PLACED,
                mt5.TRADE_RETCODE_DONE_PARTIAL,
            )
            and check_comment in ("", "done", "ok")
        )

        if not check_passed:
            result = {
                **result_base,
                "status": "EXECUTION_BLOCKED",
                "reason": "MT5_ORDER_CHECK_REJECTED",
                "order_check": check_data,
                "request": request,
            }

            self.last_result = result
            return result

        sent = mt5.order_send(request)

        if sent is None:
            result = {
                **result_base,
                "status": "ORDER_FAILED",
                "reason": "MT5_ORDER_SEND_RETURNED_NONE",
                "error": str(mt5.last_error()),
            }

            self.last_result = result
            return result

        sent_data = sent._asdict()

        if sent.retcode not in (
            mt5.TRADE_RETCODE_DONE,
            mt5.TRADE_RETCODE_PLACED,
        ):
            result = {
                **result_base,
                "status": "ORDER_REJECTED",
                "reason": "MT5_ORDER_REJECTED",
                "retcode": int(sent.retcode),
                "result": sent_data,
            }

            self.last_result = result
            return result

        result = {
            **result_base,
            "status": "ORDER_EXECUTED",
            "retcode": int(sent.retcode),
            "ticket": getattr(sent, "order", None),
            "deal": getattr(sent, "deal", None),
            "price": getattr(sent, "price", entry),
            "volume": getattr(sent, "volume", volume),
            "result": sent_data,
        }

        self.last_result = result
        return result

    # --------------------------------------------------------
    # POSITION MANAGEMENT
    # --------------------------------------------------------

    def modify_position_protection(
        self,
        ticket: int,
        stop_loss: float,
        take_profit: float,
        deviation: int = 20,
    ) -> Dict[str, Any]:
        """Safely modify SL/TP of an existing position without changing volume."""

        if not self.EXECUTION_ENABLED:
            return {
                "status": "EXECUTION_BLOCKED",
                "reason": "EXECUTION_ENABLED_FALSE",
                "ticket": int(ticket),
            }

        positions = mt5.positions_get(ticket=int(ticket))

        if not positions:
            return {
                "status": "ERROR",
                "reason": "POSITION_NOT_FOUND",
                "ticket": int(ticket),
            }

        position = positions[0]
        symbol = position.symbol

        try:
            stop_loss = float(stop_loss)
            take_profit = float(take_profit)
        except (TypeError, ValueError):
            return {
                "status": "ERROR",
                "reason": "INVALID_PROTECTION_VALUES",
                "ticket": int(ticket),
                "symbol": symbol,
            }

        if stop_loss <= 0 or take_profit <= 0:
            return {
                "status": "ERROR",
                "reason": "INVALID_PROTECTION_VALUES",
                "ticket": int(ticket),
                "symbol": symbol,
            }

        tick = self.get_current_tick(symbol)

        if tick.get("status") != "OK":
            return {
                "status": "ERROR",
                "reason": "CURRENT_TICK_UNAVAILABLE",
                "ticket": int(ticket),
                "symbol": symbol,
            }

        bid = float(tick["bid"])
        ask = float(tick["ask"])

        if position.type == mt5.POSITION_TYPE_BUY:
            if stop_loss >= bid:
                return {
                    "status": "REJECTED",
                    "reason": "INVALID_BUY_STOP_LOSS",
                    "ticket": int(ticket),
                    "symbol": symbol,
                    "bid": bid,
                    "stop_loss": stop_loss,
                }

            if take_profit <= bid:
                return {
                    "status": "REJECTED",
                    "reason": "INVALID_BUY_TAKE_PROFIT",
                    "ticket": int(ticket),
                    "symbol": symbol,
                    "bid": bid,
                    "take_profit": take_profit,
                }

        elif position.type == mt5.POSITION_TYPE_SELL:
            if stop_loss <= ask:
                return {
                    "status": "REJECTED",
                    "reason": "INVALID_SELL_STOP_LOSS",
                    "ticket": int(ticket),
                    "symbol": symbol,
                    "ask": ask,
                    "stop_loss": stop_loss,
                }

            if take_profit >= ask:
                return {
                    "status": "REJECTED",
                    "reason": "INVALID_SELL_TAKE_PROFIT",
                    "ticket": int(ticket),
                    "symbol": symbol,
                    "ask": ask,
                    "take_profit": take_profit,
                }

        else:
            return {
                "status": "ERROR",
                "reason": "UNKNOWN_POSITION_TYPE",
                "ticket": int(ticket),
                "symbol": symbol,
                "position_type": int(position.type),
            }

        info = self.get_symbol_info(symbol)

        if info.get("status") != "OK":
            return {
                "status": "ERROR",
                "reason": "SYMBOL_INFORMATION_UNAVAILABLE",
                "ticket": int(ticket),
                "symbol": symbol,
            }

        digits = int(info["digits"])
        point = float(info["point"])

        stop_loss = round(stop_loss, digits)
        take_profit = round(take_profit, digits)

        stops_level = int(info.get("stops_level", 0))
        freeze_level = int(info.get("freeze_level", 0))
        protection_distance = max(stops_level, freeze_level) * point

        reference_price = bid if position.type == mt5.POSITION_TYPE_BUY else ask

        if protection_distance > 0:
            if position.type == mt5.POSITION_TYPE_BUY:
                if (reference_price - stop_loss) < protection_distance:
                    return {
                        "status": "REJECTED",
                        "reason": "STOP_LOSS_TOO_CLOSE",
                        "ticket": int(ticket),
                        "symbol": symbol,
                        "required_distance": protection_distance,
                        "reference_price": reference_price,
                        "stop_loss": stop_loss,
                    }

                if (take_profit - reference_price) < protection_distance:
                    return {
                        "status": "REJECTED",
                        "reason": "TAKE_PROFIT_TOO_CLOSE",
                        "ticket": int(ticket),
                        "symbol": symbol,
                        "required_distance": protection_distance,
                        "reference_price": reference_price,
                        "take_profit": take_profit,
                    }

            else:
                if (stop_loss - reference_price) < protection_distance:
                    return {
                        "status": "REJECTED",
                        "reason": "STOP_LOSS_TOO_CLOSE",
                        "ticket": int(ticket),
                        "symbol": symbol,
                        "required_distance": protection_distance,
                        "reference_price": reference_price,
                        "stop_loss": stop_loss,
                    }

                if (reference_price - take_profit) < protection_distance:
                    return {
                        "status": "REJECTED",
                        "reason": "TAKE_PROFIT_TOO_CLOSE",
                        "ticket": int(ticket),
                        "symbol": symbol,
                        "required_distance": protection_distance,
                        "reference_price": reference_price,
                        "take_profit": take_profit,
                    }

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": symbol,
            "position": int(position.ticket),
            "sl": stop_loss,
            "tp": take_profit,
            "magic": 260819,
            "comment": "SUPPLY_DEMAND_MT5_PROTECTION",
        }

        check = mt5.order_check(request)

        if check is None:
            return {
                "status": "ERROR",
                "reason": "MT5_ORDER_CHECK_FAILED",
                "ticket": int(ticket),
                "symbol": symbol,
                "error": str(mt5.last_error()),
                "request": request,
            }

        check_data = check._asdict()
        check_retcode = check_data.get("retcode")
        check_comment = str(
            check_data.get("comment", "")
        ).strip().lower()

        check_passed = (
            check_retcode in (
                0,
                mt5.TRADE_RETCODE_DONE,
                mt5.TRADE_RETCODE_PLACED,
                mt5.TRADE_RETCODE_DONE_PARTIAL,
                mt5.TRADE_RETCODE_NO_CHANGES,
            )
            and check_comment in ("", "done", "ok", "no changes")
        )

        if not check_passed:
            result = {
                "status": "REJECTED",
                "reason": "MT5_PROTECTION_ORDER_CHECK_REJECTED",
                "ticket": int(ticket),
                "symbol": symbol,
                "order_check": check_data,
                "request": request,
            }
            self.last_result = result
            return result

        sent = mt5.order_send(request)

        if sent is None:
            result = {
                "status": "ERROR",
                "reason": "MT5_PROTECTION_ORDER_SEND_FAILED",
                "ticket": int(ticket),
                "symbol": symbol,
                "error": str(mt5.last_error()),
                "request": request,
                "order_check": check_data,
            }
            self.last_result = result
            return result

        data = sent._asdict()

        accepted_retcodes = (
            mt5.TRADE_RETCODE_DONE,
            mt5.TRADE_RETCODE_PLACED,
            mt5.TRADE_RETCODE_NO_CHANGES,
        )

        if sent.retcode not in accepted_retcodes:
            result = {
                "status": "REJECTED",
                "reason": "MT5_PROTECTION_ORDER_REJECTED",
                "ticket": int(ticket),
                "symbol": symbol,
                "retcode": int(sent.retcode),
                "result": data,
                "request": request,
                "order_check": check_data,
            }
            self.last_result = result
            return result

        result = {
            "status": (
                "PROTECTION_UPDATED"
                if sent.retcode != mt5.TRADE_RETCODE_NO_CHANGES
                else "PROTECTION_UNCHANGED"
            ),
            "ticket": int(ticket),
            "symbol": symbol,
            "volume": float(position.volume),
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "retcode": int(sent.retcode),
            "result": data,
            "order_check": check_data,
        }

        self.last_result = result
        return result

    def close_position(
        self,
        ticket: int,
        deviation: int = 20,
    ) -> Dict[str, Any]:
        """Close an existing MT5 position."""

        if not self.EXECUTION_ENABLED:
            return {
                "status": "EXECUTION_BLOCKED",
                "reason": "EXECUTION_ENABLED_FALSE",
                "ticket": ticket,
            }

        positions = mt5.positions_get(ticket=int(ticket))

        if not positions:
            return {
                "status": "ERROR",
                "reason": "POSITION_NOT_FOUND",
                "ticket": ticket,
            }

        position = positions[0]

        tick = self.get_current_tick(position.symbol)

        if tick.get("status") != "OK":
            return {
                "status": "ERROR",
                "reason": "CURRENT_TICK_UNAVAILABLE",
            }

        if position.type == mt5.POSITION_TYPE_BUY:
            order_type = mt5.ORDER_TYPE_SELL
            price = tick["bid"]
        else:
            order_type = mt5.ORDER_TYPE_BUY
            price = tick["ask"]

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": position.symbol,
            "volume": float(position.volume),
            "type": order_type,
            "position": int(position.ticket),
            "price": float(price),
            "deviation": int(deviation),
            "magic": 260819,
            "comment": "SUPPLY_DEMAND_MT5_CLOSE",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        sent = mt5.order_send(request)

        if sent is None:
            return {
                "status": "ERROR",
                "reason": "MT5_ORDER_SEND_FAILED",
                "error": str(mt5.last_error()),
            }

        data = sent._asdict()

        if sent.retcode not in (
            mt5.TRADE_RETCODE_DONE,
            mt5.TRADE_RETCODE_PLACED,
        ):
            return {
                "status": "REJECTED",
                "retcode": int(sent.retcode),
                "result": data,
            }

        return {
            "status": "POSITION_CLOSED",
            "ticket": int(ticket),
            "retcode": int(sent.retcode),
            "result": data,
        }

    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    def get_execution_status(self) -> Dict[str, Any]:
        return {
            "engine": self.ENGINE_NAME,
            "version": self.VERSION,
            "connected": self.connected,
            "read_only_trading": self.READ_ONLY_TRADING,
            "execution_enabled": self.EXECUTION_ENABLED,
            "simulation_enabled": self.SIMULATION_ENABLED,
            "max_open_trades": self.MAX_OPEN_TRADES,
            "max_trades_per_day": self.MAX_TRADES_PER_DAY,
            "minimum_risk_reward": self.MIN_RISK_REWARD,
            "last_error": self.last_error,
        }




