"""Build bundled face crops for GT3 drivers.

Sources, in order of preference:

1. an identity-verified crop already bundled for another series (many GT3
   drivers also race in WEC or IMSA);
2. the official SRO studio portrait linked from the driver's profile page
   (``portraitSource`` in the GT3 driver standings), cropped with the same
   face detector and framing as every other series.

Images shared by several drivers (generic silhouettes) and images without a
detectable face are skipped: the app shows initials instead.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2

from fetch_gt3_results import FACES, SERIES, SEASON
from official_headshots import decode, fetch, headshot

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = 240  # GT3 grids are large; avatars are shown at <= 64 logical px.
OTHER_FACES = ROOT / "assets" / "portraits" / "faces"


def drivers(data_root: Path) -> dict[str, str]:
    """Driver slug -> official portrait URL (may be empty)."""
    found: dict[str, str] = {}
    for series in SERIES:
        path = data_root / series / str(SEASON) / "standings_drivers.json"
        if not path.is_file():
            continue
        for driver in json.loads(path.read_text(encoding="utf-8"))["data"]:
            if driver.get("portraitSource") or driver["id"] not in found:
                found[driver["id"]] = driver.get("portraitSource") or found.get(driver["id"], "")
    return found


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=Path(os.environ.get("MOTORSPORT_DATA_ROOT", ROOT / "data")))
    parser.add_argument("--rebuild", action="store_true", help="Replace existing GT3 crops")
    args = parser.parse_args()
    target = ROOT / FACES
    target.mkdir(parents=True, exist_ok=True)
    wanted = drivers(args.data_root)
    # Official portraits already collected for other series (F1, WEC, ELMS,
    # IMSA, GT World Challenge rosters...) by scripts/official_headshots.py.
    index_path = ROOT / "data" / "sources" / "official_headshots.json"
    official: dict[str, str] = {}
    if index_path.is_file():
        for sources in json.loads(index_path.read_text(encoding="utf-8")).values():
            for slug, url in sources.items():
                if not url.startswith("assets/"):
                    official.setdefault(slug, url)
    reused, jobs = 0, {}
    for slug, url in sorted(wanted.items()):
        url = url or official.get(slug, "")
        output = target / f"{slug}.jpg"
        if output.is_file() and not args.rebuild:
            continue
        verified = next(
            (path for path in sorted(OTHER_FACES.glob(f"*/{slug}.jpg")) if path.parent.name != "gt3"),
            None,
        )
        if verified:
            image = cv2.imread(str(verified))
            cv2.imwrite(str(output), cv2.resize(image, (OUTPUT, OUTPUT), interpolation=cv2.INTER_AREA),
                        [cv2.IMWRITE_JPEG_QUALITY, 88])
            reused += 1
        elif url:
            jobs[slug] = url

    def download(item: tuple[str, str]) -> tuple[str, bytes | None]:
        slug, url = item
        try:
            return slug, fetch(url, attempts=2)
        except Exception as error:  # noqa: BLE001 - a missing photo falls back to initials
            print(f"download failed {slug}: {error}", file=sys.stderr)
            return slug, None

    with ThreadPoolExecutor(max_workers=6) as pool:
        downloaded = dict(pool.map(download, jobs.items()))
    digests: dict[str, int] = {}
    for raw in downloaded.values():
        if raw:
            digest = hashlib.sha1(raw).hexdigest()
            digests[digest] = digests.get(digest, 0) + 1
    built, skipped = 0, []
    for slug, raw in sorted(downloaded.items()):
        if not raw or digests[hashlib.sha1(raw).hexdigest()] > 1:
            skipped.append(f"{slug} (missing or shared placeholder)")
            continue
        image = decode(raw)
        result = headshot(image) if image is not None else None
        if result is None:
            skipped.append(f"{slug} (no face detected)")
            continue
        crop, _yaw = result
        crop = cv2.resize(crop, (OUTPUT, OUTPUT), interpolation=cv2.INTER_AREA)
        cv2.imwrite(str(target / f"{slug}.jpg"), crop, [cv2.IMWRITE_JPEG_QUALITY, 88])
        built += 1
    without = sorted(slug for slug in wanted if not (target / f"{slug}.jpg").is_file())
    print(f"GT3 faces: {reused} reused, {built} built, {len(skipped)} skipped, {len(without)} without photo")
    for item in skipped:
        print(f"  skipped {item}")


if __name__ == "__main__":
    shutil.os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    main()
