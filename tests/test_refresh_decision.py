import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import refresh_decision


class RefreshDecisionTests(unittest.TestCase):
    def _data(self, updated, start, with_results=False):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        (root / "f1" / "2026" / "events").mkdir(parents=True)
        (root / "manifest.json").write_text(json.dumps({"lastSuccessfulUpdate": updated.isoformat()}))
        event_path = root / "f1" / "2026" / "events" / "event.json"
        event_path.write_text(json.dumps({"data": {"sessions": ([{"type": "R", "results": [{}]}] if with_results else [])}}))
        (root / "f1" / "2026" / "calendar.json").write_text(json.dumps({"data": [{
            "id": "race", "resultsPath": "events/event.json",
            "sessions": [{"type": "R", "startTimeUtc": start.isoformat(), "durationMinutes": 120}],
        }]}))
        return temp, root

    def test_live_session_is_due_five_minutes_after_expected_end(self):
        now = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
        temp, root = self._data(now - timedelta(hours=1), now - timedelta(hours=2, minutes=5))
        self.addCleanup(temp.cleanup)
        with patch.object(refresh_decision, "DATA", root):
            self.assertEqual(refresh_decision.decision(now)[1], "awaiting-f1-race-R")

    def test_new_result_stops_live_polling(self):
        now = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
        temp, root = self._data(now - timedelta(hours=1), now - timedelta(hours=3), True)
        self.addCleanup(temp.cleanup)
        with patch.object(refresh_decision, "DATA", root):
            self.assertEqual(refresh_decision.decision(now), (False, "not-due"))


if __name__ == "__main__":
    unittest.main()
