import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import fetch_wec_results


def index(*names, event="06_X"):
    return "".join(
        f'<a href="Results/15_2026/{event}/679_FIA%20WEC/202609271100_Race/{name}">pdf</a>' for name in names
    )


QUALIFYING = """FIA WEC
Qualifying HYPERCAR
NoTeam Drivers Car Cat Ty Time Lap Total Gap Kph
HP 1 50Ferrari AF Corse A. FUOCO / M. MOLINA / N. NIELSEN Ferrari 499P HYPERCAR M 1:30.088 5 7 - - 196.2
HP 2 83AF Corse Y. YE / R. KUBICA / P. HANSON Ferrari 499P HYPERCAR M 1:30.215 5 6 +0.127+0.127 195.9
3 7Toyota Racing M. CONWAY / K. KOBAYASHI Toyota TR010 Hybrid HYPERCAR M 1:30.274 5 7 +0.186+0.059 195.8
12007Aston Martin Thor Team H. TINCKNELL / T. GAMBLE Aston Martin Valkyrie HYPERCAR M 1:30.806 5 8 +0.718+0.124 194.6
"""

RACE = """1 8 Toyota Racing S. BUEMI / B. HARTLEY Toyota TR010 Hybrid HYPERCAR M 213 6:00:10.939 0 7 1301:31.0 180.0
2 51 Ferrari AF Corse A. PIER GUIDI / J. CALADO Ferrari 499P HYPERCAR M 213 13.352 0 7 1301:31.0 180.0
3 13 13 Autosport O. FIDANI / L. KERN Corvette Z06 LMGT3.R LMGT3 G 38124:03:01.030 0 7 1301:31.0 180.0
87 Akkodis ASP Team P. UMBRÄRESCU / C. SCHMID Lexus RC F LMGT3 LMGT3 G 32 57:58.247 1 141:44.632168.9
"""


class WecParserTests(unittest.TestCase):
    def test_every_co_driver_is_kept_out_of_the_car_name(self):
        text = (
            "1 83 AF Corse Y. YE / R. KUBICA / P. HANSON Ferrari 499P HYPERCAR M 1:31.891 12 45 171.2\n"
            "2 20 BMW M Team WRT R. FRIJNS / S. VAN DER LINDE / R. RAST BMW M Hybrid V8 HYPERCAR M "
            "1:32.000 9 45 +0.109 170.9\n"
            "3 92 Manthey 1ST Phorm R. LIETZ / R. PERA / B. BARNICOAT Porsche 911 GT3 R LMGT3 G "
            "1:45.000 5 30 +0.200 150.0\n"
            "4 7 Toyota Gazoo Racing M. CONWAY / K. KOBAYASHI / N. DE VRIES Toyota TR010 Hybrid HYPERCAR M "
            "1:32.100 5 30 +0.300 150.0\n"
        )
        rows = fetch_wec_results.parse_session_rows(b"", {}, text=text)
        self.assertEqual(
            [(row["driver"]["givenName"], row["components"]["car"]) for row in rows],
            [
                ("Y. YE / R. KUBICA / P. HANSON", "Ferrari 499P"),
                ("R. FRIJNS / S. VAN DER LINDE / R. RAST", "BMW M Hybrid V8"),
                ("R. LIETZ / R. PERA / B. BARNICOAT", "Porsche 911 GT3 R"),
                ("M. CONWAY / K. KOBAYASHI / N. DE VRIES", "Toyota TR010 Hybrid"),
            ],
        )

    def test_qualifying_hyperpole_marker_and_glued_car_numbers(self):
        text = QUALIFYING.replace("12007Aston", "4007Aston")
        rows = fetch_wec_results.parse_session_rows(b"", {}, text=text)
        self.assertEqual([(row["position"], row["carNumber"]) for row in rows],
                         [(1, "50"), (2, "83"), (3, "7"), (4, "007")])
        self.assertEqual(rows[3]["team"]["name"], "Aston Martin Thor Team")
        self.assertEqual(rows[0]["time"], "1:30.088")
        self.assertEqual(rows[1]["components"]["gap"], "+0.127")

    def test_race_lists_unclassified_cars_without_a_position(self):
        text = RACE + "".join(
            f"{p} 9{p} Team {p} A. DRIVER / B. OTHER Car {p} HYPERCAR M 200 1 Lap\n" for p in range(4, 12)
        )
        rows = fetch_wec_results.parse_rows(b"", {}, text=text)
        third = rows[2]
        self.assertEqual((third["carNumber"], third["team"]["name"], third["laps"], third["time"]),
                         ("13", "13 Autosport", 381, "24:03:01.030"))
        unclassified = rows[3]
        self.assertEqual((unclassified["positionText"], unclassified["carNumber"], unclassified["classified"]),
                         ("NC", "87", False))
        self.assertTrue(all(row["classified"] for row in rows[4:]))

    def test_documents_of_another_event_are_ignored(self):
        html = index("06_Hour%206/03_Classification_Race_Hour%206_Final.PDF", event="07_OTHER")
        with patch.object(fetch_wec_results, "fetch", return_value=html.encode()):
            with self.assertRaises(fetch_wec_results.ClassificationUnavailable):
                fetch_wec_results.classification_url("06_X", 6)

    def test_session_folders_match_the_official_timetable_names(self):
        html = (
            '<a href="Results/15_2026/03_LE%20MANS/657_FIA%20WEC/202606101845_Qualifying%20LMP2-LMGT3/'
            '03_Classification_Qualifying%20LMP2-LMGT3_Final.PDF">x</a>'
            '<a href="Results/15_2026/03_LE%20MANS/658_FRJC/202606101845_Free%20Practice%201/'
            '03_Classification_Free%20Practice%201.PDF">x</a>'
        )
        documents = fetch_wec_results.session_classifications(fetch_wec_results.event_hrefs("03_LE MANS", html))
        self.assertIn(fetch_wec_results.session_key("Qualifying - LMP2 & LMGT3"), documents)
        self.assertNotIn(fetch_wec_results.session_key("Free Practice 1"), documents)


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
