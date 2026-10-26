"""Independent official F1 results lane: classifications as soon as they are
published, then the standings until they include the race."""
from __future__ import annotations

import os
import subprocess
import time
from datetime import datetime, timedelta, timezone
import json

from fetch_f1_official_results import DATA, ROOT, main as fetch_results
from seasons import results_season
from standings_progress import standings_behind
from watch_live_results import publish_changed_data

MAX_SECONDS = 19_800
POLL_SECONDS = 60
# Start looking this long before a session so the classification is fetched
# the moment formula1.com publishes it.
LEAD = timedelta(minutes=2)
FOLLOWUP_LOOKAHEAD = timedelta(hours=8)


def pending_starts(
    now: datetime, horizon: timedelta, lookback: timedelta = timedelta(days=3)
) -> list[datetime]:
    """Start times of unreceived, uncancelled sessions around ``now``."""
    starts: list[datetime] = []
    events = [
        (calendar.parent, event)
        for calendar in sorted((DATA / 'f1').glob('*/calendar.json'))
        for event in json.loads(calendar.read_text(encoding='utf-8'))['data']
    ]
    for root, event in events:
        if event.get('cancelled'):
            continue
        document = json.loads((root / event['resultsPath']).read_text(encoding='utf-8'))
        received = {
            session['type'] for session in document['data'].get('sessions', [])
            if session.get('results') and session.get('source', {}).get('name') == 'formula1-official'
        }
        for session in event.get('sessions', []):
            start = datetime.fromisoformat(session['startTimeUtc'].replace('Z', '+00:00'))
            if session.get('timeTbc'):
                continue
            if not session.get('cancelled') and session['type'] not in received and now - lookback <= start <= now + horizon:
                starts.append(start)
    return sorted(starts)


def needs_watch(now: datetime) -> bool:
    return any(start <= now + LEAD for start in pending_starts(now, LEAD))


def dispatch_followup() -> None:
    """Hand over to a fresh job: GitHub's cron fires only every few hours."""
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        return
    if pending_starts(datetime.now(timezone.utc), FOLLOWUP_LOOKAHEAD, timedelta(hours=6)):
        subprocess.run(['gh', 'workflow', 'run', 'f1-live-results.yml', '--ref', 'main'], cwd=ROOT, check=False)


def standings_pending(now: datetime) -> bool:
    """A race classified in the last day is not in the standings yet."""
    root = DATA / 'f1' / str(results_season(DATA / 'f1', now.year))
    return standings_behind(root, now)


def main() -> None:
    deadline = time.monotonic() + MAX_SECONDS
    while True:
        now = datetime.now(timezone.utc)
        starts = pending_starts(now, timedelta(seconds=MAX_SECONDS))
        if not starts and standings_pending(now):
            # formula1.com can publish the standings a few minutes after the
            # race classification: keep polling them, never wait for the
            # regular refresh.
            starts = [now]
        if not starts:
            upcoming = pending_starts(now, FOLLOWUP_LOOKAHEAD, timedelta(0))
            if upcoming:
                # Let the next job start just early enough to cover the session.
                wake = upcoming[0] - timedelta(seconds=MAX_SECONDS)
                time.sleep(max(0.0, (wake - now).total_seconds()))
            return
        wait = (starts[0] - LEAD - now).total_seconds()
        remaining = deadline - time.monotonic()
        if wait > 0:
            if wait >= remaining:
                return
            print(f'Waiting {int(wait)}s for the next F1 session', flush=True)
            time.sleep(wait)
            continue
        try:
            fetch_results(live=True)
            publish_changed_data()
        except Exception as error:
            # A temporary upstream failure must not kill automatic retries.
            print(f'Official F1 retry: {error}', flush=True)
        if time.monotonic() >= deadline:
            return
        time.sleep(POLL_SECONDS)


if __name__ == '__main__':
    main()
    dispatch_followup()
