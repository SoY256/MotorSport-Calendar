"""Validate generated portraits and render contact sheets for visual QA."""

from pathlib import Path
import json

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MODEL = str(ROOT / "scripts/models/face_detection_yunet_2023mar.onnx")


def audit(series: str) -> None:
    standings = json.loads(
        (ROOT / f"assets/data/{series}/2026/standings_drivers.json").read_text(encoding="utf-8")
    )
    paths = sorted(
        ROOT / driver["imageUrl"]
        for driver in standings["data"]
        if str(driver.get("imageUrl") or "").startswith(f"assets/portraits/faces/{series}/")
    )
    cards = []
    failures = []
    for path in paths:
        image = cv2.imread(str(path))
        detector = cv2.FaceDetectorYN.create(MODEL, "", (320, 320), 0.70, 0.3, 5000)
        _, faces = detector.detect(image)
        if faces is None:
            failures.append(path.name)
        thumb = cv2.resize(image, (128, 128))
        card = np.full((158, 160, 3), 245, dtype=np.uint8)
        card[:128, 16:144] = thumb
        cv2.putText(card, path.stem[:19], (3, 149), cv2.FONT_HERSHEY_SIMPLEX,
                    0.36, (10, 10, 10), 1, cv2.LINE_AA)
        cards.append(card)
    out = ROOT / ".tmp" / "portrait-audit"
    out.mkdir(parents=True, exist_ok=True)
    for page, start in enumerate(range(0, len(cards), 60), 1):
        chunk = cards[start:start + 60]
        rows = []
        for offset in range(0, len(chunk), 10):
            row = chunk[offset:offset + 10]
            row += [np.full_like(cards[0], 245)] * (10 - len(row))
            rows.append(np.hstack(row))
        cv2.imwrite(str(out / f"{series}-{page}.jpg"), np.vstack(rows))
    print(f"{series}: {len(paths)} portraits; detector failures: {failures}")


for name in ("imsa", "wec", "indycar", "indynxt"):
    audit(name)
