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
# Written when a race classification is published before the standings that
# include it. Sources without points in their race results (WEC, IMSA, GT)
# cannot be compared with the standings, so this marker tells the watchers to
# keep polling the series until its standings total moves.
PENDING = "pending_standings.json"
PENDING_WINDOW = timedelta(hours=12)


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


def classified_races(season_dir: Path) -> set[str]:
    races: set[str] = set()
    for path in season_dir.glob("events/*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))["data"]
        except (KeyError, ValueError):
            continue
        for session in data.get("sessions", []):
            if is_race(session.get("type", "")) and session.get("results"):
                races.add(f"{data.get('eventId', path.stem)}/{session['type']}")
    return races


def read_pending(season_dir: Path) -> dict | None:
    try:
        marker = json.loads((season_dir / PENDING).read_text(encoding="utf-8"))
        marker["since"] = parse_time(marker["since"])
        marker["pointsBefore"] = float(marker["pointsBefore"])
        return marker
    except (FileNotFoundError, KeyError, TypeError, ValueError):
        return None


def pending_since(season_dir: Path, now: datetime) -> datetime | None:
    """When a race was published that the standings do not include yet."""
    marker = read_pending(season_dir)
    current = file_progress(season_dir / "standings_drivers.json")
    if marker is None or current is None:
        return None
    if now - marker["since"] > PENDING_WINDOW or current[0] > marker["pointsBefore"] + 0.01:
        return None
    return marker["since"]


def mark_pending_standings(staged: Path, published: Path, now: datetime | None = None) -> None:
    """Record in ``staged`` that a newly published race is not yet in the
    standings, for every series alike (see ``PENDING``)."""
    now = now or datetime.now(timezone.utc)
    marker_path = staged / PENDING
    before = file_progress(published / "standings_drivers.json")
    after = file_progress(staged / "standings_drivers.json")
    previous = read_pending(published)
    marker: dict | None = None
    if before is not None and after is not None and after[0] <= before[0] + 0.01:
        new_races = classified_races(staged) - classified_races(published)
        if previous is not None and now - previous["since"] <= PENDING_WINDOW and after[0] <= previous["pointsBefore"] + 0.01:
            marker = {
                "races": sorted(set(previous.get("races", [])) | new_races),
                "pointsBefore": previous["pointsBefore"],
                "since": previous["since"],
            }
        elif new_races:
            marker = {"races": sorted(new_races), "pointsBefore": before[0], "since": now}
    if marker is None:
        marker_path.unlink(missing_ok=True)
        return
    marker["since"] = marker["since"].astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    marker_path.write_text(json.dumps(marker, indent=2) + "\n", encoding="utf-8")


def standings_due(season_dir: Path, now: datetime | None = None, window: timedelta = timedelta(hours=24)) -> datetime | None:
    """When the driver standings became due but still miss a race: from the
    points in the race results (F1, F2, F3, INDYCAR, INDY NXT) or from a
    pending marker (every series)."""
    now = now or datetime.now(timezone.utc)
    current = file_progress(season_dir / "standings_drivers.json")
    if current is None:
        return None
    awarded, latest = results_points(season_dir)
    if latest is not None and now - latest <= window and current[0] + 0.01 < awarded:
        return latest
    return pending_since(season_dir, now)


def standings_behind(season_dir: Path, now: datetime | None = None, window: timedelta = timedelta(hours=24)) -> bool:
    """Whether the driver standings do not yet include a recently classified race."""
    return standings_due(season_dir, now, window) is not None
