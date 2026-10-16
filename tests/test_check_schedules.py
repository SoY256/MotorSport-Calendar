import json
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import check_schedules
from check_schedules import CalendarEvent, OfficialEvent, compare


def wec_card(slug, iso3, day, month):
    return f"""
    <div class="d-flex flex-column align-items-center text-center gap-2">
      <a class="d-flex flex-column align-items-center text-center gap-2 "
         href="/en/race/{slug}">
        <span class="flag:XX border border-light-subtle shadow-sm"></span>
        <span class="fs-5 ff-normal fw-extrabold text-white lh-1 ">{iso3}</span>
        <div class="d-flex flex-column align-items-center text-center text-uppercase text-primary">
          <strong class="fs-8 lh-sm">{day}</strong>
          <small class="fs-11">{month}</small>
        </div>
      </a>
    </div>"""


WEC_HTML = "".join([
    wec_card("official-prologue-imola-2026", "ITA", "17", "Apr"),
    wec_card("6-hours-of-imola-2026", "ITA", "19", "Apr"),
    wec_card("6-hours-of-barcelona-2026", "ESP", "18", "Oct"),
    wec_card("6-hours-of-monza-2026", "ITA", "08", "Nov"),
    wec_card("qatar-1812km-2027", "QAT", "20", "Feb"),
    # Mobile layout repeats the season strip; the header only links the flag.
    '<a href="/en/race/6-hours-of-barcelona-2026" class="next-race"><span class="flag:ES border"></span>'
    '<span class="ff-normal">Barcelona</span></a>',
    wec_card("6-hours-of-barcelona-2026", "ESP", "18", "Oct"),
    wec_card("6-hours-of-monza-2026", "ITA", "08", "Nov"),
])

F2_HTML = """
<div><span>ROUND 12</span><span>Baku</span><span>24 - 26 SEP</span></div>
<div><span>ROUND 13</span><span>Lusail</span><span>27 - 29 NOV</span><span>Upcoming</span></div>
<a><p>ROUND 12</p><p>24 - 26</p><p>Sep</p><img alt="Flag of Azerbaijan"><span>Flag of Azerbaijan</span>
   <p>Baku</p><p>Azerbaijan</p><p>Sprint Race</p><p>D. Beganovic</p><p>Feature Race 1</p><p>A. Dunne</p></a>
<a><p>ROUND 13</p><p>Next Race</p><span>Flag of Qatar</span><p>Lusail</p><p>Qatar</p><p>27 - 29</p><p>Nov</p></a>
<a><p>ROUND 14</p><span>Flag of United Arab Emirates</span><p>Yas Marina</p><p>Abu Dhabi</p>
   <p>04 - 06</p><p>Dec</p></a>
"""

IMSA_HTML = """
<a>Print Schedule</a><h3>Roar Before The Rolex 24</h3><p>Jan 16 - Jan 18</p><p>Daytona International Speedway</p>
<p>DURATION: N/A</p><a>Event Details</a><a>Buy Tickets</a>
<h3>Rolex 24 At DAYTONA</h3><p>Jan 21 - Jan 25</p><p>Daytona International Speedway</p><p>DURATION: 24 Hours</p>
<a>Event Details</a><a>Buy Tickets</a>
<h3>Motul Petit Le Mans</h3><p>Sep 30 - Oct 3</p><p>Michelin Raceway Road Atlanta</p><p>DURATION: 10 Hours</p>
<a>Event Details</a><a>Buy Tickets</a>
"""


class ParserTests(unittest.TestCase):
    def test_wec_ignores_next_season_and_prologue_and_dedupes(self):
        events = check_schedules.parse_wec(WEC_HTML, 2026)
        self.assertEqual(
            [(event.key, event.date) for event in events],
            [("ITA", date(2026, 4, 19)), ("ESP", date(2026, 10, 18)), ("ITA", date(2026, 11, 8))],
        )

    def test_wec_conflicting_duplicates_fail_loudly(self):
        html = WEC_HTML + wec_card("6-hours-of-monza-2026", "ITA", "15", "Nov")
        with self.assertRaises(check_schedules.ParseError):
            check_schedules.parse_wec(html, 2026)

    def test_fia_feeder_rounds_with_date_before_or_after_flag(self):
        events = check_schedules.parse_fia_feeder(F2_HTML, 2026)
        self.assertEqual(
            [(event.key, event.date) for event in events],
            [("AZE", date(2026, 9, 26)), ("QAT", date(2026, 11, 29)), ("ARE", date(2026, 12, 6))],
        )
        self.assertEqual(events[1].name, "Round 13 Qatar Lusail Qatar")

    def test_fia_feeder_unknown_country_is_a_parse_error(self):
        html = "<p>ROUND 1</p><span>Flag of Atlantis</span><p>01 - 03 May</p>"
        with self.assertRaises(check_schedules.ParseError):
            check_schedules.parse_fia_feeder(html, 2026)

    def test_imsa_skips_roar_test_and_uses_final_day(self):
        events = check_schedules.parse_imsa(IMSA_HTML, 2026)
        self.assertEqual(
            [(event.name, event.key, event.date) for event in events],
            [("Rolex 24 At DAYTONA", "daytona international speedway", date(2026, 1, 25)),
             ("Motul Petit Le Mans", "michelin raceway road atlanta", date(2026, 10, 3))],
        )


