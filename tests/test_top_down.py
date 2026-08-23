import unittest
from tests.test_end_to_end import MockMarketData
from strategy.top_down import TopDownEngine

class TopDownTests(unittest.TestCase):
    def test_canonical_chain_is_loaded(self):
        result=TopDownEngine(MockMarketData()).analyze("GOLD",20)
        self.assertEqual(tuple(result["timeframes"]),("D1","H4","H1","M15","M5"))
