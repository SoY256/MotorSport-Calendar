import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from fetch_feeder_data import time_tbc, utc


class FeederTimeTests(unittest.TestCase):
    def test_unpublished_midnight_placeholder_keeps_the_local_day(self):
        session = {"startTime": "2026-12-06T00:00:00", "gmtOffset": "+04:00"}
        self.assertTrue(time_tbc(session))
        self.assertEqual(utc(session, "2026-12-06"), "2026-12-06T08:00:00Z")

    def test_published_time_is_converted_exactly(self):
        session = {"startTime": "2026-11-29T12:00:00", "gmtOffset": "+03:00"}
        self.assertFalse(time_tbc(session))
        self.assertEqual(utc(session, "2026-11-29"), "2026-11-29T09:00:00Z")


if __name__ == "__main__":
    unittest.main()
