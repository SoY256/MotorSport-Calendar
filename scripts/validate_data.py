"""Fail fast when bundled motorsport data is incomplete or references missing assets."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "assets" / "data"
PUBLISHED_DATA = ROOT / "data"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    now = datetime.now(timezone.utc)
    manifest = load(DATA / "manifest.json")
    ids = [item["id"] for item in manifest["availableSeries"]]
    if len(ids) != len(set(ids)) or not {"f1", "f2", "f3", "imsa", "indycar", "indynxt", "wec"}.issubset(ids):
        raise AssertionError(f"Incomplete or duplicate series manifest: {ids}")

    dart = (ROOT / "lib" / "features" / "calendar" / "domain" / "circuit_metadata.dart").read_text(encoding="utf-8")
    mapped = set(re.findall(r"'([^']+)'\s*(?:\|\||=>)", dart))
    failures = []
    summary = []
    for series_id in ids:
        root = DATA / series_id / "2026"
        calendar = load(root / "calendar.json")["data"]
        drivers = load(root / "standings_drivers.json")["data"]
        teams = load(root / "standings_teams.json")["data"]
        if not calendar or not drivers or not teams:
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
        ]
        if missing_portraits:
            failures.append(
                f"{series_id}: missing driver portraits for {', '.join(missing_portraits)}"
            )
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
            if event["circuit"]["name"] not in mapped:
                failures.append(f"{series_id} R{event['round']}: no circuit asset mapping for {event['circuit']['name']}")
            result_path = root / event["resultsPath"]
            if not result_path.exists():
                failures.append(f"{series_id} R{event['round']}: missing {event['resultsPath']}")
                continue
            sessions = load(result_path)["data"]["sessions"]
            published_path = PUBLISHED_DATA / series_id / "2026" / event["resultsPath"]
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
                    failures.append(f"{series_id} R{event['round']}: completed event has no results")
                else:
                    populated += 1
        summary.append(f"{series_id}: {len(calendar)} rounds, {populated}/{completed} completed with results, {len(drivers)} drivers, {len(teams)} teams")
    if failures:
        raise AssertionError("\n".join(failures))
    print("\n".join(summary))


if __name__ == "__main__":
    main()
