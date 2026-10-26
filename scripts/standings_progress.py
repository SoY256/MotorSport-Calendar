"""How far a published standings table has progressed.

Points only grow during a season, so of two snapshots of the same table the
one with more points (then more wins) is the newer one. A data job that
started before a race may otherwise publish its pre-race table after a
faster job has already published the updated one.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from seasons import parse_time

RACE_TYPES = ("R", "SPRINT")


def progress(document: dict) -> tuple[float, int]:
    rows = document.get("data") or []
    return (
        round(sum(float(row.get("points") or 0) for row in rows), 3),
        sum(int(row.get("wins") or 0) for row in rows),
    )


def file_progress(path: Path) -> tuple[float, int] | None:
    try:
        return progress(json.loads(path.read_text(encoding="utf-8")))
    except (FileNotFoundError, ValueError):
        return None


def is_race(session_type: str) -> bool:
    return session_type.startswith(RACE_TYPES)


def results_points(season_dir: Path) -> tuple[float, datetime | None]:
    """Points awarded in the season's race classifications and the end of the
    latest classified race (series whose results carry points: F1, F2, F3,
    INDYCAR, INDY NXT)."""
    total = 0.0
    latest: datetime | None = None
    calendar = json.loads((season_dir / "calendar.json").read_text(encoding="utf-8"))["data"]
    for event in calendar:
        try:
            document = json.loads((season_dir / event["resultsPath"]).read_text(encoding="utf-8"))
        except (FileNotFoundError, KeyError, ValueError):
            continue
        scheduled = {session["type"]: session for session in event.get("sessions", [])}
        for session in document.get("data", {}).get("sessions", []):
            if not is_race(session["type"]) or not session.get("results"):
                continue
            points = sum(float(row.get("points") or 0) for row in session["results"])
            if not points:
                continue
            total += points
            plan = scheduled.get(session["type"], session)
            end = parse_time(plan["startTimeUtc"]) + timedelta(minutes=int(plan.get("durationMinutes") or 120))
            latest = end if latest is None or end > latest else latest
    return round(total, 3), latest


def standings_behind(season_dir: Path, now: datetime | None = None, window: timedelta = timedelta(hours=24)) -> bool:
    """Whether the driver standings do not yet include a race classified in
    the last ``window`` (the standings total is below the points awarded)."""
    now = now or datetime.now(timezone.utc)
    current = file_progress(season_dir / "standings_drivers.json")
    if current is None:
        return False
    awarded, latest = results_points(season_dir)
    return latest is not None and now - latest <= window and current[0] + 0.01 < awarded
