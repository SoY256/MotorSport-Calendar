import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import fetch_wec_results


def index(*names):
    return "".join(f'<a href="Results/15_2026/06_X/{name}">pdf</a>' for name in names)


class WecClassificationTests(unittest.TestCase):
    def _url(self, html, hours=6):
        with patch.object(fetch_wec_results, "fetch", return_value=html.encode()):
            return fetch_wec_results.classification_url("06_X", hours)

    def test_mid_race_hourly_classification_is_not_final(self):
        html = index(
            "01_Hour%201/03_Classification_Race_Hour%201.PDF",
            "02_Hour%202/03_Classification_Race_Hour%202.PDF",
        )
        with self.assertRaises(fetch_wec_results.ClassificationUnavailable):
            self._url(html)

    def test_final_hour_is_selected_without_the_verified_suffix(self):
        html = index(
            "05_Hour%205/03_Classification_Race_Hour%205.PDF",
            "06_Hour%206/03_Classification_Race_Hour%206.PDF",
        )
        self.assertTrue(self._url(html).endswith("Hour%206.PDF"))

    def test_verified_final_wins(self):
        html = index(
            "06_Hour%206/03_Classification_Race_Hour%206.PDF",
            "06_Hour%206/03_Classification_Race_Hour%206_Final.PDF",
            "06_Hour%206/05_ClassificationByCategory_Race_Hour%206_Final.PDF",
        )
        self.assertTrue(self._url(html).endswith("03_Classification_Race_Hour%206_Final.PDF"))

    def test_le_mans_needs_hour_24(self):
        html = index("23_Hour%2023/03_Classification_Race_Hour%2023.PDF")
        with self.assertRaises(fetch_wec_results.ClassificationUnavailable):
            self._url(html, 24)


class WecCalendarTests(unittest.TestCase):
    def test_official_timetable_is_parsed_from_the_race_page(self):
        page = (
            '<div class="fw-bold lh-sm ">Free Practice 1</div>'
            '<div class="text-primary fst-italic"> <span data-local="11:30 AM" data-timestamp="1792143000">'
            '<div class="fw-bold lh-sm ">Qualifying - HYPERCAR</div>'
            '<div class="text-primary fst-italic"> <span data-local="03:40 PM" data-timestamp="1792244400">'
            '<div class="fw-bold lh-sm ">Race</div>'
            '<div class="text-primary fst-italic"> <span data-local="12:00 PM" data-timestamp="1792317600">'
            # Mobile duplicate of the same timetable.
            '<div class="fw-bold lh-sm ">Race</div>'
            '<div class="text-primary fst-italic"> <span data-local="12:00 PM" data-timestamp="1792317600">'
        )
        sessions = fetch_wec_results.official_timetable(page)
        self.assertEqual(
            [(item["type"], item["startTimeUtc"]) for item in sessions],
            [
                ("FP1", "2026-10-16T09:30:00Z"),
                ("QUALIFYING_HYPERCAR", "2026-10-17T13:40:00Z"),
                ("R", "2026-10-18T10:00:00Z"),
            ],
        )

    def test_race_pages_are_matched_by_venue(self):
        pages = fetch_wec_results.race_pages(
            '<a href="/en/race/24-hours-of-le-mans-2026"></a>'
            '<a href="/en/race/lone-star-le-mans-2026"></a>'
            '<a href="/en/race/official-prologue-imola-2026"></a>'
            '<a href="/en/race/6-hours-of-imola-2026"></a>'
        )
        self.assertEqual(
            fetch_wec_results.race_page_for({"name": "24 Hours of Le Mans"}, pages),
            "/en/race/24-hours-of-le-mans-2026",
        )
        self.assertEqual(
            fetch_wec_results.race_page_for({"name": "6 Hours of Imola"}, pages),
            "/en/race/6-hours-of-imola-2026",
        )

    def test_cancelled_middle_east_rounds_are_replaced(self):
        for base in ("data", "assets/data"):
            calendar = json.loads((ROOT / base / "wec/2026/calendar.json").read_text(encoding="utf-8"))["data"]
            rounds = {event["round"]: event for event in calendar}
            self.assertEqual(len(calendar), 8)
            self.assertEqual(rounds[7]["name"], "6 Hours of Barcelona")
            self.assertEqual(fetch_wec_results.race_session(rounds[7])["startTimeUtc"], "2026-10-18T10:00:00Z")
            self.assertEqual(rounds[7]["sessions"][0]["startTimeUtc"], "2026-10-16T09:30:00Z")
            self.assertEqual(rounds[8]["name"], "6 Hours of Monza")
            self.assertEqual(fetch_wec_results.race_session(rounds[8])["startTimeUtc"], "2026-11-08T10:00:00Z")
            for event in calendar:
                self.assertNotIn(event["circuit"]["countryCode"], {"QAT", "BHR"})
                self.assertTrue((ROOT / base / "wec/2026" / event["resultsPath"]).is_file())
                self.assertGreater(len(event["sessions"]), 1, event["name"])

    def test_every_calendar_event_is_matched_to_its_timing_page(self):
        calendar = json.loads((ROOT / "data/wec/2026/calendar.json").read_text(encoding="utf-8"))["data"]
        codes = ["01_IMOLA", "02_SPA FRANCORCHAMPS", "03_LE MANS", "04_SAO PAULO",
                 "05_CIRCUIT OF THE AMERICAS", "06_FUJI SPEEDWAY", "07_BARCELONA-CATALUNYA", "08_MONZA"]
        for event, code in zip(calendar, codes):
            self.assertEqual(fetch_wec_results.event_code(event, codes), code)


if __name__ == "__main__":
    unittest.main()
