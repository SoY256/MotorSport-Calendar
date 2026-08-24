"""Fail fast when bundled motorsport data is incomplete or references missing assets."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "assets" / "data"


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
        completed = populated = 0
        for event in calendar:
            if event["circuit"]["name"] not in mapped:
                failures.append(f"{series_id} R{event['round']}: no circuit asset mapping for {event['circuit']['name']}")
            result_path = root / event["resultsPath"]
            if not result_path.exists():
                failures.append(f"{series_id} R{event['round']}: missing {event['resultsPath']}")
                continue
            sessions = load(result_path)["data"]["sessions"]
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
