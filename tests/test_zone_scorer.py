import unittest
from tests.test_zone_detector import candles
from strategy.zone_detector import ZoneDetector
from strategy.zone_scorer import ZoneScorer
class ScorerTests(unittest.TestCase):
    def test_score_is_explainable(self):
        zone=ZoneDetector().detect(candles(),"GOLDm","M5")[0]; ZoneScorer().score(zone,100.2)
        self.assertGreaterEqual(zone.score,0); self.assertTrue(zone.score_reasons)
