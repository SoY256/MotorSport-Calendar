"""Decide whether the five-minute scheduler needs a data refresh."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
# Kept in sync with scripts/fetch_gt3_results.py (not imported: this module
# must stay dependency-free for the five-minute scheduler).
GT3_SERIES = frozenset(
    {"gtwc-europe", "gtwc-america", "gtwc-asia", "gtwc-australia", "british-gt", "igtc"}
)


def expects_results(series: str, session_type: str) -> bool:
    """Return whether the configured importer publishes this classification."""
    return (
        series in {"f1", "f2", "f3", "wec"}
        or series in GT3_SERIES
        or session_type == "R"
    )


# A GT3 classification that has not appeared this long after its session is
# not polled for any more: some never appear on the SRO sites (bronze tests,
# rounds timed by third parties). The six-hour refresh still picks up late
# publications. Other series keep polling until their classification exists.
POLL_WINDOW = timedelta(hours=6)


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
                end = timestamp(session["startTimeUtc"]) + timedelta(
                    minutes=int(session.get("durationMinutes", 120))
                )
                due = end + timedelta(minutes=5)
                # Once a session is due, keep polling until its classification
                # is present (GT3: within the polling window). Only then does
                # the six-hour cadence resume.
                if due <= now and (series_dir.name not in GT3_SERIES or now <= due + POLL_WINDOW):
                    return True, f"awaiting-{series_dir.name}-{event['id']}-{session_type}"
    return False, "not-due"


if __name__ == "__main__":
    should_run, reason = decision(datetime.now(timezone.utc))
    print(f"run={'true' if should_run else 'false'}")
    print(f"reason={reason}")
