"""Audit published data for temporal result errors and missing driver metadata."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "data"
SERIES = ("f1", "f2", "f3", "wec", "imsa", "indycar", "indynxt")


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))["data"]


def main() -> int:
    now = datetime.now(timezone.utc)
    failures: list[str] = []
    print(f"Audit time: {now.isoformat()}")
    for series in SERIES:
        root = ROOT / series / "2026"
        drivers = load(root / "standings_drivers.json")
        missing_portraits = [
            f"{driver.get('givenName', '')} {driver.get('familyName', '')}".strip()
            for driver in drivers
            if not driver.get("imageUrl")
        ]
        missing_flags = [
            f"{driver.get('givenName', '')} {driver.get('familyName', '')}".strip()
            for driver in drivers
            if not driver.get("nationality")
        ]
        future_results: list[str] = []
        overdue_results: list[str] = []
        for event in load(root / "calendar.json"):
            results = load(root / event["resultsPath"])
            available = {
                session["type"]: session.get("results", [])
                for session in results.get("sessions", [])
            }
            for session in event.get("sessions", []):
                if session.get("cancelled"):
                    continue
                start = datetime.fromisoformat(
                    session["startTimeUtc"].replace("Z", "+00:00")
                )
                due = start + timedelta(
                    minutes=int(session.get("durationMinutes", 120)) + 5
                )
                rows = available.get(session["type"], [])
                label = f"{event['name']}/{session['type']}"
                if start > now and rows:
                    future_results.append(label)
                expected = series in {"f1", "f2", "f3"} or session["type"] == "R"
                if expected and due <= now and not rows:
                    overdue_results.append(label)
        print(
            f"{series}: drivers={len(drivers)}, portraits={missing_portraits}, "
            f"flags={missing_flags}, future={future_results}, overdue={overdue_results}"
        )
        if missing_flags or future_results or overdue_results:
            failures.append(series)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
