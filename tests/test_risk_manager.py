import importlib, sys, types, unittest
class RiskTests(unittest.TestCase):
    def test_invalid_volume_is_rejected_without_mt5_call(self):
        fake=types.SimpleNamespace(); sys.modules["MetaTrader5"]=fake
        module=importlib.import_module("risk.risk_manager")
        self.assertFalse(module.RiskManager().validate_volume("GOLDm",0)["approved"])
