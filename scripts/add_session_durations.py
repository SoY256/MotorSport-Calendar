"""Add expected session durations used by the app's result polling scheduler."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def race_duration(series: str, event_name: str) -> int:
    name = event_name.casefold()
    if series == "wec":
        if "24 hours" in name:
            return 24 * 60
        if "8 hours" in name:
            return 8 * 60
        if "qatar 1812" in name:
            return 10 * 60
        return 6 * 60
    if series == "imsa":
        if "rolex 24" in name:
            return 24 * 60
        if "twelve hours" in name:
            return 12 * 60
        if "petit le mans" in name:
            return 10 * 60
        if "six hours" in name or "battle on the bricks" in name:
            return 6 * 60
        if "long beach" in name or "detroit" in name:
            return 100
        return 160
    if series == "indycar":
        return 240 if "indianapolis 500" in name else 150
    if series == "indynxt":
        return 60
    return 120


def duration(series: str, event_name: str, session_type: str, session_name: str) -> int:
    kind = session_type.upper()
    label = session_name.casefold()
    if kind.startswith("FP") or "practice" in label:
        return 60 if series == "f1" else 45
    if kind in {"SQ", "SPRINT_SHOOTOUT"} or "shootout" in label:
        return 45
    if kind == "Q" or "qualifying" in label or "hyperpole" in label:
        return 60 if series == "f1" else 30
    if kind in {"SPRINT", "SR"} or "sprint" in label:
        return 60 if series in {"f1", "f2"} else 45
    return race_duration(series, event_name)


def main(root: Path) -> None:
    for calendar_path in root.glob("*/2026/calendar.json"):
        series = calendar_path.parent.parent.name
        document = json.loads(calendar_path.read_text(encoding="utf-8"))
        for event in document["data"]:
            for session in event["sessions"]:
                session["durationMinutes"] = duration(
                    series, event["name"], session["type"], session["name"]
                )
        calendar_path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "assets/data"))
