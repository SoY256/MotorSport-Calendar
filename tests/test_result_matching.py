import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import fetch_imsa_results
import fetch_indycar_results


def event(event_id, name, circuit, locality, start):
    return {"id": event_id, "name": name, "circuit": {"name": circuit, "locality": locality},
            "sessions": [{"type": "R", "startTimeUtc": start}]}


def alkamel_url(code, stamp):
    return (f"https://imsa.results.alkamelcloud.com/Results/26_2026/{code}/"
            f"01_IMSA%20WeatherTech%20SportsCar%20Championship/{stamp}_Race/03_Results_Race_Official.JSON")


class ImsaMatchingTests(unittest.TestCase):
    calendar = [
        event("detroit", "Detroit Sports Car Classic", "Detroit Street Circuit", "Detroit", "2026-05-30T19:00:00Z"),
        event("road-america", "Motul SportsCar Endurance Grand Prix", "Road America", "Elkhart Lake",
              "2026-08-02T16:00:00Z"),
        event("ims", "Battle on the Bricks", "Indianapolis Motor Speedway", "Indianapolis", "2026-09-20T19:00:00Z"),
        event("petit", "Motul Petit Le Mans", "Michelin Raceway Road Atlanta", "Braselton", "2026-10-03T16:00:00Z"),
    ]

    def match(self, code, stamp):
        found = fetch_imsa_results.calendar_event(self.calendar, code, alkamel_url(code, stamp))
        return found and found["id"]

    def test_venue_aliases_and_race_day_match(self):
        self.assertEqual(self.match("11_Detroit Street Course", "202605301610"), "detroit")
        self.assertEqual(self.match("16_Road America", "202608021040"), "road-america")
        self.assertEqual(self.match("20_Indianapolis Motor Speedway RC", "202609201510"), "ims")
        self.assertEqual(self.match("21_Road Atlanta", "202610031210"), "petit")

    def test_unknown_or_moved_events_are_skipped_not_shifted(self):
        self.assertIsNone(self.match("12_Mid-Ohio Sports Car Course", "202606141300"))
        # Same venue, but a different weekend (e.g. a cancelled and re-added round).
        self.assertIsNone(self.match("16_Road America", "202606211040"))

    def test_ambiguous_match_raises(self):
        calendar = self.calendar + [
            event("road-america-2", "Duplicate", "Road America", "Elkhart Lake", "2026-08-01T16:00:00Z")]
        with self.assertRaises(RuntimeError):
            fetch_imsa_results.calendar_event(calendar, "16_Road America", alkamel_url("16_Road America", "202608021040"))

    def test_race_date_from_result_path(self):
        self.assertEqual(fetch_imsa_results.race_date(alkamel_url("21_Road Atlanta", "202610031210")),
                         date(2026, 10, 3))


class IndyMatchingTests(unittest.TestCase):
    calendar = [
        event("washington", "Washington", "Streets of Washington, D.C.", "Washington", "2026-08-23T17:00:00Z"),
        event("milwaukee-1", "Milwaukee 1", "Milwaukee Mile", "West Allis", "2026-08-29T18:30:00Z"),
        event("milwaukee-2", "Milwaukee 2", "Milwaukee Mile", "West Allis", "2026-08-30T17:00:00Z"),
        event("nashville", "Nashville", "Nashville Superspeedway", "Lebanon", "2026-07-19T19:00:00Z"),
        event("barber-1", "Barber Race 1", "Barber Motorsports Park", "Birmingham", "2026-03-29T17:00:00Z"),
        event("barber-2", "Barber Race 2", "Barber Motorsports Park", "Birmingham", "2026-03-30T17:00:00Z"),
    ]

    def match(self, day, number):
        found = fetch_indycar_results.calendar_event(self.calendar, day, number)
        return found and found["id"]

    def test_doubleheader_uses_race_number_even_after_rain_delay(self):
        # Race 1 was rain-delayed to Sunday, so both official dates are 8/30.
        self.assertEqual(self.match(date(2026, 8, 30), 1), "milwaukee-1")
        self.assertEqual(self.match(date(2026, 8, 30), 2), "milwaukee-2")
        self.assertEqual(self.match(date(2026, 3, 28), 1), "barber-1")
        self.assertEqual(self.match(date(2026, 3, 29), 2), "barber-2")

    def test_single_race_matches_by_date_window(self):
        self.assertEqual(self.match(date(2026, 7, 20), None), "nashville")
        self.assertEqual(self.match(date(2026, 8, 23), None), "washington")

    def test_unmatched_race_is_skipped(self):
        self.assertIsNone(self.match(date(2026, 10, 4), None))

    def test_doubleheader_without_race_number_is_ambiguous(self):
        with self.assertRaises(RuntimeError):
            self.match(date(2026, 8, 30), None)

    def test_official_race_number(self):
        self.assertEqual(fetch_indycar_results.official_race_number(
            {"EventName": "Grand Prix of Alabama Race 2", "Sessions": [{"SessionName": "Race"}]}), 2)
        self.assertEqual(fetch_indycar_results.official_race_number(
            {"EventName": "Snap-on Makers and Fixers 250",
             "Sessions": [{"SessionName": "Race"}, {"SessionName": "Qualifying - Race 1"}, {"SessionName": "Practice"}]}),
            1)
        self.assertIsNone(fetch_indycar_results.official_race_number(
            {"EventName": "Sonsio Grand Prix", "Sessions": [{"SessionName": "Race"}, {"SessionName": "Practice 1"}]}))

    def test_calendar_race_number(self):
        self.assertEqual(fetch_indycar_results.calendar_race_number({"name": "Milwaukee 2"}), 2)
        self.assertEqual(fetch_indycar_results.calendar_race_number({"name": "Barber Race 1"}), 1)
        self.assertIsNone(fetch_indycar_results.calendar_race_number({"name": "Indianapolis 500"}))


if __name__ == "__main__":
    unittest.main()
