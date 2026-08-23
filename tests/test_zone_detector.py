from datetime import datetime, timedelta, timezone
import unittest
from strategy.zone_detector import ZoneDetector

def candles():
    now=datetime(2025,1,1,tzinfo=timezone.utc); rows=[]
    for i in range(20):
        o=100.0; c=100.2
        if i==6: o,c=100.1,103.2
        if i>6: o,c=100.1,100.3
        rows.append({"time":now+timedelta(minutes=5*i),"open":o,"high":max(o,c)+.5,"low":min(o,c)-.5,"close":c,"symbol":"GOLDm"})
    return rows
class DetectorTests(unittest.TestCase):
    def test_detects_demand_base_and_departure(self):
        zones=ZoneDetector().detect(candles(),"GOLDm","M5")
        self.assertTrue(any(z.zone_type.value=="DEMAND" for z in zones))
