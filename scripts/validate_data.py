"""Fail fast when bundled motorsport data is incomplete or references missing assets."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "assets" / "data"
PUBLISHED_DATA = ROOT / "data"
# Drivers without an identity-verified face photo show initials instead of a
# guessed or shared portrait.
PORTRAIT_EXEMPT: dict[str, set[str]] = {}
# GT3 grids are large and partly amateur: drivers without an official studio
# portrait show initials, circuits without a bundled map show none, and rounds
# timed by third parties (e.g. the Nürburgring 24h) may have no classification.
LENIENT_SERIES = frozenset(
    {"gtwc-europe", "gtwc-america", "gtwc-asia", "gtwc-australia", "british-gt", "igtc"}
)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    now = datetime.now(timezone.utc)
    manifest = load(DATA / "manifest.json")
    ids = [item["id"] for item in manifest["availableSeries"]]
    pairs = [
        (item["id"], season)
        for item in manifest["availableSeries"]
        for season in sorted(set(item.get("publishedSeasons") or item["availableSeasons"]))
    ]
    if len(ids) != len(set(ids)) or not {"f1", "f2", "f3", "imsa", "indycar", "indynxt", "wec"}.issubset(ids):
        raise AssertionError(f"Incomplete or duplicate series manifest: {ids}")

    dart = (ROOT / "lib" / "features" / "calendar" / "domain" / "circuit_metadata.dart").read_text(encoding="utf-8")
    mapped = set(re.findall(r"'([^']+)'\s*(?:\|\||=>)", dart))
    failures = []
    notes = []
    summary = []
    for series_id, season in pairs:
        lenient = series_id in LENIENT_SERIES
        root = DATA / series_id / str(season)
        calendar = load(root / "calendar.json")["data"]
        drivers = load(root / "standings_drivers.json")["data"]
        teams = load(root / "standings_teams.json")["data"]
        started = any(
            datetime.fromisoformat(item["startTimeUtc"].replace("Z", "+00:00")) <= now
            for event in calendar
            for item in event["sessions"]
        )
        # A season that has not started yet (next-season calendar) has no standings.
        if not calendar or (started and (not drivers or not teams)):
            failures.append(f"{series_id}: empty calendar/driver/team standings")
        driver_keys = [(item.get("category"), item["id"]) for item in drivers]
        team_keys = [(item.get("category"), item["id"]) for item in teams]
        if len(driver_keys) != len(set(driver_keys)):
            failures.append(f"{series_id}: duplicate driver standings rows within a category")
        if len(team_keys) != len(set(team_keys)):
            failures.append(f"{series_id}: duplicate team standings rows within a category")
        missing_portraits = [
            f"{item.get('givenName', '')} {item.get('familyName', '')}".strip()
            for item in drivers
            if not item.get("imageUrl")
            and f"{item.get('givenName', '')} {item.get('familyName', '')}".strip()
            not in PORTRAIT_EXEMPT.get(series_id, set())
        ]
        if missing_portraits and lenient:
            notes.append(f"{series_id}: {len(missing_portraits)} drivers shown with initials")
        elif missing_portraits:
            failures.append(
                f"{series_id}: missing driver portraits for {', '.join(missing_portraits)}"
            )
        not_faces = [
            f"{item.get('givenName', '')} {item.get('familyName', '')}".strip()
            for item in drivers
            if item.get("imageUrl")
            and not (
                item["imageUrl"].startswith("assets/portraits/faces/")
                and (ROOT / item["imageUrl"]).is_file()
            )
        ]
        if not_faces:
            failures.append(f"{series_id}: portraits must be bundled face crops: {', '.join(not_faces)}")
        if series_id == "wec":
            entry_teams: dict[tuple[str | None, int, str], set[tuple[str, ...]]] = {}
            for item in drivers:
                entry_key = (item.get("category"), item["position"], item.get("code", ""))
                entry_teams.setdefault(entry_key, set()).add(tuple(item.get("teamIds", [])))
            inconsistent_entries = [key for key, values in entry_teams.items() if len(values) > 1]
            if inconsistent_entries:
                failures.append(
                    f"wec: inconsistent teams within standings entries {inconsistent_entries}"
                )
        completed = populated = 0
        for event in calendar:
            if event["circuit"]["name"] not in mapped and not lenient:
                failures.append(f"{series_id} R{event['round']}: no circuit asset mapping for {event['circuit']['name']}")
            result_path = root / event["resultsPath"]
            if not result_path.exists():
                failures.append(f"{series_id} R{event['round']}: missing {event['resultsPath']}")
                continue
            sessions = load(result_path)["data"]["sessions"]
            published_path = PUBLISHED_DATA / series_id / str(season) / event["resultsPath"]
            if published_path.exists():
                published_sessions = load(published_path)["data"]["sessions"]
                bundled_types = {
                    session["type"]
                    for session in sessions
                    if session.get("results")
                }
                published_types = {
                    session["type"]
                    for session in published_sessions
                    if session.get("results")
                }
                missing_types = published_types - bundled_types
                if missing_types:
                    failures.append(
                        f"{series_id} R{event['round']}: bundled fallback is missing "
                        f"published results for {', '.join(sorted(missing_types))}"
                    )
            ended = (
                not event.get("cancelled", False)
                and max(datetime.fromisoformat(item["startTimeUtc"].replace("Z", "+00:00")) for item in event["sessions"]) < now
            )
            if ended:
                completed += 1
                if not sessions or not any(session.get("results") for session in sessions):
                    message = f"{series_id} R{event['round']}: completed event has no results"
                    (notes if lenient else failures).append(message)
                else:
                    populated += 1
        summary.append(f"{series_id} {season}: {len(calendar)} rounds, {populated}/{completed} completed with results, {len(drivers)} drivers, {len(teams)} teams")
    if failures:
        raise AssertionError("\n".join(failures))
    print("\n".join(summary + [f"note: {note}" for note in notes]))


if __name__ == "__main__":
    main()
