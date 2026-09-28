"""Report standings identities without a matching bundled face crop."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from fetch_data import slugify

ROOT = Path(__file__).resolve().parents[1]


def audit(series: str) -> None:
    path = ROOT / "assets" / "data" / series / "2026" / "standings_drivers.json"
    drivers = json.loads(path.read_text(encoding="utf-8"))["data"]
    identities = {
        f"{driver.get('givenName', '')} {driver.get('familyName', '')}".strip(): slugify(
            f"{driver.get('givenName', '')} {driver.get('familyName', '')}".strip()
        )
        for driver in drivers
    }
    face_root = ROOT / "assets" / "portraits" / "faces" / series
    faces = {item.stem for item in face_root.glob("*") if item.is_file()}
    missing = [(name, slug) for name, slug in identities.items() if slug not in faces]
    orphaned = sorted(faces - set(identities.values()))
    print(
        f"{series}: {len(identities)} identities, {len(faces)} face files, "
        f"{len(missing)} missing"
    )
    for name, slug in missing:
        print(f"  MISSING {name} -> {slug}")
    for slug in orphaned:
        print(f"  ORPHAN {slug}")


if __name__ == "__main__":
    for selected in sys.argv[1:] or ["imsa", "wec"]:
        audit(selected)
