"""
Historical Strategy Adapter
===========================

This module is the ONLY strategy/execution boundary used by
historical playback.

IMPORTANT:
- It never imports MetaTrader5.
- It never calls order_send().
- It never modifies live positions.
- It never connects to a live execution engine.

The adapter discovers the real Supply & Demand strategy modules
without inventing a replacement strategy.
"""

from __future__ import annotations

import importlib
import inspect
from dataclasses import dataclass
from typing import Any


@dataclass
class StrategyDecision:
    accepted: bool
    direction: str | None = None
    entry: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    reason: str = ""
    raw: Any = None


class HistoricalStrategyAdapter:

    VERSION = "1.0.0-HISTORICAL-SAFE"

    MODULES = (
        "strategy.supply_demand",
        "strategy.top_down",
        "strategy.zone_detector",
        "strategy.zone_validation",
        "strategy.zone_confluence",
        "strategy.zone_scorer",
        "strategy.entry_engine",
    )

    def __init__(self) -> None:
        self.modules: dict[str, Any] = {}
        self.classes: dict[str, type] = {}
        self.functions: dict[str, Any] = {}

        self._discover()

    def _discover(self) -> None:

        for module_name in self.MODULES:

            try:
                module = importlib.import_module(module_name)
            except Exception:
                continue

            self.modules[module_name] = module

            for name, obj in vars(module).items():

                if inspect.isclass(obj):
                    self.classes[name] = obj

                elif inspect.isfunction(obj):
                    self.functions[name] = obj

    def discovery_report(self) -> dict[str, Any]:

        return {
            "adapter_version": self.VERSION,
            "modules": sorted(self.modules),
            "classes": sorted(self.classes),
            "functions": sorted(self.functions),
        }

    def evaluate(self, *args, **kwargs) -> StrategyDecision:
        """
        Deliberately does NOT invent a strategy.

        The live strategy interface must be explicitly bound here
        once its actual callable contract is known.
        """

        raise RuntimeError(
            "REAL_STRATEGY_INTERFACE_NOT_BOUND: "
            "historical playback is safely blocked until the "
            "actual Supply & Demand strategy callable is connected."
        )
