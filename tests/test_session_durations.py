import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import add_session_durations as durations


class SessionDurationTests(unittest.TestCase):
    def test_existing_official_durations_survive_enrichment(self):
        events = [
            {"name": "Motul SportsCar Endurance Grand Prix", "sessions": [
                {"type": "R", "name": "Race", "durationMinutes": 360},
            ]},
            {"name": "Battle on the Bricks", "sessions": [
                {"type": "R", "name": "Race", "durationMinutes": 160},
            ]},
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "imsa" / "2027" / "calendar.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"data": events}), encoding="utf-8")
            durations.main(root)
            actual = json.loads(path.read_text(encoding="utf-8"))["data"]
        self.assertEqual([event["sessions"][0]["durationMinutes"] for event in actual], [360, 160])

    def test_missing_or_invalid_durations_are_still_filled(self):
        sessions = [
            {"type": "FP1", "name": "Practice 1"},
            {"type": "Q", "name": "Qualifying", "durationMinutes": 0},
            {"type": "R", "name": "Race", "durationMinutes": -1},
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "f1" / "2026" / "calendar.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"data": [{"name": "Grand Prix", "sessions": sessions}]}), encoding="utf-8")
            durations.main(root)
            actual = json.loads(path.read_text(encoding="utf-8"))["data"][0]["sessions"]
        self.assertEqual([session["durationMinutes"] for session in actual], [60, 60, 120])


if __name__ == "__main__":
    unittest.main()
