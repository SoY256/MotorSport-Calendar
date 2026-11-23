import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import watch_live_results
import watch_f1_results


def write_series(root: Path, series: str, start: datetime, results: bool = False) -> None:
    season = root / series / "2026"
    (season / "events").mkdir(parents=True)
    (season / "calendar.json").write_text(json.dumps({"data": [{
        "id": f"{series}-1", "resultsPath": "events/1.json",
        "sessions": [{"type": "R", "startTimeUtc": start.isoformat(), "durationMinutes": 360}],
    }]}))
    sessions = [{"type": "R", "results": [{}]}] if results else []
    (season / "events" / "1.json").write_text(json.dumps({"data": {"eventId": f"{series}-1", "sessions": sessions}}))


class LiveWatcherTests(unittest.TestCase):
    def test_classification_is_polled_two_minutes_after_scheduled_end(self):
        now = datetime(2026, 10, 18, 16, 2, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            write_series(root, "wec", datetime(2026, 10, 18, 10, 0, tzinfo=timezone.utc))
            with patch.object(watch_live_results, "DATA", root):
                due, label = watch_live_results.missing_sessions(now)[0]
        self.assertEqual(label, "wec/wec-1/R")
        self.assertEqual(due, now)

    def test_followup_is_requested_for_a_session_due_soon_but_not_for_a_distant_one(self):
        now = datetime(2026, 10, 18, 6, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            write_series(root, "wec", now + timedelta(hours=1))
            with patch.object(watch_live_results, "DATA", root):
                self.assertTrue(watch_live_results.needs_followup(now))
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            write_series(root, "wec", now + timedelta(days=3))
            with patch.object(watch_live_results, "DATA", root):
                self.assertFalse(watch_live_results.needs_followup(now))

    def test_targeted_refresh_only_runs_requested_series(self):
        with patch.object(watch_live_results.subprocess, "run") as run, \
                patch.object(watch_live_results, "publish_changed_data"):
            run.return_value.returncode = 0
            watch_live_results.refresh({"wec", "f2"})
        self.assertEqual(run.call_args.args[0][-2:], ["--series", "f2,wec"])


class F1WatcherTests(unittest.TestCase):
    def test_upcoming_session_is_watched_before_it_starts(self):
        now = datetime(2026, 10, 25, 6, 0, tzinfo=timezone.utc)
        start = now + timedelta(hours=4)
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            write_series(root, "f1", start)
            with patch.object(watch_f1_results, "DATA", root):
                self.assertEqual(watch_f1_results.pending_starts(now, timedelta(hours=5)), [start])
                self.assertEqual(watch_f1_results.pending_starts(now, timedelta(hours=1)), [])

    def test_verified_non_classification_stops_both_watchers(self):
        now = datetime(2026, 11, 22, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            write_series(root, "f1", now - timedelta(hours=4))
            calendar_path = root / "f1" / "2026" / "calendar.json"
            calendar = json.loads(calendar_path.read_text())
            calendar["data"][0]["sessions"][0]["type"] = "FP1"
            calendar_path.write_text(json.dumps(calendar))
            result = root / "f1" / "2026" / "events" / "1.json"
            document = {"data": {"eventId": "f1-1", "sessions": [{
                "type": "FP1", "results": [], "classificationStatus": "not-issued",
                "classificationReason": "no-timed-laps",
                "source": {"name": "fia-official-timing", "url": "https://www.fia.com/sites/default/files/laps.pdf"},
            }]}}
            result.write_text(json.dumps(document))
            with patch.object(watch_f1_results, "DATA", root), patch.object(watch_live_results, "DATA", root):
                self.assertEqual(watch_f1_results.pending_starts(now, timedelta(hours=1)), [])
                self.assertEqual(watch_live_results.missing_sessions(now), [])
                # A bare empty response is not proof that no classification exists.
                document["data"]["sessions"][0].pop("source")
                result.write_text(json.dumps(document))
                self.assertEqual(len(watch_f1_results.pending_starts(now, timedelta(hours=1))), 1)
                self.assertEqual(len(watch_live_results.missing_sessions(now)), 1)


if __name__ == "__main__":
    unittest.main()
