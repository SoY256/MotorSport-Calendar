"""Give upcoming rounds the series' best known lap at their circuit.

Importers record the fastest race lap of each meeting once its official
classification exists ("1:46.396 • Driver (2026)"). Rounds without one yet
(future meetings, next-season calendars) show the fastest lap the same
series set at the same circuit in an earlier meeting; the year in the text
keeps its origin visible.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

LAP = re.compile(r"^(?:(\d+):)?(\d+(?:\.\d+)?)\s")


def lap_seconds(record: str) -> float | None:
    match = LAP.match(record)
    if not match:
        return None
    return int(match.group(1) or 0) * 60 + float(match.group(2))


def start(event: dict) -> str:
    return min((session["startTimeUtc"] for session in event.get("sessions", [])), default="")


def carry(data_root: Path, now: str | None = None) -> int:
    now = now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    seeds_path = data_root / "sources" / "earlier_lap_records.json"
    seeds = json.loads(seeds_path.read_text(encoding="utf-8"))["records"] if seeds_path.is_file() else {}
    changed = 0
    for series_dir in sorted(path for path in data_root.iterdir() if path.is_dir()):
        calendars = sorted(series_dir.glob("*/calendar.json"))
        documents = {path: json.loads(path.read_text(encoding="utf-8")) for path in calendars}
        events = [
            (path, event)
            for path, document in documents.items()
            for event in document.get("data", [])
            if not event.get("cancelled")
        ]
        events.sort(key=lambda item: start(item[1]))
        best: dict[str, tuple[float, str]] = {}
        for key, seed in seeds.get(series_dir.name, {}).items():
            value = lap_seconds(seed["lapRecord"])
            if value is not None:
                best[key] = (value, seed["lapRecord"])
        dirty: set[Path] = set()
        for path, event in events:
            circuit = event["circuit"]
            key = circuit.get("id") or circuit["name"]
            own = circuit.get("lapRecord")
            # A meeting that has started keeps the record its importer wrote;
            # rounds still to come always show the best earlier lap.
            if own and start(event) <= now:
                value = lap_seconds(own)
                if value is not None and (key not in best or value < best[key][0]):
                    best[key] = (value, own)
                continue
            carried = best.get(key, (None, None))[1]
            if carried != own:
                if carried:
                    circuit["lapRecord"] = carried
                else:
                    circuit.pop("lapRecord", None)
                dirty.add(path)
        for path in dirty:
            path.write_text(json.dumps(documents[path], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            changed += 1
    return changed


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parents[1] / "data"
    print(f"lap records carried forward: {carry(root)} calendars updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
