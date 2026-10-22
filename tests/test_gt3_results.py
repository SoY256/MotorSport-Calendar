import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import fetch_gt3_results as gt3  # noqa: E402
import refresh_decision  # noqa: E402
import validate_data  # noqa: E402

TIMETABLE = """
<div class="timetable">
<table><caption class="timetable__caption"> <span>Saturday, 10 October</span> </caption>
<thead><tr><th>Session</th><th>Local</th><th>GMT</th></tr></thead>
<tbody class="timetable__table-body">
<tr><td>Free Practice</td><td>09:00 pm</td><td>01:00 am</td></tr>
<tr><td>Qualifying 1 - Group A</td><td>10:00</td><td>14:00</td></tr>
<tr><td>Qualifying 1 - Group B</td><td>10:15</td><td>14:15</td></tr>
<tr><td>Driver Autograph Session</td><td>11:00</td><td>15:00</td></tr>
<tr><td>Main Race after 1h 30</td><td>13:30</td><td>17:30</td></tr>
<tr><td>Race</td><td>12:00</td><td>16:00</td></tr>
</tbody></table></div>
"""

NATSOFT_RACE = """2026 GT Festival
PHILLIP ISLAND GRAND PRIX CIRCUIT
2026 GT World Challenge Australia - Race 1
CLASSIFICATION
Pos Car Competitor/Team Driver Vehicle Cap CL Laps Race.Time Fastest...Lap
1 1 Kelso Electrical MPC B.Feeney/B.Schumacher Audi R8 LMS EVO ll PA 31 01:00:01.3101 15 1:26.9973
2 56 Kollosche AMG by Tigani O.Targett/S.Smollen Mercedes-AMG GT3 EVO PA 31 01:00:02.0752 16 1:27.1274
3 888 Mercedes-AMG Team GMR M.Engel/M.Grenier/
M.Martin Mercedes-AMG GT3 EVO PRO 30 01:00:40.5850 17 1:27.5683
"""

NATSOFT_QUALIFYING = """2026 GT Festival
PHILLIP ISLAND GRAND PRIX CIRCUIT
2026 GT World Challenge Australia - Qualifying 1
CLASSIFICATION
Pos Car Competitor/Team Driver Vehicle Cap CL Laps Fastest...Lap Gap
1 66 Move My Wheels by Tigani Jayden Ojeda (AUS) Mercedes-AMG GT3 EVO PA 9 9 1:39.0076*
2 26 ARGT Jaxon Evans (AUS) Ferrari 296 GT3 PA 9 9 1:39.7667 0:00.7591
"""


class Gt3TimetableTests(unittest.TestCase):
    def test_twelve_hour_clock_and_gmt_across_midnight(self):
        rows = gt3.timetable_rows(TIMETABLE, date(2026, 10, 8), date(2026, 10, 11))
        first = rows[0]
        self.assertEqual(first["utc"], datetime(2026, 10, 11, 1, 0, tzinfo=timezone.utc))
        self.assertEqual(first["offset"], -240)

    def test_only_track_sessions_with_unique_types(self):
        rows = gt3.timetable_rows(TIMETABLE, date(2026, 10, 8), date(2026, 10, 11))
        sessions = gt3.build_sessions("gtwc-america", "Indianapolis 8 Hour", rows)
        self.assertEqual(
            [session["type"] for session in sessions],
            ["QUALIFYING_1_GROUP_A", "QUALIFYING_1_GROUP_B", "R", "FP"],
        )
        by_type = {session["type"]: session for session in sessions}
        self.assertEqual(by_type["QUALIFYING_1_GROUP_A"]["durationMinutes"], 15)
        self.assertEqual(by_type["R"]["durationMinutes"], 480)
        self.assertEqual(by_type["R"]["startTimeTrack"], "2026-10-10 12:00:00-04:00")

    def test_results_and_timetable_names_match(self):
        self.assertEqual(gt3.session_key("Free Practice 1"), gt3.session_key("Practice 1"))
        self.assertEqual(gt3.session_key("Main Race"), gt3.session_key("Race"))
        self.assertEqual(gt3.session_type("Race 2"), "R2")
        self.assertEqual(gt3.session_type("Free Practice 1"), "FP1")

    def test_date_ranges(self):
        self.assertEqual(gt3.parse_date_range("10 - 12 April 2026"), (date(2026, 4, 10), date(2026, 4, 12)))
        self.assertEqual(
            gt3.parse_date_range("30 July 2026 - 2 August 2026"), (date(2026, 7, 30), date(2026, 8, 2))
        )


