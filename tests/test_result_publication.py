import sys
import unittest
import tempfile
import subprocess
import json
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from watch_live_results import merge_event_results
import watch_live_results


class PublicationTests(unittest.TestCase):
    def test_real_git_rebase_merges_simultaneous_session_updates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'data/f1/2026/events/race.json'
            path.parent.mkdir(parents=True)
            def git(*args):
                return subprocess.run(['git', *args], cwd=root, check=True, capture_output=True, text=True).stdout.strip()
            def save(sessions):
                path.write_text(json.dumps({'data': {'eventId': 'same', 'sessions': sessions}}), encoding='utf-8')
                git('add', 'data')
                git('commit', '-m', 'Test data')
            git('init', '-b', 'main')
            git('config', 'user.name', 'Test')
            git('config', 'user.email', 'test@example.invalid')
            save([{'type': 'Q', 'results': [1]}])
            git('branch', 'upstream')
            save([{'type': 'Q', 'results': [1, 2]}])
            git('checkout', 'upstream')
            save([{'type': 'Q', 'results': [1]}, {'type': 'R', 'results': [1], 'source': {'name': 'formula1-official'}}])
            git('update-ref', 'refs/remotes/origin/main', git('rev-parse', 'HEAD'))
            git('checkout', 'main')
            with patch.object(watch_live_results, 'ROOT', root), patch.object(watch_live_results, 'DATA', root / 'data'):
                watch_live_results.rebase_data()
            sessions = {s['type']: s['results'] for s in json.loads(path.read_text())['data']['sessions']}
            self.assertEqual(sessions, {'Q': [1, 2], 'R': [1]})

    def test_overlapping_full_refresh_keeps_newest_calendar_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            calendar = root / 'data/wec/2026/calendar.json'
            calendar.parent.mkdir(parents=True)
            def git(*args):
                return subprocess.run(['git', *args], cwd=root, check=True, capture_output=True, text=True).stdout.strip()
            def save(value):
                calendar.write_text(json.dumps({'lastSuccessfulUpdate': value}), encoding='utf-8')
                git('add', 'data')
                git('commit', '-m', 'Update motorsport data')
            git('init', '-b', 'main')
            git('config', 'user.name', 'Test')
            git('config', 'user.email', 'test@example.invalid')
            save('t0')
            git('branch', 'upstream')
            save('t2-newest')
            git('checkout', 'upstream')
            save('t1')
            git('update-ref', 'refs/remotes/origin/main', git('rev-parse', 'HEAD'))
            git('checkout', 'main')
            with patch.object(watch_live_results, 'ROOT', root), patch.object(watch_live_results, 'DATA', root / 'data'):
                watch_live_results.rebase_data()
            self.assertEqual(json.loads(calendar.read_text())['lastSuccessfulUpdate'], 't2-newest')
            self.assertIn(git('rev-parse', 'origin/main'), git('rev-list', 'HEAD'))

    def test_concurrent_race_result_survives_older_full_refresh(self):
        race = {'type': 'R', 'results': [{'position': 1}], 'source': {'name': 'formula1-official'}}
        upstream = {'data': {'eventId': 'same', 'sessions': [race]}}
        local = {'data': {'eventId': 'same', 'sessions': [{'type': 'R', 'results': []}, {'type': 'Q', 'results': [1]}]}}
        merged = merge_event_results(upstream, local)
        self.assertEqual({s['type'] for s in merged['data']['sessions']}, {'Q', 'R'})
        self.assertEqual(merged['data']['sessions'][0], race)

    def test_official_classification_wins_over_secondary_source(self):
        official = {'type': 'R', 'results': [1, 2], 'source': {'name': 'formula1-official'}}
        merged = merge_event_results({'data': {'eventId': 'same', 'sessions': [official]}}, {'data': {'eventId': 'same', 'sessions': [{'type': 'R', 'results': [1]}]}})
        self.assertEqual(merged['data']['sessions'], [official])

    def test_wrong_event_is_rejected(self):
        with self.assertRaises(ValueError):
            merge_event_results({'data': {'eventId': 'a'}}, {'data': {'eventId': 'b'}})

