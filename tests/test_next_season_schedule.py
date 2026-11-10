import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import fetch_next_season as next_season
import fetch_imsa_results as imsa_results


class ImsaNextSeasonTests(unittest.TestCase):
    def setUp(self):
        rounds = [
            ("Daytona International Speedway", "January 31", "24 HRS"),
            ("Sebring International Raceway", "March 20", "12 HRS"),
            ("Long Beach Street Circuit", "April 17", "1 HR 40 MIN"),
            ("WeatherTech Raceway Laguna Seca", "May 2", "2 HR 40 MIN"),
            ("Detroit Street Circuit", "June 5", "1 HR 40 MIN"),
            ("Watkins Glen International", "June 27", "6 HRS"),
            ("Canadian Tire Motorsport Park", "July 11", "2 HR 40 MIN"),
            ("Road America", "August 8", "6 HRS"),
            ("Virginia International Raceway", "August 22", "2 HR 40 MIN"),
            ("Indianapolis Motor Speedway", "September 19", "2 HR 40 MIN"),
            ("Michelin Raceway Road Atlanta", "October 9", "10 HRS"),
        ]
        self.previous = []
        self.cards = []
        for index, (venue, day, duration) in enumerate(rounds, start=1):
            self.previous.append({
                "name": f"Race {index}",
                "circuit": {"id": f"circuit-{index}", "name": venue, "locality": "City",
                            "country": "Country", "countryCode": "USA"},
            })
            self.cards.append(
                f'<article><h3>Race {index}</h3><p><svg><use href="#location"></use></svg>{venue}, City, FL</p>'
                f'<span><svg><use href="#imsa-time-rush"></use></svg>{duration}</span>'
                f'<p aria-label="{day}, 2027 through {day}, 2027"></p>'
                f'<a href="/events/2027-race-{index}?tab=schedule&amp;series=weathertech">Schedule</a></article>'
            )

    def page(self, cards=None):
        return (
            '<title>2027 Schedule</title><input value="weathertech" data-series-index="0">'
            '<ul data-series-index="0">'
            + "".join(self.cards if cards is None else cards)
            + '</ul><ul data-series-index="1"><article><h3>Pilot Challenge</h3></article></ul>'
        )

    def build(self, html=None):
        with patch.object(next_season, "get", return_value=self.page() if html is None else html) as get:
            events = next_season.imsa_calendar(2027, self.previous)
        get.assert_called_once_with("https://www.imsa.com/2027/schedule/")
        return events

    def test_reads_all_weathertech_rounds_with_official_durations_and_unconfirmed_times(self):
        events = self.build()
        self.assertEqual(len(events), 11)
        self.assertEqual([event["sessions"][0]["durationMinutes"] for event in events],
                         [1440, 720, 100, 160, 100, 360, 160, 360, 160, 160, 600])
        self.assertEqual(events[0]["sessions"][0]["startTimeUtc"], "2027-01-30T12:00:00Z")
        self.assertEqual(events[-1]["sessions"][0]["startTimeUtc"], "2027-10-09T12:00:00Z")
        self.assertTrue(all(event["sessions"][0]["timeTbc"] for event in events))
        self.assertEqual(events[0]["circuit"], self.previous[0]["circuit"])
        self.assertEqual(events[0]["url"], "https://www.imsa.com/events/2027-race-1")

    def test_incomplete_page_cannot_replace_the_calendar(self):
        with self.assertRaisesRegex(next_season.ParseError, "incomplete WeatherTech calendar"):
            self.build(self.page(self.cards[:3]))

    def test_unknown_venue_is_an_error_not_a_partially_published_calendar(self):
        self.previous = []
        with self.assertRaisesRegex(next_season.ParseError, "unknown venue"):
            self.build()

    def test_missing_duration_is_not_replaced_with_a_guessed_value(self):
        with self.assertRaisesRegex(next_season.ParseError, "missing race duration"):
            self.build(self.page().replace('href="#imsa-time-rush"', 'href="#unknown"', 1))

    def test_publish_includes_source_and_empty_future_results_and_standings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            next_season.publish("imsa", 2027, self.build(), root)
            folder = root / "imsa" / "2027"
            calendar = json.loads((folder / "calendar.json").read_text(encoding="utf-8"))
            self.assertEqual(calendar["source"]["url"], "https://www.imsa.com/2027/schedule/")
            self.assertEqual(len(calendar["data"]), 11)
            for event in calendar["data"]:
                result = json.loads((folder / event["resultsPath"]).read_text(encoding="utf-8"))
                self.assertEqual(result["data"], {"eventId": event["id"], "sessions": []})
            for name in ("standings_drivers.json", "standings_teams.json"):
                self.assertEqual(json.loads((folder / name).read_text(encoding="utf-8"))["data"], [])


class ImsaResultSeasonTests(unittest.TestCase):
    def test_timing_season_is_not_fixed_to_2026(self):
        for year in (2026, 2027):
            with self.subTest(year=year), patch.object(imsa_results, "SEASON", year), \
                    patch.object(imsa_results, "fetch", return_value=b'<option value="01_Daytona">Daytona</option>') as fetch:
                self.assertEqual(imsa_results.completed_event_codes(), ["01_Daytona"])
                fetch.assert_called_once_with(f"{imsa_results.BASE}?season={year - 2000}_{year}")

    def test_race_lookup_uses_the_same_selected_season(self):
        with patch.object(imsa_results, "SEASON", 2027), \
                patch.object(imsa_results, "fetch", return_value=b"no race published yet") as fetch:
            with self.assertRaises(RuntimeError):
                imsa_results.result_url("01_Daytona")
            fetch.assert_called_once_with(f"{imsa_results.BASE}?season=27_2027&evvent=01_Daytona")


if __name__ == "__main__":
    unittest.main()