class Gt3ResultTests(unittest.TestCase):
    def test_sprint_rounds_are_identified_by_their_two_races(self):
        self.assertEqual(gt3.event_cup("<td>Race 1</td><td>Race 2</td>Endurance Cup"), "Sprint Cup")
        self.assertEqual(gt3.event_cup("x", "Barcelona", {"barcelona": "Sprint Cup"}), "Sprint Cup")

    def test_session_selector_is_preferred_over_broken_links(self):
        page = (
            '<select name="filter_season_id"><option value="11" selected>2026</option></select>'
            '<select name="filter_meeting_id"><option value="0">x</option>'
            '<option value="111" selected>Sonoma</option></select>'
            '<select id="filter_race_id" name="filter_race_id"><option value="">Session</option>'
            '<option value="542">Race</option></select>'
            '<a href="/results/2026/sonoma-raceway/">Race</a>'
        )
        self.assertEqual(
            gt3.result_links(page),
            [("Race", "/results?filter_season_id=11&filter_meeting_id=111&filter_race_id=542")],
        )

    def test_gt4_cars_are_removed_from_mixed_grids(self):
        rows = [
            {"pos": "1", "car #": "1", "class": "GT3 Pro-Am", "drivers": "A B, C D", "team": "T",
             "car": "Ferrari 296 GT3", "time": "1:30.0", "laps": "20", "gap": ""},
            {"pos": "2", "car #": "40", "class": "GT4 Silver", "drivers": "E F", "team": "U",
             "car": "BMW M4 GT4", "time": "1:40.0", "laps": "18", "gap": "2 Laps"},
            {"pos": "3", "car #": "7", "class": "GT3 Silver-Am", "drivers": "G H", "team": "V",
             "car": "Porsche 911 GT3 R", "time": "1:31.0", "laps": "20", "gap": "5.123"},
        ]
        result = gt3.result_rows(rows, True, {})
        self.assertEqual([(row["position"], row["carNumber"]) for row in result], [(1, "1"), (2, "7")])
        self.assertEqual(result[0]["driver"]["givenName"], "A B / C D")
        self.assertEqual(result[0]["team"]["color"], "#DC0000")
        self.assertEqual(result[1]["time"], "+5.123")

    def test_natsoft_race_classification(self):
        known = {"broc-feeney": "Broc Feeney", "maro-engel": "Maro Engel"}
        title, rows = gt3.natsoft_classification(NATSOFT_RACE, known)
        self.assertEqual(title, "Race 1")
        self.assertEqual(rows[0]["drivers"], "Broc Feeney, B. Schumacher")
        self.assertEqual(rows[0]["team"], "Kelso Electrical MPC")
        self.assertEqual(rows[0]["car"], "Audi R8 LMS EVO ll")
        self.assertEqual(rows[1]["gap"], "+0.765")
        self.assertEqual(rows[2]["drivers"], "Maro Engel, M. Grenier, M. Martin")
        self.assertEqual(rows[2]["gap"], "1 lap")

    def test_natsoft_qualifying_lists_the_driver_with_nationality(self):
        title, rows = gt3.natsoft_classification(NATSOFT_QUALIFYING, {})
        self.assertEqual(title, "Qualifying 1")
        self.assertEqual(
            (rows[0]["drivers"], rows[0]["team"], rows[0]["best lap"]),
            ("Jayden Ojeda", "Move My Wheels by Tigani", "1:39.0076"),
        )
        self.assertEqual(rows[1]["best lap"], "1:39.7667")


