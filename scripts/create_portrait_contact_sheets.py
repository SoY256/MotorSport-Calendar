"""Create labelled contact sheets for visual portrait QA."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

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
        sheet = Image.new("RGB", (COLS * TILE, rows * (TILE + LABEL)), "white")
        draw = ImageDraw.Draw(sheet)
        for index, driver in enumerate(group):
            x = (index % COLS) * TILE
            y = (index // COLS) * (TILE + LABEL)
            value = driver.get("imageUrl")
            image = None
            if value and value.startswith("assets/"):
                try:
                    image = Image.open(ROOT / value).convert("RGB")
                except (OSError, ValueError):
                    image = None
            if image is None:
                image = Image.new("RGB", (TILE, TILE), (220, 40, 40))
            else:
                image = image.resize((TILE, TILE), Image.Resampling.LANCZOS)
            sheet.paste(image, (x, y))
            name = f"{driver['givenName']} {driver['familyName']}"
            draw.text((x + 4, y + TILE + 3), name[:24], fill="black")
            draw.text((x + 4, y + TILE + 20), str(offset + index + 1), fill=(80, 80, 80))
        target = OUTPUT / f"{series}-{page:02d}.jpg"
        sheet.save(target, quality=93)
        print(target.relative_to(ROOT))


if __name__ == "__main__":
    selected = sys.argv[1:] or ["f1", "f2", "f3", "wec", "imsa", "indycar", "indynxt"]
    for item in selected:
        contact_sheets(item)
