"""Create verified local face crops; fall back to initials when no face is found."""

from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

import cv2
import numpy as np

from fetch_data import slugify

ROOT = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HEADERS = {"User-Agent": "MotorSport-Calendar/0.1 (+https://github.com/SoY256/MotorSport-Calendar)"}
MODEL = str(ROOT / "scripts" / "models" / "face_detection_yunet_2023mar.onnx")
def stored_sources(name: str) -> dict[str, str]:
    path = ROOT / "data" / "sources" / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


WIKI = stored_sources("wikipedia_driver_portraits.json")
IMSA = stored_sources("imsa_driver_portraits.json")
OFFICIAL = stored_sources("official_driver_portraits.json")


def mapped_source(mapping: dict[str, str], name: str) -> str | None:
    normalized = " ".join(name.split()).casefold()
    return next(
        (value for key, value in mapping.items() if " ".join(key.split()).casefold() == normalized),
        None,
    )


def original_source(series: str, driver: dict) -> str | None:
    name = f"{driver['givenName']} {driver['familyName']}"
    slug = slugify(name)
    verified_face = {
        "christian-rasmussen": "assets/portraits/faces/indycar/christian-rasmussen.jpg",
        "james-roe": "assets/portraits/faces/indynxt/james-roe.jpg",
    }.get(slug)
    if verified_face and (ROOT / verified_face).exists():
        return verified_face
    for mapping in (IMSA, OFFICIAL, WIKI):
        source = mapped_source(mapping, name)
        if source:
            return source
    for suffix in ("jpg", "png"):
        local = ROOT / "assets" / "portraits" / series / f"{slug}.{suffix}"
        if local.exists():
            return local.relative_to(ROOT).as_posix()
    for suffix in ("jpg", "png"):
        matches = list((ROOT / "assets" / "portraits").glob(f"*/{slug}.{suffix}"))
        if matches:
            return matches[0].relative_to(ROOT).as_posix()
    # Only reuse an old crop after checking current verified sources. This
    # prevents a previously bad crop (car, torso, or background) from
    # permanently shadowing a corrected official portrait URL.
    for suffix in ("jpg", "png"):
        local_face = ROOT / "assets" / "portraits" / "faces" / series / f"{slug}.{suffix}"
        if local_face.exists():
            return local_face.relative_to(ROOT).as_posix()
        matches = list((ROOT / "assets" / "portraits" / "faces").glob(f"*/{slug}.{suffix}"))
        if matches:
            return matches[0].relative_to(ROOT).as_posix()
    current = driver.get("imageUrl")
    return current if current and "/faces/" not in current else None


def read_image(value: str) -> np.ndarray | None:
    try:
        if value.startswith("assets/"):
            raw = (ROOT / value).read_bytes()
        else:
            for attempt in range(3):
                try:
                    with urlopen(Request(value, headers=HEADERS), timeout=10) as response:
                        raw = response.read()
                    break
                except Exception:
                    if attempt == 2:
                        raise
                    time.sleep(1.5 * (attempt + 1))
        return cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    except Exception:
        return None