class StandingsPublicationTests(unittest.TestCase):
    """A job that started before the race must not overwrite the standings a
    faster job published after it (US GP 2026: 365 points replaced by 340)."""

    def repository(self, directory):
        root = Path(directory)
        def git(*args):
            return subprocess.run(['git', *args], cwd=root, check=True, capture_output=True, text=True).stdout.strip()
        git('init', '-b', 'main')
        git('config', 'user.name', 'Test')
        git('config', 'user.email', 'test@example.invalid')
        return root, git

    def standings(self, root, points, stamp, wins=8):
        path = root / 'data/f1/2026/standings_drivers.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = [{'code': 'ANT', 'points': points, 'wins': wins}, {'code': 'RUS', 'points': 238}]
        path.write_text(json.dumps({'lastSuccessfulUpdate': stamp, 'data': rows}, indent=2), encoding='utf-8')
        return path

    def publish(self, root, git):
        base = git('merge-base', 'HEAD', 'origin/main')
        with patch.object(watch_live_results, 'ROOT', root), patch.object(watch_live_results, 'DATA', root / 'data'):
            watch_live_results.rebase_data()
            return watch_live_results.keep_newest_standings(base)

    def test_stale_job_keeps_the_newer_published_standings(self):
        with tempfile.TemporaryDirectory() as directory:
            root, git = self.repository(directory)
            path = self.standings(root, 340, 't0')
            git('add', 'data'); git('commit', '-m', 'before the race')
            git('branch', 'stale-job')
            self.standings(root, 365, 't1', wins=9)
            git('add', 'data'); git('commit', '-m', 'fast job after the race')
            git('update-ref', 'refs/remotes/origin/main', git('rev-parse', 'HEAD'))
            git('checkout', 'stale-job')
            self.standings(root, 340, 't2-later-but-stale')
            calendar = root / 'data/f1/2026/calendar.json'
            calendar.write_text('{"data": []}', encoding='utf-8')
            git('add', 'data'); git('commit', '-m', 'slow job')
            self.assertTrue(self.publish(root, git))
            self.assertEqual(json.loads(path.read_text())['data'][0]['points'], 365)
            self.assertTrue(calendar.is_file())

    def test_only_stale_standings_leave_nothing_to_publish(self):
        with tempfile.TemporaryDirectory() as directory:
            root, git = self.repository(directory)
            path = self.standings(root, 340, 't0')
            git('add', 'data'); git('commit', '-m', 'before the race')
            git('branch', 'stale-job')
            self.standings(root, 365, 't1', wins=9)
            git('add', 'data'); git('commit', '-m', 'fast job after the race')
            git('update-ref', 'refs/remotes/origin/main', git('rev-parse', 'HEAD'))
            git('checkout', 'stale-job')
            self.standings(root, 340, 't2', wins=8)
            path.write_text(path.read_text().replace('"RUS"', '"RUS", "x": 1'), encoding='utf-8')
            git('add', 'data'); git('commit', '-m', 'slow job')
            self.assertFalse(self.publish(root, git))
            self.assertEqual(json.loads(path.read_text())['data'][0]['points'], 365)

    def test_a_correction_that_lowers_points_is_published(self):
        with tempfile.TemporaryDirectory() as directory:
            root, git = self.repository(directory)
            path = self.standings(root, 365, 't0', wins=9)
            git('add', 'data'); git('commit', '-m', 'race')
            git('update-ref', 'refs/remotes/origin/main', git('rev-parse', 'HEAD'))
            self.standings(root, 340, 't1', wins=8)
            git('add', 'data'); git('commit', '-m', 'winner disqualified')
            self.assertTrue(self.publish(root, git))
            self.assertEqual(json.loads(path.read_text())['data'][0]['points'], 340)
