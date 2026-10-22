"""Build uniform head-and-shoulders portraits from official championship photos.

Every series publishes studio portraits of its drivers. They are collected into
``data/sources/official_headshots.json`` and cropped with one consistent framing
into ``assets/portraits/faces/<series>/<driver-slug>.jpg``. A driver who races
in several series can use the official studio photo of another championship;
only exact name matches are accepted across series so identities never mix.

Usage:
    python scripts/official_headshots.py --collect   # refresh source URLs
    python scripts/official_headshots.py --build     # (re)crop every driver
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from html import unescape
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

import cv2
import numpy as np

from fetch_data import slugify
from portrait_identity import MANUAL_SOURCES, PORTRAIT_ALIASES

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "data" / "sources" / "official_headshots.json"
FACES = ROOT / "assets" / "portraits" / "faces"
MODEL = str(ROOT / "scripts" / "models" / "face_detection_yunet_2023mar.onnx")
SERIES = ("f1", "f2", "f3", "imsa", "indycar", "indynxt", "wec")
BROWSER = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,image/webp,image/png,image/jpeg,*/*;q=0.8",
}
BACKGROUND = (42, 36, 30)  # BGR #1E242A behind transparent studio cut-outs
OUTPUT = 320
# Square crop side relative to the detected face width and the vertical
# position of the face centre: identical framing for every driver.
FRAME = 2.55
FACE_CENTRE_Y = 0.45


def fetch(url: str, attempts: int = 4) -> bytes:
    for attempt in range(attempts):
        try:
            with urlopen(Request(url, headers=BROWSER), timeout=40) as response:
                return response.read()
        except Exception as error:
            if attempt == attempts - 1 or getattr(error, "code", None) == 404:
                raise
            # imsa.com rate-limits bursts with 403; back off progressively.
            time.sleep(3 * (attempt + 1))
    raise AssertionError


def text(url: str) -> str:
    return fetch(url).decode("utf-8", "replace")


def collect_f1() -> dict[str, str]:
    from fetch_data import official_f1_portraits

    return {key: url.replace("w_440", "w_1024") for key, url in official_f1_portraits().items()}


def collect_feeder(series: str) -> dict[str, str]:
    from fetch_feeder_data import official_portraits

    return {key: url.replace("w_406", "w_1024") for key, url in official_portraits(series).items()}


def collect_wec() -> dict[str, str]:
    base = "https://www.fiawec.com"
    season = text(f"{base}/en/season/2026")
    profiles = sorted(set(re.findall(r'href="(/en/driver/2026/\d+)"', season)))

    def one(profile: str) -> tuple[str, str] | None:
        page = text(base + profile)
        title = re.search(r"<title>\s*FIA WEC drivers - (.*?)\s*</title>", page, re.S)
        image = re.search(r'"(https://www\.fiawec\.com/uploads/2026-wec-[^"]+-right-[^"]+\.png)"', page)
        if not title or not image:
            return None
        return slugify(unescape(title.group(1))), image.group(1)

    with ThreadPoolExecutor(max_workers=8) as pool:
        return dict(item for item in pool.map(one, profiles) if item)


def collect_imsa() -> dict[str, str]:
    page = text("https://www.imsa.com/weathertech/drivers/")
    found = {}
    for url, name in re.findall(
        r'data-src="([^"]+_355x355[^"]*\.(?:png|jpe?g))"[^>]*alt="Photo of ([^"]+)"', page, re.I
    ):
        found[slugify(unescape(name))] = re.sub(r"-\d+x\d+(\.\w+)$", r"\1", url)
    return found


def collect_indy(domain: str, folder: str) -> dict[str, str]:
    base = f"https://www.{domain}.com"
    page = text(f"{base}/Drivers")
    found = {}
    for profile in sorted(set(re.findall(r'href="/Drivers/([^"/?]+)"', page))):
        match = re.search(
            rf'(?:src|data-src)="([^"]*/{folder}/Driver-List/{re.escape(profile.replace("-", ""))}\.(?:png|jpe?g))',
            page,
            re.I,
        )
        if match:
            found[slugify(profile.replace("-", " "))] = urljoin(base, match.group(1))
    return found


def collect_aco_driver(base: str, season: int, wanted: set[str]) -> dict[str, str]:
    """Official ACO studio portraits (WEC/ELMS/Asian LMS) of other seasons."""
    try:
        listing = text(f"{base}/en/season/{season}")
    except Exception:
        return {}
    found = {}
    for href, name in re.findall(r'href="(/en/driver/\d+/\d+)"[^>]*>([^<]+)<', listing):
        key = slugify(unescape(name))
        if key not in wanted or key in found:
            continue
        try:
            page = text(base + href)
        except Exception:
            continue
        family = key.split("-")[-1]
        images = [
            image
            for image in re.findall(r'"(https?://[^"]+/uploads/\d{4}-[a-z]+-[^"]+\.(?:png|jpe?g))"', page)
            if "/cache/" not in image and family in image.lower()
        ]
        if images:
            found[key] = images[0]
    return found


def camel(name: str) -> str:
    return "".join(part[:1].upper() + part[1:] for part in slugify(name).split("-"))


def collect_supplemental(missing: dict[str, str]) -> dict[str, str]:
    """Find official portraits for drivers absent from current roster pages.

    ``missing`` maps a driver slug to the series whose standings list them.
    """
    found: dict[str, str] = {}
    for slug, series in missing.items():
        if series in {"f2", "f3"}:
            number = series[1]
            try:
                page = text(f"https://www.fiaformula{number}.com/en/drivers/{slug}")
            except Exception:
                page = ""
            image = re.search(r'(https://res\.cloudinary\.com/[^"\s]+right[^"\s]*\.webp)', page)
            if image:
                found[slug] = re.sub(r"c_fill,w_\d+", "c_fill,w_1024", image.group(1))
    remaining = {slug for slug in missing if slug not in found}
    for base, season in (
        ("https://www.europeanlemansseries.com", 2026),
        ("https://www.fiawec.com", 2025),
        ("https://www.asianlemansseries.com", 2025),
    ):
        for slug, url in collect_aco_driver(base, season, remaining).items():
            found.setdefault(slug, url)
        remaining = {slug for slug in missing if slug not in found}
    for base in (
        "https://www.gt-world-challenge-europe.com",
        "https://www.gt-world-challenge-america.com",
    ):
        try:
            listing = text(f"{base}/drivers")
        except Exception:
            continue
        for number, profile in re.findall(r'href="/driver/(\d+)/([a-z0-9-]+)"', listing):
            if profile in remaining and profile not in found:
                for extension in ("png", "jpg"):
                    url = f"{base}/images/drivers/photo_{number}.{extension}"
                    try:
                        fetch(url, attempts=2)
                    except Exception:
                        continue
                    found[profile] = url
                    break
        remaining = {slug for slug in missing if slug not in found}
    templates = (
        "https://www.indycar.com/-/media/IndyCar/Drivers/IndyCar-Series/Driver-List/{}.png",
        "https://www.indycar.com/-/media/IndyCar/Drivers/IndyCar-Series/Headshot/{}.jpg",
        "https://indynxt-cdn.azureedge.net/-/media/IndyCar/Drivers/INDY-NXT/Driver-List/{}.jpg",
    )
    placeholders = set()
    for template in templates:
        # Unknown media items return a generic silhouette instead of a 404.
        try:
            placeholders.add(fetch(template.format("NoSuchDriverZzq"), attempts=1))
        except Exception:
            pass
    for slug in sorted(remaining):
        name = camel(slug.replace("-", " "))
        for template in templates:
            url = template.format(name)
            try:
                content = fetch(url, attempts=1)
            except Exception:
                continue
            if content in placeholders:
                continue
            found[slug] = url
            break
    return found


def collect() -> dict[str, dict[str, str]]:
    collectors = {
        "f1": collect_f1,
        "f2": lambda: collect_feeder("f2"),
        "f3": lambda: collect_feeder("f3"),
        "imsa": collect_imsa,
        "indycar": lambda: collect_indy("indycar", "IndyCar-Series"),
        "indynxt": lambda: collect_indy("indynxt", "INDY-NXT"),
        "wec": collect_wec,
    }
    previous = json.loads(SOURCES.read_text(encoding="utf-8")) if SOURCES.is_file() else {}
    result = {}
    for series, collector in collectors.items():
        try:
            found = collector()
        except Exception as error:  # keep the last verified list on outages
            print(f"{series}: collection failed ({error}); keeping previous", file=sys.stderr)
            found = previous.get(series, {})
        if not found:
            found = previous.get(series, {})
        result[series] = dict(sorted(found.items()))
        print(f"{series}: {len(found)} official portraits")
    missing = {}
    for series, names in standings_drivers().items():
        for name in names:
            if pick_source(series, name, result) is None:
                missing.setdefault(slugify(name), series)
    extra = collect_supplemental(missing)
    # Last resort: identity-verified official images curated earlier.
    legacy_path = ROOT / "data" / "sources" / "official_driver_portraits.json"
    if legacy_path.is_file():
        legacy = json.loads(legacy_path.read_text(encoding="utf-8"))
        for name, url in legacy.items():
            if slugify(name) in missing:
                extra.setdefault(slugify(name), url)
    extra.update(MANUAL_SOURCES)
    result["other"] = dict(sorted(extra.items()))
    print(f"other official sources: {len(extra)} of {len(missing)} missing drivers")
    SOURCES.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def standings_drivers() -> dict[str, set[str]]:
    drivers: dict[str, set[str]] = {series: set() for series in SERIES}
    for root in (ROOT / "assets" / "data", ROOT / "data"):
        for series in SERIES:
            for path in sorted((root / series).glob("*/standings_drivers.json")):
                for driver in json.loads(path.read_text(encoding="utf-8"))["data"]:
                    name = f"{driver.get('givenName', '')} {driver.get('familyName', '')}".strip()
                    drivers[series].add(name)
    return drivers


def pick_source(series: str, name: str, sources: dict[str, dict[str, str]]) -> tuple[str, str] | None:
    slug = slugify(name)
    keys = [slug] + ([PORTRAIT_ALIASES[slug]] if slug in PORTRAIT_ALIASES else [])
    order = [series] + [other for other in SERIES if other != series] + ["other"]
    for source_series in order:
        # Hyphen-insensitive keys cover "Pato O'Ward" vs "Pato OWard".
        available = {key.replace("-", ""): url for key, url in sources.get(source_series, {}).items()}
        for key in keys:
            if key.replace("-", "") in available:
                return source_series, available[key.replace("-", "")]
    # Within the driver's own series a unique family-name match is safe
    # (e.g. "Kimi Antonelli" on formula1.com vs "Andrea Kimi Antonelli").
    family = slug.split("-")[-1]
    own = [url for key, url in sources.get(series, {}).items() if key.split("-")[-1] == family]
    if len(own) == 1:
        return series, own[0]
    return None


def decode(raw: bytes) -> np.ndarray | None:
    image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_UNCHANGED)
    if image is None:
        return None
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.shape[2] == 4:
        alpha = image[:, :, 3:4].astype(np.float32) / 255.0
        backdrop = np.empty_like(image[:, :, :3])
        backdrop[:] = BACKGROUND
        image = (image[:, :, :3] * alpha + backdrop * (1 - alpha)).astype(np.uint8)
    return image


def detect(image: np.ndarray):
    height, width = image.shape[:2]
    detector = cv2.FaceDetectorYN.create(MODEL, "", (width, height), 0.6, 0.3, 5000)
    _, faces = detector.detect(image)
    if faces is None or len(faces) == 0:
        return None
    return max(faces, key=lambda face: float(face[14]) * face[2] * face[3])


def headshot(image: np.ndarray) -> tuple[np.ndarray, float] | None:
    """Return the uniform crop and the yaw ratio (0 = facing the camera)."""
    face = detect(image)
    if face is None:
        return None
    height, width = image.shape[:2]
    x, y, w, h = (float(value) for value in face[:4])
    eye_mid = (face[4] + face[6]) / 2
    eye_distance = max(1.0, abs(face[6] - face[4]))
    yaw = float((face[8] - eye_mid) / eye_distance)
    size = int(round(w * FRAME))
    cx, cy = x + w / 2, y + h / 2
    left = int(round(cx - size / 2))
    top = int(round(cy - size * FACE_CENTRE_Y))
    # Studio photos often start just above the hair: pad with the photo's
    # own backdrop colour rather than shifting the face off-centre.
    border = np.concatenate([image[0, :], image[:, 0], image[:, -1]])
    fill = tuple(int(v) for v in np.median(border, axis=0))
    pad = max(0, -left, -top, left + size - width, top + size - height)
    if pad:
        image = cv2.copyMakeBorder(image, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=fill)
        left += pad
        top += pad
    crop = image[top : top + size, left : left + size]
    interpolation = cv2.INTER_AREA if size > OUTPUT else cv2.INTER_CUBIC
    return cv2.resize(crop, (OUTPUT, OUTPUT), interpolation=interpolation), yaw


def build(only: set[str] | None = None) -> None:
    sources = json.loads(SOURCES.read_text(encoding="utf-8"))
    drivers = standings_drivers()
    jobs = []
    missing = []
    for series, names in drivers.items():
        for name in sorted(names):
            slug = slugify(name)
            if only and slug not in only:
                continue
            chosen = pick_source(series, name, sources)
            if chosen is None:
                missing.append(f"{series}/{name}")
                continue
            jobs.append((series, name, slug, chosen))
    cache: dict[str, bytes | None] = {}

    def download(url: str) -> tuple[str, bytes | None]:
        try:
            if url.startswith("assets/"):
                return url, (ROOT / url).read_bytes()
            return url, fetch(url)
        except Exception as error:
            print(f"download failed {url}: {error}", file=sys.stderr)
            return url, None

    with ThreadPoolExecutor(max_workers=3) as pool:
        cache.update(pool.map(download, sorted({job[3][1] for job in jobs})))
    report = {"built": [], "failed": [], "profile": [], "missing": missing}
    for series, name, slug, (source_series, url) in jobs:
        raw = cache.get(url)
        image = decode(raw) if raw else None
        result = headshot(image) if image is not None else None
        if result is None:
            report["failed"].append(f"{series}/{name} <- {source_series}")
            continue
        crop, yaw = result
        folder = FACES / series
        folder.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(folder / f"{slug}.jpg"), crop, [cv2.IMWRITE_JPEG_QUALITY, 92])
        report["built"].append(f"{series}/{slug} <- {source_series}")
        if abs(yaw) > 0.3:
            report["profile"].append(f"{series}/{name} yaw={yaw:.2f}")
    for key in ("failed", "profile", "missing"):
        print(f"{key}: {len(report[key])}")
        for item in report[key]:
            print(f"  {item}")
    print(f"built: {len(report['built'])}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--collect", action="store_true")
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--only", nargs="*", help="Driver slugs to rebuild")
    args = parser.parse_args()
    if args.collect:
        collect()
    if args.build:
        build(set(args.only) if args.only else None)


if __name__ == "__main__":
    main()
