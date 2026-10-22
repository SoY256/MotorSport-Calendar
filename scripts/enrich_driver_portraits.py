"""Link standings to the verified local face crops (never remote full-body art).

Face crops are produced by ``official_headshots.py`` and stored in
``assets/portraits/faces/<series>/<driver-slug>.jpg``. A driver without a
verified crop deliberately gets no ``imageUrl`` so the app shows initials
instead of a wrong or non-face image.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from fetch_data import slugify
from portrait_identity import PORTRAIT_ALIASES

ROOT = Path(__file__).resolve().parents[1]
FACES = ROOT / "assets" / "portraits" / "faces"


def local_face(series: str, driver: dict) -> str | None:
    slugs = [slugify(f"{driver.get('givenName', '')} {driver.get('familyName', '')}")]
    slugs.append(slugify(driver.get("id", "")))
    slugs += [PORTRAIT_ALIASES[slug] for slug in list(slugs) if slug in PORTRAIT_ALIASES]
    # The same driver often races in several series; the exact name is an
    # identity-safe key, so a crop from another series is accepted.
    folders = [FACES / series] + sorted(
        folder for folder in FACES.iterdir() if folder.is_dir() and folder.name != series
    )
    for slug in dict.fromkeys(slug for slug in slugs if slug):
        for folder in folders:
            path = folder / f"{slug}.jpg"
            if path.is_file():
                return path.relative_to(ROOT).as_posix()
    return None


def enrich(root: Path, series: str) -> int:
    matched = 0
    for path in sorted((root / series).glob("*/standings_drivers.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        for driver in document["data"]:
            image = local_face(series, driver)
            if image:
                driver["imageUrl"] = image
                matched += 1
            else:
                driver.pop("imageUrl", None)
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return matched


def main() -> None:
    configured = os.environ.get("PORTRAIT_SINGLE_ROOT")
    roots = (Path(configured),) if configured else (ROOT / "assets" / "data", ROOT / "data")
    for root in roots:
        for series in ("f1", "f2", "f3", "imsa", "indycar", "indynxt", "wec"):
            matched = enrich(root, series)
            print(f"{root.name}/{series}: {matched} face portraits")


if __name__ == "__main__":
    main()
