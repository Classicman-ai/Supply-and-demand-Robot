"""Safe orchestration for the Supply/Demand analysis cycle."""
from __future__ import annotations
import logging
import signal
import time
from dataclasses import dataclass, field
from typing import Any

import config
from strategy.entry_engine import EntryEngine
from strategy.top_down import TopDownEngine

LOG = logging.getLogger("supply_demand")

@dataclass
class SupplyDemandApplication:
    market_data: Any
    top_down: TopDownEngine
    entry_engine: EntryEngine
    risk_manager: Any | None = None
    execution_engine: Any | None = None
    seen_signals: set[tuple[str, str]] = field(default_factory=set)
    running: bool = True

    def run_cycle(self, instrument_request: str | None = None) -> dict[str, Any]:
        requested = instrument_request or config.INSTRUMENT_REQUEST
        try:
            if not self.market_data.connect():
                return {"status": "RECOVERABLE_ERROR", "stage": "CONNECT", "error": self.market_data.get_last_error()}
            symbol = self.market_data.resolve_symbol(requested)
            if not symbol:
                return {"status": "RECOVERABLE_ERROR", "stage": "SYMBOL_RESOLUTION", "requested_symbol": requested}
            analysis = self.top_down.analyze(symbol, config.HISTORY_CANDLES)
            setup = self.entry_engine.evaluate(analysis)
            if setup["status"] != "SETUP": return {"status": "NO_TRADE", "analysis": analysis, "setup": setup}
            key = (setup["symbol"], setup["zone_id"])
            if key in self.seen_signals: return {"status": "NO_TRADE", "setup": setup, "reason": "DUPLICATE_SIGNAL"}
            self.seen_signals.add(key)
            if self.risk_manager:
                volume = setup.get("volume", getattr(config, "DEMO_TEST_VOLUME", None))
                if volume is None:
                    return {"status": "RISK_REJECTED", "setup": setup, "risk": {"approved": False, "reason": "VOLUME_REQUIRED"}}
                setup["volume"] = volume
                risk = self.risk_manager.validate_trade(
                    setup["symbol"], setup["direction"], setup["entry"], setup["stop_loss"], setup["take_profit"], volume
                )
                if not risk.get("approved"): return {"status": "RISK_REJECTED", "setup": setup, "risk": risk}
            if config.READ_ONLY or not config.EXECUTION_ENABLED:
                return {"status": "EXECUTION_GATED", "setup": setup, "reason": "READ_ONLY_OR_EXECUTION_DISABLED"}
            if not self.execution_engine: return {"status": "EXECUTION_GATED", "setup": setup, "reason": "EXECUTION_ENGINE_UNAVAILABLE"}
            import MetaTrader5 as mt5
            terminal, account = mt5.terminal_info(), mt5.account_info()
            if terminal is None or account is None:
                return {"status": "EXECUTION_GATED", "setup": setup, "reason": "TERMINAL_OR_ACCOUNT_UNAVAILABLE"}
            if getattr(config, "REQUIRE_DEMO_ACCOUNT", True) and account.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO:
                return {"status": "EXECUTION_GATED", "setup": setup, "reason": "DEMO_ACCOUNT_REQUIRED"}
            if not terminal.trade_allowed:
                return {"status": "EXECUTION_GATED", "setup": setup, "reason": "TERMINAL_AUTOTRADING_DISABLED"}
            return {"status": "EXECUTION_RESULT", "setup": setup, "result": self.execution_engine.execute(
                setup["symbol"], setup["direction"], setup["volume"], setup["stop_loss"], setup["take_profit"],
                {"decision": setup["direction"], "symbol": setup["symbol"]})}
        except Exception as exc:
            LOG.exception("analysis cycle failed")
            return {"status": "RECOVERABLE_ERROR", "stage": "CYCLE", "error": f"{type(exc).__name__}: {exc}"}

    def run_forever(self) -> None:
        while self.running:
            started = time.monotonic(); result = self.run_cycle(); LOG.info("cycle status=%s duration=%.2fs", result["status"], time.monotonic()-started)
            time.sleep(max(1, config.ANALYSIS_CYCLE_SECONDS - (time.monotonic()-started)))

def build_application() -> SupplyDemandApplication:
    from market.market_data import MarketData
    from risk.risk_manager import RiskManager
    from execution.mt5_execution import MT5ExecutionEngine
    market_data = MarketData()
    return SupplyDemandApplication(market_data, TopDownEngine(market_data), EntryEngine(), RiskManager(market_data), MT5ExecutionEngine())

def main() -> None:
    logging.basicConfig(level=getattr(logging, config.LOG_LEVEL, logging.INFO))
    app = build_application()
    signal.signal(signal.SIGINT, lambda *_: setattr(app, "running", False))
    signal.signal(signal.SIGTERM, lambda *_: setattr(app, "running", False))
    app.run_forever()

if __name__ == "__main__": main()
