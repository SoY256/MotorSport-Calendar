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
