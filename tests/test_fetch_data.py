import json
import tempfile
import unittest
from pathlib import Path

from scripts.fetch_data import DataValidationError, adapt_result, adapt_schedule, adapt_standings, publish, utc_timestamp


def schedule_payload():
    return {"data": {"year": 2026, "events": [{
        "round": {"id": "round_1", "number": 1, "name": "Australian Grand Prix", "is_cancelled": False},
        "circuit": {"id": "circuit_1", "name": "Albert Park", "locality": "Melbourne",
                    "country": "Australia", "country_code": "AUS"},
        "schedule": [
            {"code": "FP1", "title": "Practice 1", "timestamp": "2026-03-06T01:30:00Z",
             "sessions": [{"is_cancelled": False}]},
            {"code": "SQ", "title": "Sprint Qualifying", "timestamp": "2026-03-06T05:30:00+00:00",
             "sessions": [{"is_cancelled": False}]},
            {"code": "SR", "title": "Sprint Race", "timestamp": "2026-03-07T04:00:00Z",
             "sessions": [{"is_cancelled": False}]},
            {"code": "R", "title": "Race", "timestamp": "2026-03-08T04:00:00Z",
             "sessions": [{"is_cancelled": False}]},
        ],
    }]}}


class AdapterTests(unittest.TestCase):
    def test_schedule_maps_every_weekend_session_and_utc(self):
        event = adapt_schedule(schedule_payload(), 2026)[0]
        self.assertEqual(["FP1", "SQ", "SPRINT", "R"], [item["type"] for item in event["sessions"]])
        self.assertTrue(all(item["startTimeUtc"].endswith("Z") for item in event["sessions"]))

    def test_result_does_not_leak_upstream_shape(self):
        payload = {"data": {"code": "R", "title": "Race", "timestamp": "2026-03-08T04:00:00Z", "results": [{
            "position": 1, "position_text": "1", "driver": {"id": "d1", "abbreviation": "AAA",
            "given_name": "A", "family_name": "Driver"}, "team": {"id": "t1", "name": "Team"},
            "points": 25, "components": {"GRID": {"position": 2}},
        }]}}
        result = adapt_result(payload)
        self.assertEqual("Driver", result["results"][0]["driver"]["familyName"])
        self.assertNotIn("given_name", json.dumps(result))

    def test_naive_timestamp_is_rejected(self):
        with self.assertRaises(DataValidationError):
            utc_timestamp("2026-03-08T04:00:00")

    def test_driver_standings_maps_all_entries(self):
        raw = {"position": "1", "points": "25", "wins": "1", "Driver": {
            "driverId": "driver", "code": "DRV", "givenName": "Test", "familyName": "Driver"
        }, "Constructors": [{"constructorId": "team"}]}
        payload = {"MRData": {"StandingsTable": {"StandingsLists": [{"DriverStandings": [raw, raw]}]}}}
        self.assertEqual(2, len(adapt_standings(payload, "drivers")))

    def test_failed_build_preserves_previous_data(self):
        class FailingClient:
            def get(self, _url):
                raise RuntimeError("offline")
        with tempfile.TemporaryDirectory() as temp:
            data = Path(temp) / "data"
            data.mkdir()
            (data / "manifest.json").write_text('{"old": true}', encoding="utf-8")
            with self.assertRaises(RuntimeError):
                publish(FailingClient(), data, 2026)
            self.assertEqual('{"old": true}', (data / "manifest.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