class Gt3LapRecordTests(unittest.TestCase):
    def test_best_lap_column_but_not_total_race_time(self):
        self.assertEqual(gt3.race_best_lap({"time": "1:33.413", "laps": "35"}), "1:33.413")
        self.assertEqual(gt3.race_best_lap({"best lap": "1:34.966", "time": ""}), "1:34.966")
        # GT Asia / British GT: "time" is the race time next to an average speed.
        self.assertIsNone(gt3.race_best_lap({"time": "18:40.266", "av mph": "103.000"}))
        self.assertIsNone(gt3.race_best_lap({"time": "1:00:28.625"}))
        self.assertIsNone(gt3.race_best_lap({"time": "0.000"}))

    def test_tsl_rows_give_the_lap_after_the_average_speed(self):
        lines = [
            "1 16 SILVER 1 C F o A n W gfu Audi R8 LMS GT3 EVO II 33 1:01:24.358 119.40 1:29.569 24 2 1",
            "2 500*SILVER 2 T T a E k Nissan GT-R NISMO GT3 33 1:01:26.341 1.983 1.983 119.33 1:29.654 23 5 3",
            "9 15 PRO-AM 5 A A n Audi R8 LMS GT3 EVO II 32 1:01:44.152 1 Lap 1:05.123 118.76 1:30.377 24 13 4",
        ]
        parsed = [gt3.TSL_ROW.match(line).groups() for line in lines]
        self.assertEqual(parsed, [("16", "1:29.569"), ("500", "1:29.654"), ("15", "1:30.377")])

    def test_event_record_is_the_fastest_race_lap_with_its_crew(self):
        def row(car, crew, lap):
            return {"carNumber": car, "driver": {"givenName": crew}, "components": {"bestLap": lap}}

        sessions = [
            {"type": "Q1", "results": [row("1", "Fast QUALIFIER", "1:20.000")]},
            {"type": "R1", "results": [row("2", "Wei LU / Ben MCDONALD", "1:28.486"), row("3", "B / C", "1:29.000")]},
            {"type": "R2", "results": [row("4", "D / E", "1:28.900"), row("5", "F", "1:00:00.000")]},
        ]
        self.assertEqual(gt3.event_lap_record(sessions, 2026), "1:28.486 • Wei Lu / Ben McDonald (2026)")
        self.assertIsNone(gt3.event_lap_record([{"type": "R", "results": []}], 2026))

    def test_24h_nurburgring_runs_on_the_nordschleife(self):
        self.assertEqual(gt3.circuit_for("ADAC Ravenol 24h Nürburgring", "Germany", "DE")["name"], "Nürburgring Nordschleife")
        self.assertEqual(gt3.circuit_for("Nürburgring", "Germany", "DE")["name"], "Nürburgring")

class Gt3PipelineTests(unittest.TestCase):
    def test_series_lists_stay_in_sync(self):
        self.assertEqual(refresh_decision.GT3_SERIES, frozenset(gt3.SERIES))
        self.assertEqual(validate_data.LENIENT_SERIES, frozenset(gt3.SERIES))
        dart = (Path(__file__).resolve().parents[1] / "lib" / "core" / "series_catalog.dart").read_text(
            encoding="utf-8"
        )
        for series in gt3.SERIES:
            self.assertIn(f"id: '{series}'", dart)

    def test_every_gt3_session_is_polled_but_not_forever(self):
        self.assertTrue(refresh_decision.expects_results("gtwc-europe", "QUALIFYING_1_GROUP_A"))
        self.assertEqual(refresh_decision.POLL_WINDOW, timedelta(hours=6))


if __name__ == "__main__":
    unittest.main()
