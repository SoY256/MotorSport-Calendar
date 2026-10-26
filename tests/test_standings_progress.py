import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import fetch_f1_official_results  # noqa: E402
import update_all_data  # noqa: E402
from standings_progress import progress, standings_behind  # noqa: E402

NOW = datetime(2026, 10, 25, 22, 10, tzinfo=timezone.utc)


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def season(root: Path, standings_points: float, race_start: datetime) -> Path:
    folder = root / "f1" / "2026"
    write(folder / "calendar.json", {"data": [{
        "resultsPath": "events/18.json",
        "sessions": [{"type": "R", "startTimeUtc": race_start.isoformat(), "durationMinutes": 120}],
    }]})
    write(folder / "events" / "18.json", {"data": {"sessions": [{
        "type": "R", "source": {"name": "formula1-official"},
        "results": [
            {"position": 1, "points": 25, "driver": {"code": "ANT"}, "team": {"name": "Mercedes"}},
            {"position": 2, "points": 18, "driver": {"code": "RUS"}, "team": {"name": "Mercedes"}},
        ],
    }]}})
    write(folder / "standings_drivers.json", {"data": [{"code": "ANT", "points": standings_points, "wins": 0}]})
    return folder


class StandingsProgressTests(unittest.TestCase):
    def test_progress_is_points_then_wins(self):
        self.assertGreater(progress({"data": [{"points": 365, "wins": 8}]}), progress({"data": [{"points": 340, "wins": 9}]}))
        self.assertGreater(progress({"data": [{"points": 365, "wins": 9}]}), progress({"data": [{"points": 365, "wins": 8}]}))

    def test_standings_behind_a_race_classified_today(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = season(Path(directory), 0, NOW - timedelta(hours=2))
            self.assertTrue(standings_behind(folder, NOW))
            write(folder / "standings_drivers.json", {"data": [{"points": 25}, {"points": 18}]})
            self.assertFalse(standings_behind(folder, NOW))

    def test_an_old_mismatch_does_not_keep_watchers_alive(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = season(Path(directory), 0, NOW - timedelta(days=3))
            self.assertFalse(standings_behind(folder, NOW))

    def test_wins_are_counted_from_official_race_results(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = season(Path(directory), 0, NOW)
            drivers, teams = fetch_f1_official_results.race_wins(folder)
            self.assertEqual((drivers["ANT"], drivers["RUS"], teams["mercedes"]), (1, 0, 1))


class KeepPublishedStandingsTests(unittest.TestCase):
    def run_guard(self, published_points, staged_points, written):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target, staged = root / "data", root / "staged"
            write(target / "f1" / "2026" / "standings_drivers.json",
                  {"lastSuccessfulUpdate": written.isoformat(), "data": [{"points": published_points}]})
            write(staged / "f1" / "2026" / "standings_drivers.json",
                  {"lastSuccessfulUpdate": NOW.isoformat(), "data": [{"points": staged_points}]})
            update_all_data.keep_published_standings(staged, target, NOW)
            return json.loads((staged / "f1" / "2026" / "standings_drivers.json").read_text())["data"][0]["points"]

    def test_lagging_source_does_not_undo_fresh_standings(self):
        self.assertEqual(self.run_guard(365, 340, NOW - timedelta(minutes=3)), 365)

    def test_progress_is_published(self):
        self.assertEqual(self.run_guard(340, 365, NOW - timedelta(minutes=3)), 365)

    def test_a_later_correction_is_published(self):
        self.assertEqual(self.run_guard(365, 340, NOW - timedelta(hours=13)), 340)


if __name__ == "__main__":
    unittest.main()
