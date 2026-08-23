import unittest
from tests.test_end_to_end import MockMarketData
from strategy.top_down import TopDownEngine
from strategy.entry_engine import EntryEngine

class EntryTests(unittest.TestCase):
    def test_entry_never_bypasses_conditions(self):
        result=EntryEngine().evaluate(TopDownEngine(MockMarketData()).analyze("GOLD",20))
        self.assertIn(result["status"],("SETUP","NO_TRADE"))
