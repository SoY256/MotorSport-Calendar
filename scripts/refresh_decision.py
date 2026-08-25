"""Decide whether the five-minute scheduler needs a data refresh."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def result_types(path: Path) -> set[str]:
    try:
        sessions = json.loads(path.read_text(encoding="utf-8"))["data"]["sessions"]
        return {session["type"] for session in sessions if session.get("results")}
    except (FileNotFoundError, KeyError, TypeError, json.JSONDecodeError):
        return set()


def decision(now: datetime) -> tuple[bool, str]:
    try:
        manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
        last_update = timestamp(manifest["lastSuccessfulUpdate"])
    except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError):
        return True, "missing-or-invalid-manifest"
    if now - last_update >= timedelta(hours=6):
        return True, "six-hour-refresh"

    for series_dir in DATA.iterdir():
        calendar_path = series_dir / "2026" / "calendar.json"
        if not calendar_path.is_file():
            continue
        events = json.loads(calendar_path.read_text(encoding="utf-8"))["data"]
        for event in events:
            available = result_types(calendar_path.parent / event["resultsPath"])
            for session in event.get("sessions", []):
                if session.get("cancelled") or session.get("type") in available:
                    continue
                end = timestamp(session["startTimeUtc"]) + timedelta(
                    minutes=int(session.get("durationMinutes", 120))
                )
                due = end + timedelta(minutes=5)
                # Arm polling around a newly completed session, not for a
                # permanently absent classification from an old archive.
                if due <= now <= due + timedelta(days=7):
                    return True, f"awaiting-{series_dir.name}-{event['id']}-{session['type']}"
    return False, "not-due"


if __name__ == "__main__":
    should_run, reason = decision(datetime.now(timezone.utc))
    print(f"run={'true' if should_run else 'false'}")
    print(f"reason={reason}")
