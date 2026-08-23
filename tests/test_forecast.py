import unittest
from strategy.automatic_forecast import AutomaticForecastEngine
class ForecastTests(unittest.TestCase):
    def test_requires_explicit_dependencies(self):
        with self.assertRaises(ValueError): AutomaticForecastEngine(None,None,None,None,None,None)
