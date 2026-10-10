"""Independent official F1 results lane: no standings, portraits or other series."""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
import json

from fetch_f1_official_results import DATA, main as fetch_results
from watch_live_results import publish_changed_data


def needs_watch(now: datetime) -> bool:
    root = DATA / 'f1' / '2026'
    events = json.loads((root / 'calendar.json').read_text(encoding='utf-8'))['data']
    for event in events:
        if event.get('cancelled'):
            continue
        document = json.loads((root / event['resultsPath']).read_text(encoding='utf-8'))
        received = {
            session['type'] for session in document['data'].get('sessions', [])
            if session.get('results') and session.get('source', {}).get('name') == 'formula1-official'
        }
        for session in event.get('sessions', []):
            start = datetime.fromisoformat(session['startTimeUtc'].replace('Z', '+00:00'))
            if not session.get('cancelled') and session['type'] not in received and now - timedelta(days=3) <= start <= now + timedelta(minutes=15):
                return True
    return False


def main() -> None:
    deadline = time.monotonic() + 19_800
    while needs_watch(datetime.now(timezone.utc)):
        try:
            fetch_results(live=True)
            publish_changed_data()
        except Exception as error:
            # A temporary upstream failure must not kill automatic retries.
            print(f'Official F1 retry: {error}', flush=True)
        if time.monotonic() >= deadline:
            return
        if not needs_watch(datetime.now(timezone.utc)):
            return
        time.sleep(60)


if __name__ == '__main__':
    main()
