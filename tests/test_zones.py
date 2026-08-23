from datetime import datetime, timezone
import unittest
from models.zones import Zone, ZoneType

class ZoneTests(unittest.TestCase):
    def test_zone_contract_round_trip(self):
        zone=Zone("z","GOLDm","H1",ZoneType.DEMAND,101,100,datetime.now(timezone.utc),datetime.now(timezone.utc))
        self.assertEqual(Zone.from_dict(zone.to_dict()).zone_id,"z")
    def test_rejects_invalid_prices(self):
        with self.assertRaises(ValueError): Zone("z","GOLD","H1",ZoneType.SUPPLY,100,100,datetime.now(),datetime.now())
