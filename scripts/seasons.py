"""Season helpers shared by the data pipeline.

Data lives in ``data/<series>/<season>/``. A series can hold the season that
is running and the next one whose calendar has already been published.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def season_dirs(series_root: Path) -> list[int]:
    """Seasons with a calendar, oldest first."""
    if not series_root.is_dir():
        return []
    return sorted(
        int(path.name)
        for path in series_root.iterdir()
        if path.name.isdigit() and (path / "calendar.json").is_file()
    )


def calendar_events(series_root: Path, season: int) -> list[dict]:
    path = series_root / str(season) / "calendar.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))["data"]
    except (FileNotFoundError, KeyError, ValueError):
        return []


def season_started(series_root: Path, season: int, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    return any(
        parse_time(session["startTimeUtc"]) <= now
        for event in calendar_events(series_root, season)
        for session in event.get("sessions", [])
        if not session.get("cancelled")
    )


def season_finished(series_root: Path, season: int, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    sessions = [
        session
        for event in calendar_events(series_root, season)
        if not event.get("cancelled")
        for session in event.get("sessions", [])
        if not session.get("cancelled")
    ]
    return bool(sessions) and all(
        parse_time(item["startTimeUtc"]) + timedelta(minutes=int(item.get("durationMinutes", 120))) <= now
        for item in sessions
    )


def results_season(series_root: Path, default: int, now: datetime | None = None) -> int:
    """The season whose results and standings are being produced: the latest
    season that has started (the previous one stays until the next begins)."""
    seasons = season_dirs(series_root)
    started = [season for season in seasons if season_started(series_root, season, now)]
    if started:
        return started[-1]
    return seasons[0] if seasons else default


def current_season(series_root: Path, default: int, now: datetime | None = None) -> int:
    """The season users follow now: the earliest one that is not finished."""
    seasons = season_dirs(series_root)
    for season in seasons:
        if not season_finished(series_root, season, now):
            return season
    return seasons[-1] if seasons else default
