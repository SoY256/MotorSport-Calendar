"""Create verified local face crops; fall back to initials when no face is found."""

from __future__ import annotations

import json
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
WIKI = json.loads((ROOT / "data" / "sources" / "wikipedia_driver_portraits.json").read_text(encoding="utf-8"))
IMSA = json.loads((ROOT / "data" / "sources" / "imsa_driver_portraits.json").read_text(encoding="utf-8"))


def original_source(series: str, driver: dict) -> str | None:
    name = f"{driver['givenName']} {driver['familyName']}"
    slug = slugify(name)
    for suffix in ("jpg", "png"):
        local = ROOT / "assets" / "portraits" / series / f"{slug}.{suffix}"
        if local.exists():
            return local.relative_to(ROOT).as_posix()
    if name in IMSA:
        return IMSA[name]
    if name in WIKI:
        return WIKI[name]
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
    detector = cv2.FaceDetectorYN.create(MODEL, "", (width, height), 0.72, 0.3, 5000)
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
    left = cx - size // 2
    top = cy - size // 2
    right = left + size
    bottom = top + size
    # Pad beyond the photograph instead of clipping and stretching.  This is
    # what previously distorted portraits close to an edge (notably Kubica).
    pad_left = max(0, -left)
    pad_top = max(0, -top)
    pad_right = max(0, right - width)
    pad_bottom = max(0, bottom - height)
    if pad_left or pad_top or pad_right or pad_bottom:
        image = cv2.copyMakeBorder(
            image, pad_top, pad_bottom, pad_left, pad_right, cv2.BORDER_REPLICATE
        )
        left += pad_left
        right += pad_left
        top += pad_top
        bottom += pad_top
    crop = image[top:bottom, left:right]
    if crop.size == 0:
        return None
    return cv2.resize(crop, (320, 320), interpolation=cv2.INTER_LANCZOS4)


def process(series: str, only_slug: str | None = None) -> None:
    bundled_path = ROOT / "assets" / "data" / series / "2026" / "standings_drivers.json"
    document = json.loads(bundled_path.read_text(encoding="utf-8"))
    output = ROOT / "assets" / "portraits" / "faces" / series
    output.mkdir(parents=True, exist_ok=True)
    success = 0
    failed = 0
    for driver in document["data"]:
        name = f"{driver['givenName']} {driver['familyName']}"
        if only_slug and slugify(name) != only_slug:
            continue
        source = original_source(series, driver)
        if not source:
            failed += 1
            continue
        target = output / f"{slugify(name)}.jpg"
        crop = face_crop(
            read_image(source),
            crop_factor=1.32 if series == "indynxt" else 1.72,
        )
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
    (ROOT / "data" / series / "2026" / "standings_drivers.json").write_text(text, encoding="utf-8")
    print(f"{series}: faces={success}, initials={failed}")


def main() -> None:
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
