"""Publish next-season calendars as soon as the organisers announce them.

The regular importers produce the season that is running. Before the next
season starts, its official calendar is often already published (F1 and FIA
WEC announce it during the current season). This importer writes those
calendars to ``data/<series>/<next season>/`` so the app can show them; the
regular importer takes the folder over once the season has started.

Times that the organisers have not confirmed are marked ``timeTbc``.
"""

from __future__ import annotations

import html as html_lib
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from fetch_data import slugify, write_json
from fetch_wec_results import RACE_PAGE_ALIASES, official_timetable
from check_schedules import parse_wec
from http_retry import read
from seasons import results_season

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "official-next-season-calendar"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SecarCalendar/1.0; +https://github.com/SoY256/MotorSport-Calendar)"}

F1_SESSION_TYPES = {
    "Practice 1": ("FP1", 60),
    "Practice 2": ("FP2", 60),
    "Practice 3": ("FP3", 60),
    "Sprint Qualifying": ("SQ", 45),
    "Sprint": ("SPRINT", 60),
    "Qualifying": ("Q", 60),
    "Race": ("R", 120),
}
# Venues new to the calendar (others reuse the previous season's circuit).
F1_NEW_CIRCUITS = {
    "bahrain": ("Bahrain Grand Prix", "Bahrain International Circuit", "Sakhir", "Bahrain", "BHR"),
    "brazil": ("São Paulo Grand Prix", "Autódromo José Carlos Pace", "São Paulo", "Brazil", "BRA"),
    "mexico": ("Mexico City Grand Prix", "Autódromo Hermanos Rodríguez", "Mexico City", "Mexico", "MEX"),
    "portugal": ("Portuguese Grand Prix", "Algarve International Circuit", "Portimão", "Portugal", "PRT"),
    "turkey": ("Turkish Grand Prix", "Istanbul Park", "Istanbul", "Turkey", "TUR"),
}
WEC_NEW_EVENTS = {
    "qatar": ("Qatar 1812 km", "Lusail International Circuit", "Lusail", "Qatar", "QAT"),
    "silverstone": ("6 Hours of Silverstone", "Silverstone Circuit", "Silverstone", "United Kingdom", "GBR"),
    "bahrain": ("8 Hours of Bahrain", "Bahrain International Circuit", "Sakhir", "Bahrain", "BHR"),
}
WEC_RACE_MINUTES = {"24-hours": 1440, "8-hours": 480, "1812km": 600}


def get(url: str) -> str:
    return read(url, HEADERS, timeout=40, attempts=3).decode("utf-8", "replace")


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def document(data, url: str, updated: str) -> dict:
    return {"schemaVersion": 1, "lastSuccessfulUpdate": updated, "source": {"name": SOURCE, "url": url}, "data": data}


def managed_by_us(folder: Path) -> bool:
    """A season folder may be (re)written only if this importer created it."""
    calendar = folder / "calendar.json"
    if not calendar.is_file():
        return True
    try:
        return json.loads(calendar.read_text(encoding="utf-8"))["source"]["name"] == SOURCE
    except (KeyError, ValueError):
        return False


def circuit(name: str, locality: str, country: str, code: str) -> dict:
    return {"id": slugify(name), "name": name, "locality": locality, "country": country, "countryCode": code}


def previous_events(series_root: Path, season: int) -> list[dict]:
    path = series_root / str(season - 1) / "calendar.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))["data"]
    except (FileNotFoundError, KeyError, ValueError):
        return []


# --------------------------------------------------------------------------
# Formula 1 (formula1.com race hub pages)
# --------------------------------------------------------------------------


def f1_event(season: int, slug: str, page: str, previous: list[dict]) -> dict | None:
    blocks = re.findall(r'<script type="application/ld\+json">([\s\S]*?)</script>', page)
    data = next((json.loads(block) for block in blocks if '"subEvent"' in block), None)
    if not data:
        return None
    sessions_ld = data.get("subEvent", [])
    race = next((item for item in sessions_ld if item["name"].startswith("Race - ")), None)
    if race is None:
        return None
    name = race["name"].split(" - ", 1)[1].strip()
    visible = re.sub(r"<[^>]+>", " ", re.sub(r"<script[\s\S]*?</script>", " ", page))
    # Until the organiser confirms the timetable every time reads "TBC" and
    # the session list is a placeholder: keep only the race day.
    confirmed = "TBC" not in visible
    sessions = []
    for item in sessions_ld:
        label = item["name"].split(" - ", 1)[0].strip()
        if label not in F1_SESSION_TYPES or (not confirmed and label != "Race"):
            continue
        kind, minutes = F1_SESSION_TYPES[label]
        start = datetime.fromisoformat(item["startDate"].replace("Z", "+00:00"))
        session = {"type": kind, "name": label, "startTimeUtc": iso(start), "cancelled": False, "durationMinutes": minutes}
        if not confirmed:
            session["timeTbc"] = True
        sessions.append(session)
    location = data.get("location", {}).get("name", "")
    known = next((event for event in previous if event["name"] == name), None)
    if slug == "spain":
        madrid = "madrid" in location.lower()
        known = next(
            (event for event in previous if (event["circuit"]["name"] == "Madring") == madrid
             and event["circuit"]["countryCode"] == "ESP"),
            known,
        )
    if known:
        venue = {key: known["circuit"][key] for key in ("id", "name", "locality", "country", "countryCode")}
        name = known["name"] if slug != "spain" else name
    elif slug in F1_NEW_CIRCUITS:
        event_name, *details = F1_NEW_CIRCUITS[slug]
        name = name or event_name
        venue = circuit(*details)
    else:
        print(f"f1 {season} {slug}: unknown circuit, skipped", file=sys.stderr)
        return None
    return {"name": name, "circuit": venue, "sessions": sessions, "url": f"https://www.formula1.com/en/racing/{season}/{slug}"}