class CompareTests(unittest.TestCase):
    today = date(2026, 10, 16)
    ours = [
        CalendarEvent("6 Hours of Imola", "ITA", date(2026, 4, 19)),
        CalendarEvent("6 Hours of Barcelona", "ESP", date(2026, 10, 18)),
        CalendarEvent("6 Hours of Monza", "ITA", date(2026, 11, 8)),
    ]
    official = [
        OfficialEvent("imola", "ITA", date(2026, 4, 19)),
        OfficialEvent("barcelona", "ESP", date(2026, 10, 18)),
        OfficialEvent("monza", "ITA", date(2026, 11, 8)),
    ]

    def test_no_differences(self):
        self.assertEqual(compare(self.ours, self.official, self.today), [])

    def test_one_day_time_zone_offset_is_tolerated(self):
        official = self.official[:2] + [OfficialEvent("monza", "ITA", date(2026, 11, 9))]
        self.assertEqual(compare(self.ours, official, self.today), [])

    def test_cancelled_event_is_reported(self):
        ours = self.ours + [CalendarEvent("Qatar 1812km", "QAT", date(2026, 10, 24))]
        differences = compare(ours, self.official, self.today)
        self.assertEqual(len(differences), 1)
        self.assertIn("Qatar 1812km", differences[0])
        self.assertIn("no longer on the official schedule", differences[0])

    def test_new_official_event_is_reported(self):
        official = self.official + [OfficialEvent("bahrain", "BHR", date(2026, 11, 28))]
        differences = compare(self.ours, official, self.today)
        self.assertEqual(len(differences), 1)
        self.assertIn("bahrain", differences[0])
        self.assertIn("missing from our calendar", differences[0])

    def test_date_change_is_reported(self):
        official = self.official[:2] + [OfficialEvent("monza", "ITA", date(2026, 11, 15))]
        differences = compare(self.ours, official, self.today)
        self.assertEqual(len(differences), 1)
        self.assertIn("our race day 2026-11-08, official 2026-11-15", differences[0])

    def test_past_differences_are_ignored(self):
        official = [OfficialEvent("imola", "ITA", date(2026, 4, 26))] + self.official[1:]
        ours = self.ours + [CalendarEvent("Old round", "BHR", date(2026, 3, 1))]
        self.assertEqual(compare(ours, official, self.today), [])

    def test_locally_cancelled_event_still_on_official_list_is_reported(self):
        ours = self.ours[:2] + [CalendarEvent("6 Hours of Monza", "ITA", date(2026, 11, 8), cancelled=True)]
        differences = compare(ours, self.official, self.today)
        self.assertEqual(len(differences), 1)
        self.assertIn("monza", differences[0])


class RunChecksTests(unittest.TestCase):
    def test_parse_failures_are_not_reported_as_no_changes(self):
        def fetch(url):
            if "fiawec" in url:
                raise RuntimeError("network down")
            return "<html>maintenance</html>"

        report = check_schedules.run_checks(ROOT / "data", date(2026, 10, 16), fetch)
        self.assertEqual(report.exit_code, 2)
        self.assertIn("FIA WEC 2026", report.failures)
        self.assertIn("no events found", report.failures["FIA Formula 2 2026"])

    def test_differences_take_exit_code_one(self):
        report = check_schedules.Report({"X": ["changed"]}, {"Y": "down"}, [])
        self.assertEqual(report.exit_code, 1)
        self.assertIn("- changed", report.render())


class GitHubIssueTests(unittest.TestCase):
    def _sync(self, report, issues):
        calls = []

        def gh(*args):
            calls.append(args)
            return json.dumps(issues) if args[:2] == ("issue", "list") else ""

        with patch.object(check_schedules, "gh", side_effect=gh):
            check_schedules.sync_github_issue(report)
        return calls[1:]

    def test_creates_issue_for_differences(self):
        calls = self._sync(check_schedules.Report({"X": ["changed"]}, {}, []), [])
        self.assertEqual(calls[0][:4], ("issue", "create", "--title", "Official schedule changed"))

    def test_unchanged_body_is_not_edited(self):
        report = check_schedules.Report({"X": ["changed"]}, {}, [])
        body = self._sync(report, [])[0][5]
        calls = self._sync(report, [{"number": 7, "title": "Official schedule changed", "body": body}])
        self.assertEqual(calls, [])

    def test_changed_body_is_edited(self):
        report = check_schedules.Report({"X": ["changed"]}, {}, [])
        calls = self._sync(report, [{"number": 7, "title": "Official schedule changed", "body": "old"}])
        self.assertEqual(calls[0][:3], ("issue", "edit", "7"))

    def test_matching_schedule_closes_open_issue(self):
        report = check_schedules.Report({"X": []}, {}, [])
        calls = self._sync(report, [{"number": 7, "title": "Official schedule changed", "body": "old"}])
        self.assertEqual(calls[0][:3], ("issue", "close", "7"))


if __name__ == "__main__":
    unittest.main()
