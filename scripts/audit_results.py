"""Audit every published classification for gaps and inconsistencies.

Checks, per series, season and event:

* every session that has ended and is expected to publish a classification
  has one (``refresh_decision.expects_results``);
* positions start at 1, are unique and contiguous (unclassified rows last);
* no car or driver appears twice in one session, and no row lacks a name;
* practice and qualifying grids share their cars with the race (a session
  copied from another championship would not);
* standings are ordered by position with non-increasing points per class;
* optionally (``--online``) F1 race podiums match the Jolpica archive.

Run: ``python scripts/audit_results.py [--online] [--data-root data]``.
Exit code 1 when an error is found; warnings are informational.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from http_retry import read
from refresh_decision import GT3_SERIES, expects_results
from seasons import parse_time

ROOT = Path(__file__).resolve().parents[1]
# Results older than this are final; younger gaps may still be in progress.
GRACE = timedelta(hours=6)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def session_checks(label: str, session: dict, errors: list[str], warnings: list[str]) -> None:
    rows = session.get("results", [])
    positions = [row.get("position") for row in rows if row.get("position") is not None]
    if positions and sorted(positions) != list(range(1, len(positions) + 1)):
        errors.append(f"{label}: positions are not 1..{len(positions)} ({sorted(positions)[:6]}...)")
    seen_unclassified = False
    for row in rows:
        if row.get("position") is None:
            seen_unclassified = True
        elif seen_unclassified:
            errors.append(f"{label}: classified row after an unclassified one")
            break
    cars = Counter(row.get("carNumber") for row in rows if row.get("carNumber"))
    duplicates = [car for car, count in cars.items() if count > 1]
    if duplicates:
        errors.append(f"{label}: car numbers listed twice {duplicates[:5]}")
    if not cars:
        drivers = Counter(row["driver"].get("id") for row in rows)
        repeated = [driver for driver, count in drivers.items() if count > 1]
        if repeated:
            errors.append(f"{label}: drivers listed twice {repeated[:5]}")
    unnamed = [row.get("carNumber") or row.get("positionText") for row in rows
               if not (row["driver"].get("givenName") or row["driver"].get("familyName") or "").strip()]
    if unnamed:
        errors.append(f"{label}: rows without a driver name {unnamed[:5]}")
    if rows and session["type"] in ("R", "SPRINT") and not rows[0].get("time"):
        warnings.append(f"{label}: winner has no race time")


def event_checks(series: str, season: int, event: dict, document: dict, now: datetime,
                 errors: list[str], warnings: list[str]) -> None:
    sessions = {item["type"]: item for item in document["data"].get("sessions", []) if item.get("results")}
    prefix = f"{series} {season} R{event['round']} {event['name']}"
    for scheduled in event.get("sessions", []):
        if scheduled.get("cancelled") or event.get("cancelled"):
            continue
        end = parse_time(scheduled["startTimeUtc"]) + timedelta(minutes=int(scheduled.get("durationMinutes", 120)))
        if end + GRACE > now or not expects_results(series, scheduled["type"]):
            continue
        if scheduled["type"] not in sessions:
            message = f"{prefix}: no classification for {scheduled['name']} ({scheduled['type']})"
            # GT3 timetables list sessions (tests, bronze practice) that are
            # often never classified; races must always be.
            race = re.fullmatch(r"R\d*|SPRINT", scheduled["type"])
            (errors if race or series not in GT3_SERIES else warnings).append(message)
    for kind, session in sessions.items():
        session_checks(f"{prefix} {kind}", session, errors, warnings)
    grid = {row.get("carNumber") for kind, item in sessions.items() if re.fullmatch(r"R\d*", kind)
            for row in item["results"] if row.get("carNumber")}
    if len(grid) >= 5:
        for kind, item in sessions.items():
            cars = {row.get("carNumber") for row in item["results"] if row.get("carNumber")}
            if cars and not re.fullmatch(r"R\d*", kind) and len(cars & grid) < 0.5 * len(cars):
                errors.append(f"{prefix} {kind}: entry list does not match the race grid")


def standings_checks(series: str, season: int, folder: Path, errors: list[str]) -> None:
    for name in ("standings_drivers.json", "standings_teams.json"):
        path = folder / name
        if not path.is_file():
            continue
        by_class: dict[str | None, list[dict]] = {}
        for row in load(path)["data"]:
            by_class.setdefault(row.get("category"), []).append(row)
        for category, rows in by_class.items():
            for previous, current in zip(rows, rows[1:]):
                if current["position"] < previous["position"] or current["points"] > previous["points"] + 1e-9:
                    errors.append(f"{series} {season} {name} {category or ''}: "
                                  f"P{current['position']} {current.get('id')} out of order")
                    break


def f1_podiums(data_root: Path, errors: list[str]) -> None:
    for folder in sorted((data_root / "f1").glob("*/calendar.json")):
        season = folder.parent.name
        try:
            payload = json.loads(read(f"https://api.jolpi.ca/ergast/f1/{season}/results/1.json?limit=100",
                                      {"User-Agent": "SecarAudit/1.0"}))
        except Exception as error:  # noqa: BLE001
            print(f"f1 {season}: archive unavailable ({error})")
            continue
        winners = {
            race["date"]: race["Results"][0]["Driver"]["familyName"]
            for race in payload["MRData"]["RaceTable"]["Races"]
        }
        for event in load(folder)["data"]:
            race = next((item for item in event["sessions"] if item["type"] == "R"), None)
            document = load(folder.parent / event["resultsPath"])
            result = next((item for item in document["data"]["sessions"] if item["type"] == "R"), None)
            if not race or not result or not result["results"]:
                continue
            archived = winners.get(race["startTimeUtc"][:10])
            ours = result["results"][0]["driver"].get("familyName", "")
            if archived and archived.casefold() not in ours.casefold():
                errors.append(f"f1 {season} {event['name']}: winner {ours}, archive says {archived}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=ROOT / "data")
    parser.add_argument("--online", action="store_true", help="also compare F1 winners with the Jolpica archive")
    args = parser.parse_args(argv)
    now = datetime.now(timezone.utc)
    errors: list[str] = []
    warnings: list[str] = []
    counted = Counter()
    for calendar_path in sorted(args.data_root.glob("*/*/calendar.json")):
        series, season = calendar_path.parent.parent.name, int(calendar_path.parent.name)
        for event in load(calendar_path)["data"]:
            document = load(calendar_path.parent / event["resultsPath"])
            if document["data"].get("eventId") != event["id"]:
                errors.append(f"{series} {season} {event['name']}: result document belongs to another event")
                continue
            event_checks(series, season, event, document, now, errors, warnings)
            counted[series] += sum(1 for item in document["data"]["sessions"] if item.get("results"))
        standings_checks(series, season, calendar_path.parent, errors)
    if args.online:
        f1_podiums(args.data_root, errors)
    for line in warnings:
        print(f"warning: {line}")
    for line in errors:
        print(f"ERROR: {line}")
    print("classifications checked: " + ", ".join(f"{key} {value}" for key, value in sorted(counted.items())))
    print(f"{len(errors)} errors, {len(warnings)} warnings")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