def f1_calendar(season: int, previous: list[dict]) -> list[dict]:
    hub = get(f"https://www.formula1.com/en/racing/{season}")
    slugs = sorted({slug for slug in re.findall(rf'href="/en/racing/{season}/([a-z0-9-]+)"', hub) if "testing" not in slug})
    if len(slugs) < 10:
        return []
    with ThreadPoolExecutor(max_workers=6) as pool:
        pages = dict(zip(slugs, pool.map(lambda slug: get(f"https://www.formula1.com/en/racing/{season}/{slug}"), slugs)))
    events = [event for slug in slugs if (event := f1_event(season, slug, pages[slug], previous))]
    return sorted(events, key=lambda event: event["sessions"][-1]["startTimeUtc"])


# --------------------------------------------------------------------------
# FIA WEC (fiawec.com season and race pages)
# --------------------------------------------------------------------------


def wec_calendar(season: int, previous: list[dict]) -> list[dict]:
    overview = get(f"https://www.fiawec.com/en/season/{season}")
    paths = sorted({
        path for path in re.findall(rf'href="(/en/race/[a-z0-9-]+-{season})"', overview) if "prologue" not in path
    })
    if len(paths) < 4:
        return []
    by_alias = {alias: name for name, alias in RACE_PAGE_ALIASES.items()}
    race_days = {event.name: event.date for event in parse_wec(overview, season)}
    events = []
    for path in paths:
        slug = path.rsplit("/", 1)[1].removesuffix(f"-{season}")
        page = get("https://www.fiawec.com" + path)
        sessions = official_timetable(page)
        if sum(1 for item in sessions if item["type"] == "R") != 1:
            day = race_days.get(slug)
            if day is None:
                continue
            # Race day announced, timetable not yet published.
            sessions = [{
                "type": "R", "name": "Race", "cancelled": False, "timeTbc": True,
                "startTimeUtc": f"{day.isoformat()}T12:00:00Z",
            }]
        alias = next((alias for alias in by_alias if alias in slug), None)
        known = next((event for event in previous if alias and event["name"] == by_alias[alias]), None)
        new = next((value for key, value in WEC_NEW_EVENTS.items() if key in slug), None)
        if known:
            name = known["name"]
            venue = {key: known["circuit"][key] for key in ("id", "name", "locality", "country", "countryCode")}
        elif new:
            name, *details = new
            venue = circuit(*details)
        else:
            print(f"wec {season} {slug}: unknown venue, skipped", file=sys.stderr)
            continue
        race_minutes = next((minutes for key, minutes in WEC_RACE_MINUTES.items() if key in slug), 360)
        for item in sessions:
            item["durationMinutes"] = race_minutes if item["type"] == "R" else 60
        events.append({"name": name, "circuit": venue, "sessions": sessions, "url": "https://www.fiawec.com" + path})
    return sorted(events, key=lambda event: event["sessions"][-1]["startTimeUtc"])


BUILDERS = {"f1": f1_calendar, "wec": wec_calendar}


def publish(series: str, season: int, events: list[dict], data_root: Path) -> None:
    folder = data_root / series / str(season)
    updated = iso(datetime.now(timezone.utc))
    calendar = []
    for round_number, event in enumerate(events, start=1):
        event_id = f"{series}-{season}-{round_number}"
        results_path = f"events/{round_number:02d}-{slugify(event['name'])}.json"
        calendar.append({
            "id": event_id, "seriesId": series, "season": season, "round": round_number,
            "name": event["name"], "cancelled": False, "circuit": event["circuit"],
            "sessions": event["sessions"], "resultsPath": results_path,
        })
        result = folder / results_path
        if not result.is_file():
            write_json(result, document({"eventId": event_id, "sessions": []}, event["url"], updated))
    for stale in (folder / "events").glob("*.json"):
        if stale.relative_to(folder).as_posix() not in {event["resultsPath"] for event in calendar}:
            stale.unlink()
    write_json(folder / "calendar.json", document(calendar, events[0]["url"].rsplit("/", 1)[0], updated))
    for name in ("standings_drivers.json", "standings_teams.json"):
        if not (folder / name).is_file():
            write_json(folder / name, document([], events[0]["url"], updated))
    print(f"{series} {season}: {len(calendar)} rounds (next season)")


def main() -> int:
    data_root = Path(os.environ.get("MOTORSPORT_DATA_ROOT", ROOT / "assets" / "data"))
    now = datetime.now(timezone.utc)
    for series, builder in BUILDERS.items():
        series_root = data_root / series
        season = results_season(series_root, now.year, now) + 1
        folder = series_root / str(season)
        if not managed_by_us(folder):
            continue
        try:
            events = builder(season, previous_events(series_root, season))
        except Exception as error:  # an unpublished or unreachable calendar is not an error
            print(f"{series} {season}: next season unavailable ({error})", file=sys.stderr)
            continue
        if events:
            publish(series, season, events, data_root)
        else:
            print(f"{series} {season}: calendar not published yet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
