import unittest
from main import SupplyDemandApplication
from strategy.top_down import TopDownEngine
from strategy.entry_engine import EntryEngine
from tests.test_end_to_end import MockMarketData
class OrchestrationTests(unittest.TestCase):
    def test_read_only_gate_or_no_trade(self):
        app=SupplyDemandApplication(MockMarketData(),TopDownEngine(MockMarketData()),EntryEngine())
        self.assertIn(app.run_cycle()["status"],("EXECUTION_GATED","NO_TRADE"))
