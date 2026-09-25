import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from fetch_f1_official_results import official_rows


class OfficialF1ResultsTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
