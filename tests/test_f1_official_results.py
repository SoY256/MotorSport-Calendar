import sys
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from fetch_f1_official_results import official_rows, ROUTES, page_for_event
import fetch_f1_official_results as official


class OfficialF1ResultsTests(unittest.TestCase):
    def test_race_identity_not_round_order_selects_official_page(self):
        pages = {1: ('1', 'australia'), 2: ('2', 'singapore')}
        self.assertEqual(page_for_event({'round': 1, 'name': 'Singapore Grand Prix'}, pages), ('2', 'singapore'))
        self.assertIsNone(page_for_event({'round': 2, 'name': 'Unknown Grand Prix'}, pages))
    def test_current_official_sprint_qualifying_route(self):
        self.assertEqual(ROUTES['SQ'], 'sprint-qualifying')

    def test_non_classified_drivers_are_not_dropped(self):
        page = '<table><tr><th>Pos</th></tr><tr><td>NC</td><td>3</td><td>Max Verstappen VER</td><td>Red Bull Racing</td><td>0</td><td>DNF</td><td>0</td></tr></table>'
        rows = official_rows(page, 'SPRINT', {}, {})
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]['position'])
        self.assertEqual(rows[0]['positionText'], 'NC')
        self.assertFalse(rows[0]['classified'])

    def test_practice_table_preserves_verified_driver_and_team_metadata(self):
        page = """
        <table><thead><tr><th>Pos.</th><th>No.</th><th>Driver</th><th>Team</th><th>Time</th><th>Laps</th></tr></thead>
        <tbody><tr><td>1</td><td>3</td><td><span>Max</span> <span>Verstappen</span><span>VER</span></td>
        <td>Red Bull Racing</td><td>1:43.922</td><td>21</td></tr></tbody></table>
        """
        drivers = {"VER": {"id": "max_verstappen", "givenName": "Max", "familyName": "Verstappen", "nationality": "Dutch"}}
        teams = {"red bull": {"id": "red-bull", "name": "Red Bull", "color": "#4781D7"}}

        rows = official_rows(page, "FP3", drivers, teams)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["driver"]["id"], "max_verstappen")
        self.assertEqual(rows[0]["driver"]["nationality"], "Dutch")
        self.assertEqual(rows[0]["team"]["color"], "#4781D7")
        self.assertEqual(rows[0]["time"], "1:43.922")
        self.assertEqual(rows[0]["laps"], 21)

    def test_no_classification_requires_finished_timing_not_an_empty_page(self):
        laps = (
            "FORMULA 1 TEST GRAND PRIX 2026\nFirst Practice Session Lap Times\n"
            "1 Example DRIVER\nNO TIME NO TIME\n1 P 17:11:32\n2 P 31:07.424\n"
        )
        control = "FORMULA 1 TEST GRAND PRIX 2026\nRace Control Messages\n17:30 CHEQUERED FLAG"
        self.assertTrue(official.untimed_practice(laps, control, "FP1", 2026))
        self.assertFalse(official.untimed_practice(laps, control.replace("CHEQUERED FLAG", "GREEN LIGHT"), "FP1", 2026))
        self.assertFalse(official.untimed_practice(laps + "\n3 1:22.123", control, "FP1", 2026))
        self.assertFalse(official.untimed_practice(laps, control, "FP2", 2026))
        self.assertFalse(official.untimed_practice(laps, control, "FP1", 2027))
        self.assertFalse(official.untimed_practice("No results available", control, "FP1", 2026))

    def test_fia_classification_link_prevents_a_non_classification_notice(self):
        index = '<a href="https://www.fia.com/sites/default/files/2026_21_usa_f1_p1_timing_firstpracticesessionclassification_v01.pdf">Classification</a>'
        with patch.object(official, "fetch", return_value=index), \
                patch.object(official, "read") as read:
            notice = official.fia_practice_notice(
                {"name": "Las Vegas Grand Prix"}, {"type": "FP1"}, 2026, {},
            )
        self.assertIsNone(notice)
        read.assert_not_called()

    def test_import_stores_verified_notice_instead_of_waiting_forever(self):
        notice = {
            "type": "FP1", "name": "Practice 1", "startTimeUtc": "2026-11-20T00:30:00Z",
            "results": [], "classificationStatus": "not-issued", "classificationReason": "no-timed-laps",
            "source": {"name": "fia-official-timing", "url": "https://www.fia.com/sites/default/files/laps.pdf"},
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            season = root / "f1" / "2026"
            (season / "events").mkdir(parents=True)
            (season / "calendar.json").write_text(json.dumps({"data": [{
                "id": "vegas", "round": 21, "name": "Las Vegas Grand Prix", "resultsPath": "events/vegas.json",
                "sessions": [{"type": "FP1", "name": "Practice 1", "startTimeUtc": notice["startTimeUtc"],
                              "durationMinutes": 60}],
            }]}), encoding="utf-8")
            result = season / "events" / "vegas.json"
            result.write_text(json.dumps({"data": {"eventId": "vegas", "sessions": []}}), encoding="utf-8")
            with patch.object(official, "DATA", root), \
                    patch.object(official, "race_pages", return_value={21: ("1300", "las-vegas")}), \
                    patch.object(official, "metadata", return_value=({}, {})), \
                    patch.object(official, "fetch", return_value="No results available"), \
                    patch.object(official, "fia_practice_notice", return_value=notice), \
                    patch.object(official, "standings_behind", return_value=False), \
                    patch.object(official, "datetime", wraps=datetime) as clock:
                clock.now.return_value = datetime(2026, 11, 22, tzinfo=timezone.utc)
                official.main(live=True)
            document = json.loads(result.read_text(encoding="utf-8"))
            self.assertEqual(document["data"]["sessions"], [notice])
            self.assertIn("lastSuccessfulUpdate", document)


if __name__ == "__main__":
    unittest.main()
