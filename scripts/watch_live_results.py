"""Keep a workflow alive around live sessions until results are published.

GitHub's cron service is best effort and can start scheduled workflows late.
This watcher therefore starts before an expected classification is due, waits
inside the already-running job, and retries the official importers every five
minutes until the classification appears.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from refresh_decision import expects_results, result_types, timestamp

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
# Official classifications appear within minutes of the flag; polling starts
# this long after the scheduled end and then repeats every interval.
LIVE_GRACE_MINUTES = 2
FOLLOWUP_LOOKAHEAD_HOURS = 8


def missing_sessions(now: datetime) -> list[tuple[datetime, str]]:
    missing: list[tuple[datetime, str]] = []
    for series_dir in DATA.iterdir():
        calendar_path = series_dir / "2026" / "calendar.json"
        if not calendar_path.is_file():
            continue
        events = json.loads(calendar_path.read_text(encoding="utf-8"))["data"]
        for event in events:
            available = result_types(calendar_path.parent / event["resultsPath"])
            for session in event.get("sessions", []):
                session_type = session.get("type")
                if (
                    session.get("cancelled")
                    or not expects_results(series_dir.name, session_type)
                    or session_type in available
                ):
                    continue
                due = timestamp(session["startTimeUtc"]) + timedelta(
                    minutes=int(session.get("durationMinutes", 120)) + LIVE_GRACE_MINUTES
                )
                missing.append(
                    (due, f"{series_dir.name}/{event['id']}/{session_type}")
                )
    return sorted(missing)


def manifest_is_stale(now: datetime) -> bool:
    try:
        manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
        return now - timestamp(manifest["lastSuccessfulUpdate"]) >= timedelta(hours=6)
    except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError):
        return True


def refresh(series: set[str] | None = None) -> bool:
    command = [sys.executable, str(ROOT / "scripts" / "update_all_data.py")]
    if series:
        command += ["--series", ",".join(sorted(series))]
    completed = subprocess.run(command, cwd=ROOT, check=False)
    if completed.returncode == 0:
        publish_changed_data()
        return True
    return False


def needs_followup(now: datetime) -> bool:
    """Whether a live session is overdue or due soon enough to keep chaining runs."""
    return any(
        now - timedelta(hours=6) <= due <= now + timedelta(hours=FOLLOWUP_LOOKAHEAD_HOURS)
        for due, _label in missing_sessions(now)
    )


def dispatch_followup() -> None:
    """Start the next watcher before this one ends.

    GitHub's cron is best effort and in practice fires only every few hours, so
    a watcher that stops without handing over leaves a gap in which a finished
    session waits for the next (late) scheduled run.
    """
    if os.environ.get("GITHUB_ACTIONS") != "true" or not needs_followup(datetime.now(timezone.utc)):
        return
    subprocess.run(
        ["gh", "workflow", "run", "update-data.yml", "--ref", "main"], cwd=ROOT, check=False
    )


def publish_changed_data() -> None:
    """Publish each successful classification without waiting for the watcher."""
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return
    changed = subprocess.run(
        ["git", "status", "--porcelain", "--", "data"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if not changed:
        return
    commands = (
        ("git", "config", "user.name", "github-actions[bot]"),
        ("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"),
        ("git", "add", "data"),
        ("git", "commit", "-m", "Update motorsport data"),
    )
    for command in commands:
        subprocess.run(command, cwd=ROOT, check=True)
    for attempt in range(3):
        subprocess.run(['git', 'fetch', 'origin', 'main'], cwd=ROOT, check=True)
        rebase_data()
        if subprocess.run(['git', 'push', 'origin', 'HEAD:main'], cwd=ROOT).returncode == 0:
            return
    raise RuntimeError('Remote changed during three publication attempts; local results retained')


def merge_event_results(upstream: dict, local: dict) -> dict:
    """Keep independently published classifications when rebasing a data update."""
    if upstream.get('data', {}).get('eventId') != local.get('data', {}).get('eventId'):
        raise ValueError('Cannot merge results from different events')
    merged = dict(local)
    sessions = {s['type']: s for s in upstream['data'].get('sessions', [])}
    for session in local['data'].get('sessions', []):
        previous = sessions.get(session['type'])
        if not session.get('results') and previous and previous.get('results'):
            continue
        if previous and previous.get('results') and previous.get('source', {}).get('name') == 'formula1-official' and session.get('source', {}).get('name') != 'formula1-official':
            continue
        sessions[session['type']] = session
    merged['data'] = {**local['data'], 'sessions': list(sessions.values())}
    return merged


def rebase_data() -> None:
    result = subprocess.run(['git', 'rebase', 'origin/main'], cwd=ROOT)
    while result.returncode:
        conflicts = subprocess.run(['git', 'diff', '--name-only', '--diff-filter=U'], cwd=ROOT, check=True, capture_output=True, text=True).stdout.splitlines()
        if not conflicts:
            raise RuntimeError('Rebase failed without resolvable result conflicts')
        for name in conflicts:
            path = (ROOT / name).resolve()
            if not path.is_relative_to(DATA.resolve()) or path.suffix != '.json':
                raise RuntimeError(f'Refusing to auto-resolve non-data conflict: {name}')
            if '/events/' not in name.replace('\\', '/'):
                # Calendars, standings and indexes are regenerated as a whole by
                # each run; the snapshot being replayed is the most recent one.
                # (During a rebase "--theirs" is the commit being replayed.)
                subprocess.run(['git', 'checkout', '--theirs', '--', name], cwd=ROOT, check=True)
                subprocess.run(['git', 'add', '--', name], cwd=ROOT, check=True)
                continue
            def stage(number):
                return json.loads(subprocess.run(['git', 'show', f':{number}:{name}'], cwd=ROOT, check=True, capture_output=True, text=True, encoding='utf-8').stdout)
            merged = merge_event_results(stage(2), stage(3))
            path.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            subprocess.run(['git', 'add', '--', name], cwd=ROOT, check=True)
        result = subprocess.run(['git', 'rebase', '--continue'], cwd=ROOT, env={**os.environ, 'GIT_EDITOR': 'true'})


def watch(max_seconds: int, interval_seconds: int) -> int:
    started = datetime.now(timezone.utc)
    deadline = started + timedelta(seconds=max_seconds)

    if manifest_is_stale(started):
        refresh()

    while True:
        now = datetime.now(timezone.utc)
        candidates = [
            item
            for item in missing_sessions(now)
            if now - timedelta(hours=6) <= item[0] <= deadline
        ]
        if not candidates:
            upcoming = [
                item[0] for item in missing_sessions(now)
                if deadline < item[0] <= now + timedelta(hours=FOLLOWUP_LOOKAHEAD_HOURS)
            ]
            if upcoming:
                # Hold the hand-over until the next watcher can cover the
                # session for its whole job window.
                wake = min(upcoming) - timedelta(seconds=max_seconds)
                wait_seconds = max(0.0, (wake - now).total_seconds())
                print(f"Idle for {int(wait_seconds)}s before handing over to the next watcher", flush=True)
                time.sleep(wait_seconds)
            else:
                print("No live classification needs a persistent watcher")
            return 0

        due, label = candidates[0]
        if due > now:
            wait_seconds = min((due - now).total_seconds(), (deadline - now).total_seconds())
            if wait_seconds <= 0:
                return 0
            print(f"Waiting {int(wait_seconds)}s for {label} to become due", flush=True)
            time.sleep(wait_seconds)
            continue

        attempt_started = time.monotonic()
        overdue = [item for item in candidates if item[0] <= now]
        series = {item[1].split("/", 1)[0] for item in overdue}
        print(f"Refreshing official data for {', '.join(item[1] for item in overdue)}", flush=True)
        refresh(series)
        still_missing = {item[1] for item in missing_sessions(datetime.now(timezone.utc))}
        for _due, overdue_label in overdue:
            if overdue_label not in still_missing:
                print(f"Official classification received for {overdue_label}", flush=True)
        if any(item[1] not in still_missing for item in overdue):
            continue

        remaining = (deadline - datetime.now(timezone.utc)).total_seconds()
        if remaining <= 0:
            print(f"Watcher deadline reached while waiting for {label}")
            return 0
        delay = min(
            max(0.0, interval_seconds - (time.monotonic() - attempt_started)),
            remaining,
        )
        print(f"No classification yet; retrying {label} in {int(delay)}s", flush=True)
        time.sleep(delay)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-seconds", type=int, default=19_800)
    parser.add_argument("--interval-seconds", type=int, default=60)
    args = parser.parse_args()
    code = watch(args.max_seconds, args.interval_seconds)
    dispatch_followup()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
