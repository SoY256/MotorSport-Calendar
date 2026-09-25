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
                    minutes=int(session.get("durationMinutes", 120)) + 5
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


def refresh() -> bool:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "update_all_data.py")],
        cwd=ROOT,
        check=False,
    )
    if completed.returncode == 0:
        publish_changed_data()
        return True
    return False


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
        ("git", "fetch", "origin", "main"),
        ("git", "rebase", "origin/main"),
        ("git", "push"),
    )
    for command in commands:
        subprocess.run(command, cwd=ROOT, check=True)


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
        print(f"Refreshing official data for {label}", flush=True)
        refresh()
        if all(item[1] != label for item in missing_sessions(datetime.now(timezone.utc))):
            print(f"Official classification received for {label}", flush=True)
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
    parser.add_argument("--interval-seconds", type=int, default=300)
    args = parser.parse_args()
    return watch(args.max_seconds, args.interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
