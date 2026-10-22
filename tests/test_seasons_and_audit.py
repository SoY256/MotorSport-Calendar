import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import audit_results  # noqa: E402
import fetch_gt3_results as gt3  # noqa: E402
import seasons  # noqa: E402


def calendar(season: int, starts: list[str]) -> dict:
    return {
        "data": [
            {"id": f"x-{season}-{index}", "round": index, "name": f"Round {index}", "resultsPath": f"events/{index}.json",
             "sessions": [{"type": "R", "name": "Race", "startTimeUtc": start, "durationMinutes": 60}]}
            for index, start in enumerate(starts, start=1)
        ]
    }


class SeasonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "f1"
        for season, starts in ((2026, ["2026-03-01T12:00:00Z", "2026-12-06T12:00:00Z"]),
                               (2027, ["2027-03-14T12:00:00Z"])):
            folder = self.root / str(season)
            folder.mkdir(parents=True)
            (folder / "calendar.json").write_text(json.dumps(calendar(season, starts)), encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_running_season_keeps_results_until_the_next_one_starts(self):
        october = datetime(2026, 10, 22, tzinfo=timezone.utc)
        december = datetime(2026, 12, 20, tzinfo=timezone.utc)
        march = datetime(2027, 3, 15, tzinfo=timezone.utc)
        self.assertEqual(seasons.season_dirs(self.root), [2026, 2027])
        self.assertEqual(seasons.results_season(self.root, 2026, october), 2026)
        self.assertEqual(seasons.results_season(self.root, 2026, december), 2026)
        self.assertEqual(seasons.results_season(self.root, 2026, march), 2027)
        self.assertEqual(seasons.current_season(self.root, 2026, october), 2026)
        self.assertEqual(seasons.current_season(self.root, 2026, december), 2027)


class Gt3FixTests(unittest.TestCase):
    def test_standings_out_of_points_order_are_re_ranked(self):
        rows = [
            {"position": 4, "points": 66.0, "category": "AM", "id": "a"},
            {"position": 6, "points": 42.0, "category": "AM", "id": "b"},
            {"position": 5, "points": 33.0, "category": "AM", "id": "c"},
            {"position": 5, "points": 33.0, "category": "AM", "id": "d"},
        ]
        ranked = gt3.consistent_order(rows)
        self.assertEqual([(row["id"], row["position"]) for row in ranked],
                         [("a", 1), ("b", 2), ("c", 3), ("d", 3)])

    def test_result_only_sessions_fill_the_timetable(self):
        sessions = [
            {"type": "R1", "name": "Race 1", "startTimeUtc": "2026-10-03T12:00:00Z", "durationMinutes": 60},
            {"type": "R2", "name": "Race 2", "startTimeUtc": "2026-10-04T12:00:00Z", "durationMinutes": 60},
        ]
        links = [("Race 2", "/b"), ("Qualifying 2", "/q"), ("Race 1", "/a")]  # newest first
        merged = gt3.add_result_only_sessions("gtwc-europe", "Barcelona", sessions, links)
        added = next(item for item in merged if item["name"] == "Qualifying 2")
        self.assertTrue(added["timeTbc"])
        self.assertTrue("2026-10-03T13:00" <= added["startTimeUtc"] < "2026-10-04T12:00")

    def test_foreign_entry_lists_are_rejected(self):
        race = {"results": [{"carNumber": str(number)} for number in range(1, 30)]}
        foreign = {"results": [{"carNumber": str(number)} for number in range(100, 120)]}
        kept = gt3.without_foreign_sessions("gtwc-europe", "Paul Ricard", {"R": race, "FP1": foreign}, {})
        self.assertEqual(set(kept), {"R"})

    def test_suzuka_pro_am_rows_are_kept(self):
        text = (
            "2026 Intercontinental GT Challenge - 50th Suzuka 1000KM\n"
            "NIGHT PRACTICE - CLASSIFICATION - FINAL\n"
            "PONOS RACING (JPN) Ferrari 296 GT3 EVO\n"
            "1 45 PRO 1 SeitaNONAKA(JPN)/TakuroSHINOHARA(JPN) 1:58.523 4 5 176.38\n"
            "Team (JPN) Ferrari 296 GT3 EVO\n"
            "2 60 PROAM 1 KeiNAKANISHI(JPN)/GiancarloFISICHELLA(ITA) 2:00.698 6 25 0.303 0.010 173.20\n"
        )
        _title, rows = gt3.asian_classification(text)
        self.assertEqual([(row["pos"], row["class"]) for row in rows], [("1", "Pro"), ("2", "Pro-Am")])


class AuditTests(unittest.TestCase):
    def test_gaps_duplicates_and_missing_names_are_errors(self):
        errors, warnings = [], []
        session = {"type": "R", "results": [
            {"position": 1, "carNumber": "1", "driver": {"givenName": "A"}, "time": "1:00:00"},
            {"position": 3, "carNumber": "1", "driver": {"givenName": ""}},
        ]}
        audit_results.session_checks("x", session, errors, warnings)
        self.assertEqual(len(errors), 3)


if __name__ == "__main__":
    unittest.main()
