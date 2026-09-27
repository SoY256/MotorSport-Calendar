"""Create labelled contact sheets for visual portrait QA."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "build" / "portrait_audit"
TILE = 180
LABEL = 42
COLS = 6
PER_PAGE = 48


def contact_sheets(series: str) -> None:
    document = json.loads(
        (ROOT / "assets" / "data" / series / "2026" / "standings_drivers.json").read_text(
            encoding="utf-8"
        )
    )
    items = document["data"]
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for page, offset in enumerate(range(0, len(items), PER_PAGE), 1):
        group = items[offset : offset + PER_PAGE]
        rows = (len(group) + COLS - 1) // COLS
        sheet = np.full((rows * (TILE + LABEL), COLS * TILE, 3), 255, np.uint8)
        for index, driver in enumerate(group):
            x = (index % COLS) * TILE
            y = (index // COLS) * (TILE + LABEL)
            value = driver.get("imageUrl")
            image = None
            if value and value.startswith("assets/"):
                image = cv2.imread(str(ROOT / value))
            if image is None:
                image = np.full((TILE, TILE, 3), (40, 40, 220), np.uint8)
            else:
                image = cv2.resize(image, (TILE, TILE), interpolation=cv2.INTER_AREA)
            sheet[y : y + TILE, x : x + TILE] = image
            name = f"{driver['givenName']} {driver['familyName']}"
            cv2.putText(
                sheet,
                name[:24],
                (x + 4, y + TILE + 19),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.42,
                (0, 0, 0),
                1,
                cv2.LINE_AA,
            )
            cv2.putText(
                sheet,
                str(offset + index + 1),
                (x + 4, y + TILE + 36),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.38,
                (80, 80, 80),
                1,
                cv2.LINE_AA,
            )
        target = OUTPUT / f"{series}-{page:02d}.jpg"
        cv2.imwrite(str(target), sheet, [cv2.IMWRITE_JPEG_QUALITY, 93])
        print(target.relative_to(ROOT))


if __name__ == "__main__":
    selected = sys.argv[1:] or ["f1", "f2", "f3", "wec", "imsa", "indycar", "indynxt"]
    for item in selected:
        contact_sheets(item)