def face_crop(image: np.ndarray, crop_factor: float = 1.72) -> np.ndarray | None:
    if image is None:
        return None
    height, width = image.shape[:2]
    detector = cv2.FaceDetectorYN.create(MODEL, "", (width, height), 0.5, 0.3, 5000)
    _, faces = detector.detect(image)
    if faces is None or len(faces) == 0:
        return None
    # Prefer a large, confident face.  The sources occasionally contain team
    # photos, so confidence alone is not enough and area alone can select a
    # foreground bystander.
    best = max(faces, key=lambda face: float(face[14]) * np.sqrt(face[2] * face[3]))
    x, y, w, h = best[:4].astype(int)
    size = max(1, int(max(w, h) * crop_factor))
    cx = x + w // 2
    cy = y + int(h * 0.52)
    # Keep the square inside the original photograph. Padding with duplicated
    # edge pixels visibly stretched heads near the image boundary.
    size = min(size, width, height)
    left = max(0, min(cx - size // 2, width - size))
    top = max(0, min(cy - size // 2, height - size))
    right = left + size
    bottom = top + size
    crop = image[top:bottom, left:right]
    if crop.size == 0:
        return None
    return cv2.resize(crop, (320, 320), interpolation=cv2.INTER_LANCZOS4)


def verified_manual_crop(image: np.ndarray, slug: str) -> np.ndarray | None:
    # Normalized, visually verified boxes for authentic portraits on which
    # YuNet does not return a detection. Values are center-x, center-y and
    # square size relative to the source dimensions.
    boxes = {
        "alec-udell": (0.67, 0.29, 0.48),
        "ryan-yardley": (0.62, 0.28, 0.45),
        "fran-rueda": (0.50, 0.26, 0.58),
    }
    box = boxes.get(slug)
    if image is None or box is None:
        return None
    height, width = image.shape[:2]
    size = max(1, int(min(width, height) * box[2]))
    cx, cy = int(width * box[0]), int(height * box[1])
    left = max(0, min(cx - size // 2, width - size))
    top = max(0, min(cy - size // 2, height - size))
    crop = image[top : top + size, left : left + size]
    return cv2.resize(crop, (320, 320), interpolation=cv2.INTER_LANCZOS4)


def process(series: str, only_slug: str | None = None, *, only_missing: bool = False) -> None:
    bundled_path = ROOT / "assets" / "data" / series / "2026" / "standings_drivers.json"
    document = json.loads(bundled_path.read_text(encoding="utf-8"))
    output = ROOT / "assets" / "portraits" / "faces" / series
    output.mkdir(parents=True, exist_ok=True)
    success = 0
    failed = 0
    for driver in document["data"]:
        name = f"{driver['givenName']} {driver['familyName']}"
        if only_missing and driver.get("imageUrl"):
            continue
        if only_slug and slugify(name) != only_slug:
            continue
        source = original_source(series, driver)
        if not source:
            failed += 1
            continue
        target = output / f"{slugify(name)}.jpg"
        if (
            source.startswith("assets/portraits/faces/")
            and slugify(name) in {"christian-rasmussen", "james-roe"}
        ):
            source_path = ROOT / source
            if source_path.resolve() != target.resolve():
                shutil.copyfile(source_path, target)
            driver["imageUrl"] = f"assets/portraits/faces/{series}/{target.name}"
            success += 1
            continue
        # Keep the complete head inside the square with a small margin.  The
        # previous tighter INDY NXT crop cut off chins, hair and sometimes half
        # of the face when the detected box sat close to an image edge.
        image = read_image(source)
        crop = face_crop(image, crop_factor=1.78)
        if crop is None:
            crop = verified_manual_crop(image, slugify(name))
        if crop is None:
            driver["imageUrl"] = None
            failed += 1
            print(f"INITIALS {series}/{name}")
            continue
        cv2.imwrite(str(target), crop, [cv2.IMWRITE_JPEG_QUALITY, 92])
        driver["imageUrl"] = f"assets/portraits/faces/{series}/{target.name}"
        success += 1
    text = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    bundled_path.write_text(text, encoding="utf-8")

    # Live standings can contain a newer/larger field than the bundled
    # fallback. Preserve every live row and merge only identity-bound portrait
    # metadata; never replace current points with the bundled snapshot.
    published_path = ROOT / "data" / series / "2026" / "standings_drivers.json"
    if published_path.is_file():
        published = json.loads(published_path.read_text(encoding="utf-8"))
        portraits = {
            (item.get("id") or f"{item.get('givenName', '')} {item.get('familyName', '')}".casefold()): item.get("imageUrl")
            for item in document["data"]
            if item.get("imageUrl")
        }
        by_name = {
            f"{item.get('givenName', '')} {item.get('familyName', '')}".strip().casefold(): item.get("imageUrl")
            for item in document["data"]
            if item.get("imageUrl")
        }
        for item in published.get("data", []):
            key = item.get("id")
            name = f"{item.get('givenName', '')} {item.get('familyName', '')}".strip().casefold()
            portrait = portraits.get(key) or by_name.get(name)
            if portrait:
                item["imageUrl"] = portrait
        published_path.write_text(
            json.dumps(published, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(f"{series}: faces={success}, initials={failed}")


def main() -> None:
    if len(sys.argv) == 3 and sys.argv[2] == "--missing":
        process(sys.argv[1], only_missing=True)
        return
    if len(sys.argv) == 2:
        process(sys.argv[1])
        return
    if len(sys.argv) == 3:
        process(sys.argv[1], sys.argv[2])
        return
    for series in ("imsa", "wec", "indycar", "indynxt"):
        process(series)


if __name__ == "__main__":
    main()
