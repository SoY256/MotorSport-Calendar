"""Remove repeated official IMSA points links and renumber each class."""

from __future__ import annotations

import json
from pathlib import Path

from fetch_imsa_results import deduplicate_standings

ROOT = Path(__file__).resolve().parents[1]


def repair(path: Path, kind: str) -> None:
    document = json.loads(path.read_text(encoding="utf-8"))
    rows = deduplicate_standings(document["data"], kind)
    rows.sort(key=lambda item: (item.get("category", ""), -float(item.get("points", 0))))
    positions: dict[str, int] = {}
    for row in rows:
        category = row.get("category", "").replace("GTDPRO", "GTD PRO")
        row["category"] = category
        positions[category] = positions.get(category, 0) + 1
        row["position"] = positions[category]
    document["data"] = rows
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{path}: {len(rows)} rows {positions}")


if __name__ == "__main__":
    for root in (ROOT / "data", ROOT / "assets" / "data"):
        repair(root / "imsa" / "2026" / "standings_drivers.json", "drivers")
        repair(root / "imsa" / "2026" / "standings_teams.json", "teams")
