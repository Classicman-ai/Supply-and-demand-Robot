import unittest
from tests.test_zone_detector import candles
from strategy.top_down import TopDownEngine
from strategy.entry_engine import EntryEngine
class MockMarketData:
    def connect(self): return True
    def get_last_error(self): return None
    def resolve_symbol(self,symbol): return "GOLDm"
    def get_top_down_data(self,symbol,bars): return {tf:candles() for tf in ("D1","H4","H1","M15","M5")}
class EndToEndTests(unittest.TestCase):
    def test_data_to_no_execution_setup(self):
        analysis=TopDownEngine(MockMarketData()).analyze("GOLD",20)
        self.assertEqual(analysis["status"],"OK")
        setup=EntryEngine().evaluate(analysis)
        self.assertIn(setup["status"],("SETUP","NO_TRADE"))
