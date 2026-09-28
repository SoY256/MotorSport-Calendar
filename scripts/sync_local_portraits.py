"""Bind standings identities to existing, verified local face crops."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from fetch_data import slugify

ROOT = Path(__file__).resolve().parents[1]


def local_face(series: str, slug: str) -> str | None:
    preferred = ROOT / "assets" / "portraits" / "faces" / series
    roots = [preferred, *(ROOT / "assets" / "portraits" / "faces").glob("*")]
    for root in roots:
        for suffix in ("jpg", "jpeg", "png", "webp"):
            candidate = root / f"{slug}.{suffix}"
            if candidate.is_file():
                return candidate.relative_to(ROOT).as_posix()
    return None


def sync(series: str) -> None:
    for data_root in (ROOT / "assets" / "data", ROOT / "data"):
        path = data_root / series / "2026" / "standings_drivers.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        matched = 0
        for driver in document["data"]:
            name = f"{driver.get('givenName', '')} {driver.get('familyName', '')}".strip()
            portrait = local_face(series, slugify(name))
            if portrait:
                driver["imageUrl"] = portrait
                matched += 1
            else:
                driver.pop("imageUrl", None)
        path.write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"{data_root.name}/{series}: {matched}/{len(document['data'])} rows")


if __name__ == "__main__":
    for selected in sys.argv[1:] or ["imsa", "wec"]:
        sync(selected)
