import importlib, sys, types, unittest
class SymbolResolutionTests(unittest.TestCase):
    def test_empty_request_is_rejected_without_terminal(self):
        fake=types.SimpleNamespace(); sys.modules["MetaTrader5"]=fake
        module=importlib.import_module("connector.mt5_connector")
        self.assertIsNone(module.MT5Connector().resolve_symbol(""))
