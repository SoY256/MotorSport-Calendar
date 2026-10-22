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
import re
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher
from pathlib import Path

import cv2

from fetch_gt3_results import FACES, SERIES, driver_profile
from official_headshots import collect_aco_driver, decode, fetch, headshot, text

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = 240  # GT3 grids are large; avatars are shown at <= 64 logical px.
OTHER_FACES = ROOT / "assets" / "portraits" / "faces"


NAMES: dict[str, str] = {}


def drivers(data_root: Path) -> dict[str, str]:
    """Driver slug -> official portrait URL (may be empty)."""
    found: dict[str, str] = {}
    for series in SERIES:
        for path in sorted((data_root / series).glob("*/standings_drivers.json")):
            for driver in json.loads(path.read_text(encoding="utf-8"))["data"]:
                NAMES[driver["id"]] = f"{driver.get('givenName', '')} {driver.get('familyName', '')}".strip()
                if driver.get("portraitSource") or driver["id"] not in found:
                    found[driver["id"]] = driver.get("portraitSource") or found.get(driver["id"], "")
    return found


def spelling_variant(slug: str, faces: dict[str, Path]) -> Path | None:
    """A verified crop filed under a one-letter spelling variant of the name,
    e.g. "fabien-schiller" / "fabian-schiller" or "ricardo-pera" /
    "riccardo-pera" (official result sheets spell some names differently)."""
    given, _, family = slug.partition("-")
    matches = []
    for other, path in faces.items():
        other_given, _, other_family = other.partition("-")
        if other == slug or not family or not other_family:
            continue
        same_family = family == other_family
        same_given = given == other_given
        if (same_family and SequenceMatcher(None, given, other_given).ratio() >= 0.8) or (
            same_given and SequenceMatcher(None, family, other_family).ratio() >= 0.85
        ):
            matches.append(path)
    return matches[0] if len(matches) == 1 else None


SRO_SITES = (
    "https://www.gt-world-challenge-europe.com",
    "https://www.gt-world-challenge-america.com",
    "https://www.gt-world-challenge-asia.com",
    "https://www.gt-world-challenge-australia.com",
    "https://www.britishgt.com",
    "https://www.intercontinentalgtchallenge.com",
)
ACO_SITES = (
    ("https://www.europeanlemansseries.com", 2026),
    ("https://www.europeanlemansseries.com", 2025),
    ("https://www.asianlemansseries.com", 2026),
    ("https://www.asianlemansseries.com", 2025),
    ("https://www.fiawec.com", 2025),
)


def other_sources(missing: set[str]) -> dict[str, list[str]]:
    """Official studio portraits of the same drivers on other championships'
    sites: their profile on another SRO series, then ELMS / Asian Le Mans /
    WEC (ACO) profiles."""
    found: dict[str, list[str]] = {}

    def profiles(base: str) -> list[tuple[str, str]]:
        try:
            listing = text(f"{base}/drivers")
        except Exception:  # noqa: BLE001
            return []
        return [
            (base, path) for path, slug in set(re.findall(r'href="(/driver/\d+/([a-z0-9-]+))"', listing))
            if slug in missing
        ]

    with ThreadPoolExecutor(max_workers=6) as pool:
        pages = [item for batch in pool.map(profiles, SRO_SITES) for item in batch]

        def portrait(item: tuple[str, str]) -> tuple[str, str]:
            base, path = item
            try:
                return path.rsplit("/", 1)[1], driver_profile(base, path)["portraitSource"]
            except Exception:  # noqa: BLE001
                return path.rsplit("/", 1)[1], ""

        for slug, url in pool.map(portrait, pages):
            if url:
                found.setdefault(slug, []).append(url)
    for base, season in ACO_SITES:
        for slug, url in collect_aco_driver(base, season, missing).items():
            found.setdefault(slug, []).append(url)
    return found


WIKI_SOURCES = ROOT / "data" / "sources" / "gt3_wikimedia_portraits.json"
# Reviewed by eye and rejected: the face is covered or not recognisable.
REJECTED = {
    "frank-stippler": "helmet",
    "pierre-louis-chovet": "face mask",
}
MIN_SHARPNESS = 50  # Laplacian variance; tiny upscaled photos are blurry


def sharp(crop) -> bool:
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var() >= MIN_SHARPNESS


