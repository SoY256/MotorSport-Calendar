"""Render downloaded team marks into a contact sheet for visual QA."""

from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
paths = sorted((ROOT / "assets/team_logos").glob("team-*.png"))
cards = []
for path in paths:
    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if image is None:
        continue
    if image.shape[2] == 4:
        alpha = image[:, :, 3:4] / 255.0
        image = (image[:, :, :3] * alpha + 255 * (1 - alpha)).astype(np.uint8)
    scale = min(170 / image.shape[1], 90 / image.shape[0])
    resized = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_LANCZOS4)
    card = np.full((130, 200, 3), 255, dtype=np.uint8)
    y = (100 - resized.shape[0]) // 2
    x = (200 - resized.shape[1]) // 2
    card[y:y + resized.shape[0], x:x + resized.shape[1]] = resized
    cv2.putText(card, path.stem[5:][:23], (4, 120), cv2.FONT_HERSHEY_SIMPLEX,
                0.42, (20, 20, 20), 1, cv2.LINE_AA)
    cards.append(card)
while len(cards) % 5:
    cards.append(np.full_like(cards[0], 245))
sheet = np.vstack([np.hstack(cards[i:i + 5]) for i in range(0, len(cards), 5)])
target = ROOT / ".tmp/team-logo-audit.jpg"
target.parent.mkdir(exist_ok=True)
cv2.imwrite(str(target), sheet)
print(target)
