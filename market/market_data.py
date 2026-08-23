from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import MetaTrader5 as mt5


class MarketData:
    """
    SUPPLY & DEMAND MT5
    MARKET DATA ENGINE

    REAL MT5 DATA ONLY
    READ-ONLY
    NO SIMULATION
    NO HARDCODED PRICES
    NO TRADE EXECUTION
    """

    VERSION = "1.1.0"
    READ_ONLY = True
    EXECUTION_ENABLED = False
    SIMULATION_ENABLED = False

    SUPPORTED_TIMEFRAMES = {
        "M1": mt5.TIMEFRAME_M1,
        "M2": mt5.TIMEFRAME_M2,
        "M3": mt5.TIMEFRAME_M3,
        "M4": mt5.TIMEFRAME_M4,
        "M5": mt5.TIMEFRAME_M5,
        "M6": mt5.TIMEFRAME_M6,
        "M10": mt5.TIMEFRAME_M10,
        "M12": mt5.TIMEFRAME_M12,
        "M15": mt5.TIMEFRAME_M15,
        "M20": mt5.TIMEFRAME_M20,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H2": mt5.TIMEFRAME_H2,
        "H3": mt5.TIMEFRAME_H3,
        "H4": mt5.TIMEFRAME_H4,
        "H6": mt5.TIMEFRAME_H6,
        "H8": mt5.TIMEFRAME_H8,
        "H12": mt5.TIMEFRAME_H12,
        "D1": mt5.TIMEFRAME_D1,
        "W1": mt5.TIMEFRAME_W1,
        "MN1": mt5.TIMEFRAME_MN1,
    }

    def __init__(self) -> None:
        self.connected = False
        self.last_error: Optional[Any] = None
        self.last_symbol: Optional[str] = None
        self.last_timeframe: Optional[str] = None
        self.last_count: Optional[int] = None

    # ==============================================================
    # CONNECTION
    # ==============================================================

    def connect(self) -> bool:
        try:
            connected = mt5.initialize()

        except Exception as exc:
            self.connected = False
            self.last_error = (
                -1,
                f"{type(exc).__name__}: {exc}",
            )
            return False

        if not connected:
            self.connected = False
            self.last_error = mt5.last_error()
            return False

        self.connected = True
        self.last_error = None
        return True

    # ==============================================================
    # DISCONNECT
    # ==============================================================

    def disconnect(self) -> None:
        try:
            mt5.shutdown()
        finally:
            self.connected = False

    # ==============================================================
    # CONNECTION CHECK
    # ==============================================================

    def is_connected(self) -> bool:
        if not self.connected:
            return False

        terminal = mt5.terminal_info()

        if terminal is None:
            self.connected = False
            self.last_error = mt5.last_error()
            return False

        self.connected = bool(
            getattr(
                terminal,
                "connected",
                False,
            )
        )

        return self.connected

    # ==============================================================
    # MT5 ERROR
    # ==============================================================

    def get_last_error(self) -> Any:
        try:
            self.last_error = mt5.last_error()
        except Exception as exc:
            self.last_error = (
                -1,
                f"{type(exc).__name__}: {exc}",
            )

        return self.last_error

    # ==============================================================
    # SYMBOL RESOLUTION
    # ==============================================================

    def resolve_symbol(
        self,
        requested_symbol: str,
    ) -> Optional[str]:

        if not requested_symbol:
            self.last_error = (
                -2,
                "Symbol cannot be empty.",
            )
            return None

        if not self.is_connected():
            if not self.connect():
                return None

        requested = str(
            requested_symbol
        ).strip()

        # Exact match.
        info = mt5.symbol_info(requested)

        if info is not None:
            if not info.visible:
                mt5.symbol_select(
                    requested,
                    True,
                )

            self.last_symbol = requested
            return requested

        # Case-insensitive exact match.
        symbols = mt5.symbols_get()

        if symbols is None:
            self.last_error = mt5.last_error()
            return None

        requested_upper = requested.upper()
        # Logical asset identifiers are deliberately resolved against broker
        # inventory.  GOLD accepts the internationally used XAU root without
        # assuming a broker suffix or an exact trade symbol.
        search_terms = ("GOLD", "XAU") if requested_upper == "GOLD" else (requested_upper,)

        for item in symbols:
            name = getattr(
                item,
                "name",
                "",
            )

            if str(name).upper() == requested_upper:
                if not getattr(
                    item,
                    "visible",
                    False,
                ):
                    mt5.symbol_select(
                        name,
                        True,
                    )

                self.last_symbol = name
                return name

        # Broker suffix/prefix search.
        candidates = []

        for item in symbols:
            name = getattr(
                item,
                "name",
                "",
            )

            name_upper = str(
                name
            ).upper()

            if any(name_upper.startswith(term) or term in name_upper for term in search_terms):
                candidates.append(name)

        if candidates:
            candidates.sort(key=lambda candidate: (
                not bool(getattr(mt5.symbol_info(candidate), "visible", False)),
                0 if str(candidate).upper().startswith("XAU") else 1,
                len(str(candidate)), str(candidate),
            ))
            resolved = candidates[0]

            mt5.symbol_select(
                resolved,
                True,
            )

            self.last_symbol = resolved
            return resolved

        self.last_error = (
            -2,
            (
                f"Unable to resolve symbol "
                f"'{requested_symbol}'. "
                f"Candidates={candidates[:10]}"
            ),
        )

        return None

    # ==============================================================
    # TIMEFRAME
    # ==============================================================

    def normalize_timeframe(
        self,
        timeframe: str,
    ) -> Optional[int]:

        if not timeframe:
            self.last_error = (
                -2,
                "Timeframe cannot be empty.",
            )
            return None

        value = str(
            timeframe
        ).strip().upper()

        constant = self.SUPPORTED_TIMEFRAMES.get(
            value
        )

        if constant is None:
            self.last_error = (
                -2,
                f"Unsupported timeframe: {value}",
            )
            return None

        return constant

    # ==============================================================
    # HISTORICAL CANDLES
    # ==============================================================

    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        count: int = 500,
    ) -> List[Dict[str, Any]]:

        if not self.is_connected():
            if not self.connect():
                raise RuntimeError(
                    f"MT5 connection failed: "
                    f"{self.last_error}"
                )

        if not isinstance(count, int):
            raise TypeError(
                "count must be an integer."
            )

        if count <= 0:
            raise ValueError(
                "count must be greater than zero."
            )

        resolved = self.resolve_symbol(
            symbol
        )

        if resolved is None:
            raise RuntimeError(
                f"Symbol resolution failed: "
                f"{symbol}; "
                f"error={self.last_error}"
            )

        mt5_timeframe = self.normalize_timeframe(
            timeframe
        )

        if mt5_timeframe is None:
            raise RuntimeError(
                f"Timeframe resolution failed: "
                f"{timeframe}; "
                f"error={self.last_error}"
            )

        self.last_symbol = resolved
        self.last_timeframe = str(
            timeframe
        ).strip().upper()
        self.last_count = count

        try:
            rates = mt5.copy_rates_from_pos(
                resolved,
                mt5_timeframe,
                0,
                count,
            )

        except Exception as exc:
            self.last_error = (
                -1,
                f"{type(exc).__name__}: {exc}",
            )

            raise RuntimeError(
                f"MT5 candle request failed: "
                f"{self.last_error}"
            ) from exc

        if rates is None:
            self.last_error = mt5.last_error()

            raise RuntimeError(
                "MT5 returned no candle data: "
                f"{self.last_error}"
            )

        if len(rates) == 0:
            self.last_error = mt5.last_error()

            raise RuntimeError(
                "MT5 returned zero candles: "
                f"{self.last_error}"
            )

        return [
            self._normalize_candle(candle)
            for candle in rates
        ]

    # ==============================================================
    # SINGLE CANDLE NORMALIZATION
    # ==============================================================

    @staticmethod
    def _normalize_candle(
        candle: Any,
    ) -> Dict[str, Any]:

        timestamp = candle["time"]

        if isinstance(
            timestamp,
            datetime,
        ):
            dt = timestamp

            if dt.tzinfo is None:
                dt = dt.replace(
                    tzinfo=timezone.utc,
                )
            else:
                dt = dt.astimezone(
                    timezone.utc,
                )

        else:
            dt = datetime.fromtimestamp(
                int(timestamp),
                tz=timezone.utc,
            )

        names = getattr(
            candle.dtype,
            "names",
            (),
        )

        return {
            "time": dt,
            "timestamp": int(timestamp),

            "open": float(
                candle["open"]
            ),

            "high": float(
                candle["high"]
            ),

            "low": float(
                candle["low"]
            ),

            "close": float(
                candle["close"]
            ),

            "tick_volume": int(
                candle["tick_volume"]
            )
            if "tick_volume" in names
            else 0,

            "spread": int(
                candle["spread"]
            )
            if "spread" in names
            else 0,

            "real_volume": int(
                candle["real_volume"]
            )
            if "real_volume" in names
            else 0,
        }

    # ==============================================================
    # TOP-DOWN DATA
    # ==============================================================

    def get_top_down_data(
        self,
        symbol: str,
        count: int = 500,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Complete Supply & Demand top-down dataset.

        D1  -> Primary higher-timeframe context
        H4  -> Major structure / supply-demand context
        H1  -> Intermediate structure / zone refinement
        M15 -> Setup / confirmation timeframe
        M5  -> Execution timeframe

        ALL DATA IS DIRECTLY FROM MT5.
        """

        return {
            "D1": self.get_candles(
                symbol,
                "D1",
                count,
            ),

            "H4": self.get_candles(
                symbol,
                "H4",
                count,
            ),

            "H1": self.get_candles(
                symbol,
                "H1",
                count,
            ),

            "M15": self.get_candles(
                symbol,
                "M15",
                count,
            ),

            "M5": self.get_candles(
                symbol,
                "M5",
                count,
            ),
        }

    # ==============================================================
    # CURRENT TICK
    # ==============================================================

    def get_tick(
        self,
        symbol: str,
    ) -> Dict[str, Any]:

        if not self.is_connected():
            if not self.connect():
                raise RuntimeError(
                    f"MT5 connection failed: "
                    f"{self.last_error}"
                )

        resolved = self.resolve_symbol(
            symbol
        )

        if resolved is None:
            raise RuntimeError(
                f"Unable to resolve symbol: "
                f"{symbol}"
            )

        tick = mt5.symbol_info_tick(
            resolved
        )

        if tick is None:
            self.last_error = mt5.last_error()

            raise RuntimeError(
                f"MT5 tick unavailable: "
                f"{self.last_error}"
            )

        return {
            "symbol": resolved,

            "time": datetime.fromtimestamp(
                int(tick.time),
                tz=timezone.utc,
            ),

            "timestamp": int(
                tick.time
            ),

            "bid": float(
                tick.bid
            ),

            "ask": float(
                tick.ask
            ),

            "last": float(
                getattr(
                    tick,
                    "last",
                    0.0,
                )
            ),

            "volume": int(
                getattr(
                    tick,
                    "volume",
                    0,
                )
            ),
        }


__all__ = [
    "MarketData",
]