def wikipedia_faces(slugs: list[str], target: Path) -> int:
    """Last resort: the lead image of the driver's Wikipedia article, only when
    the article title is exactly the driver's name and describes a racing
    driver, and a single clear face is detected. Sources are recorded for
    attribution (Wikimedia Commons licences)."""
    from fetch_wikipedia_portraits import portrait

    register = json.loads(WIKI_SOURCES.read_text(encoding="utf-8")) if WIKI_SOURCES.is_file() else {}
    built = 0
    for slug in slugs:
        name = NAMES.get(slug, "")
        if len(name.split()) < 2:
            continue
        try:
            url = portrait(name)
            raw = fetch(url, attempts=2) if url else None
        except Exception as error:  # noqa: BLE001
            print(f"wikipedia {name}: {error}", file=sys.stderr)
            continue
        image = decode(raw) if raw else None
        result = headshot(image) if image is not None else None
        if result is None or abs(result[1]) > 0.35 or slug in REJECTED:
            continue
        crop = cv2.resize(result[0], (OUTPUT, OUTPUT), interpolation=cv2.INTER_AREA)
        if not sharp(crop):
            continue
        cv2.imwrite(str(target / f"{slug}.jpg"), crop, [cv2.IMWRITE_JPEG_QUALITY, 88])
        register[slug] = {"name": name, "source": url}
        built += 1
    WIKI_SOURCES.write_text(json.dumps(dict(sorted(register.items())), ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
    return built


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

    missing = sorted(
        slug for slug in wanted
        if not (target / f"{slug}.jpg").is_file() or args.rebuild
    )
    candidates: dict[str, list[str]] = {slug: [jobs[slug]] if slug in jobs else [] for slug in missing}
    for slug, url in other_sources(set(missing)).items():
        candidates.setdefault(slug, []).extend(url)

    urls = sorted({url for options in candidates.values() for url in options})

    def download(url: str) -> tuple[str, bytes | None]:
        try:
            return url, fetch(url, attempts=2)
        except Exception as error:  # noqa: BLE001 - a missing photo falls back to initials
            print(f"download failed {url}: {error}", file=sys.stderr)
            return url, None

    with ThreadPoolExecutor(max_workers=6) as pool:
        downloaded = dict(pool.map(download, urls))
    # The same image offered for several drivers is a site's silhouette.
    owners: dict[str, set[str]] = {}
    for slug, options in candidates.items():
        for url in options:
            raw = downloaded.get(url)
            if raw:
                owners.setdefault(hashlib.sha1(raw).hexdigest(), set()).add(slug)
    built, skipped = 0, []
    for slug in missing:
        reason = "no official portrait"
        for url in candidates.get(slug, []):
            raw = downloaded.get(url)
            if not raw or len(owners[hashlib.sha1(raw).hexdigest()]) > 1:
                reason = "placeholder only"
                continue
            image = decode(raw)
            result = headshot(image) if image is not None else None
            if result is None:
                reason = "no face detected"
                continue
            crop = cv2.resize(result[0], (OUTPUT, OUTPUT), interpolation=cv2.INTER_AREA)
            cv2.imwrite(str(target / f"{slug}.jpg"), crop, [cv2.IMWRITE_JPEG_QUALITY, 88])
            built += 1
            break
        else:
            skipped.append(f"{slug} ({reason})")
    faces = {path.stem: path for path in sorted(OTHER_FACES.glob("*/*.jpg"))}
    variants = 0
    for slug in missing:
        output = target / f"{slug}.jpg"
        source = None if output.is_file() else spelling_variant(slug, faces)
        if source is not None:
            image = cv2.imread(str(source))
            cv2.imwrite(str(output), cv2.resize(image, (OUTPUT, OUTPUT), interpolation=cv2.INTER_AREA),
                        [cv2.IMWRITE_JPEG_QUALITY, 88])
            variants += 1
    wiki = wikipedia_faces([slug for slug in missing if not (target / f"{slug}.jpg").is_file()], target)
    print(f"GT3 faces: {variants} from name variants, {wiki} from Wikimedia Commons")
    without = sorted(slug for slug in wanted if not (target / f"{slug}.jpg").is_file())
    print(f"GT3 faces: {reused} reused, {built} built, {len(skipped)} skipped, {len(without)} without photo")
    for item in skipped:
        print(f"  skipped {item}")


if __name__ == "__main__":
    shutil.os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    main()
