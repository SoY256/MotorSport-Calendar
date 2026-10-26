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
from standings_progress import PENDING, progress, standings_due

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
# Official classifications appear within minutes of the flag; polling starts
# this long after the scheduled end and then repeats every interval.
LIVE_GRACE_MINUTES = 2
FOLLOWUP_LOOKAHEAD_HOURS = 8


def missing_sessions(now: datetime) -> list[tuple[datetime, str]]:
    missing: list[tuple[datetime, str]] = []
    # Every season, including an announced next season.
    for calendar_path in sorted(DATA.glob("*/*/calendar.json")):
        series_dir = calendar_path.parent.parent
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
    # Standings that do not include a recently classified race yet, in every
    # series (F1 also has its own lane that polls formula1.com every minute).
    for series_dir in sorted(path for path in DATA.iterdir() if path.is_dir() and path.name != "f1"):
        for season_dir in sorted(path for path in series_dir.iterdir() if (path / "calendar.json").is_file()):
            try:
                due = standings_due(season_dir, now)
            except (KeyError, ValueError):
                continue
            if due is not None:
                missing.append(
                    (due + timedelta(minutes=LIVE_GRACE_MINUTES), f"{series_dir.name}/{season_dir.name}/standings")
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
        base = subprocess.run(
            ['git', 'merge-base', 'HEAD', 'origin/main'], cwd=ROOT, check=True, capture_output=True, text=True
        ).stdout.strip()
        rebase_data()
        if not keep_newest_standings(base):
            print('Nothing newer than the published data to publish', flush=True)
            return
        if subprocess.run(['git', 'push', 'origin', 'HEAD:main'], cwd=ROOT).returncode == 0:
            return
    raise RuntimeError('Remote changed during three publication attempts; local results retained')


def git_json(revision: str, name: str) -> dict | None:
    shown = subprocess.run(
        ['git', 'show', f'{revision}:{name}'], cwd=ROOT, capture_output=True, text=True, encoding='utf-8'
    )
    if shown.returncode:
        return None
    try:
        return json.loads(shown.stdout)
    except ValueError:
        return None


def newer_standings(upstream: dict | None, local: dict | None) -> str:
    """'upstream' or 'local': the standings snapshot that includes more races.

    A job that started before a race can finish after a faster one; its table
    must not replace the updated one (points only grow during a season).
    """
    if upstream is None:
        return 'local'
    if local is None:
        return 'upstream'
    return 'upstream' if progress(upstream) > progress(local) else 'local'


def keep_newest_standings(base: str) -> bool:
    """Restore standings that another job published while this one ran and
    that are ahead of this job's snapshot (a correction that lowers points,
    e.g. a disqualification, still goes through when nobody else touched the
    table in the meantime).

    Returns False when nothing of this job's commit is left to publish.
    """
    changed = subprocess.run(
        ['git', 'diff', '--name-only', 'origin/main', 'HEAD', '--', 'data'],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.split()

    def published_meanwhile(name: str) -> bool:
        return subprocess.run(['git', 'diff', '--quiet', base, 'origin/main', '--', name], cwd=ROOT).returncode == 1

    restored = [
        name for name in changed
        if Path(name).name.startswith('standings_')
        and published_meanwhile(name)
        and newer_standings(git_json('origin/main', name), git_json('HEAD', name)) == 'upstream'
    ]
    if restored:
        subprocess.run(['git', 'checkout', 'origin/main', '--', *restored], cwd=ROOT, check=True)
        for name in restored:
            print(f'Kept the newer published {name}', flush=True)
        if len(restored) == len(changed):
            subprocess.run(['git', 'reset', '--hard', 'origin/main'], cwd=ROOT, check=True)
            return False
        subprocess.run(['git', 'commit', '--amend', '--no-edit'], cwd=ROOT, check=True)
    return bool(changed)


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
                # Calendars and indexes are regenerated as a whole by each
                # run; the snapshot being replayed is the most recent one.
                # (During a rebase "--theirs" is the commit being replayed.)
                # Standings keep whichever snapshot includes more races.
                if Path(name).name == PENDING:
                    # Keep a pending-standings marker if either side has one;
                    # it expires by itself once the standings move.
                    for side in ('--theirs', '--ours'):
                        if subprocess.run(['git', 'checkout', side, '--', name], cwd=ROOT).returncode == 0:
                            subprocess.run(['git', 'add', '--', name], cwd=ROOT, check=True)
                            break
                    else:
                        subprocess.run(['git', 'rm', '-q', '--', name], cwd=ROOT, check=True)
                    continue
                side = '--theirs'
                if Path(name).name.startswith('standings_'):
                    def staged(number):
                        return git_json(f':{number}', name)
                    if newer_standings(staged(2), staged(3)) == 'upstream':
                        side = '--ours'
                subprocess.run(['git', 'checkout', side, '--', name], cwd=ROOT, check=True)
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
