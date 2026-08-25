"""Attach verified official portrait URLs to bundled and published standings."""

from __future__ import annotations

import json
from pathlib import Path
import os
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin

from fetch_data import official_f1_portraits, slugify
from fetch_feeder_data import official_portraits
from http_retry import read

ROOT = Path(__file__).resolve().parents[1]
HEADERS = {"User-Agent": "MotorSport-Calendar/0.1 (+https://github.com/SoY256/MotorSport-Calendar)"}


def indy_portraits(domain: str) -> dict[str, str]:
    base = f"https://www.{domain}.com"
    html = read(f"{base}/Drivers", HEADERS).decode("utf-8", "replace")
    profiles = sorted(set(re.findall(r'href="(/Drivers/[^"]+)"', html, re.I)))

    def portrait(profile: str) -> tuple[str, str] | None:
        page = read(urljoin(base, profile), HEADERS).decode("utf-8", "replace")
        match = re.search(
            r'<img src="([^"]+/FullBody/[^"]+\.png[^"]*)"[\s\S]{0,300}?alt="([^"]+) standing"',
            page,
            re.I,
        )
        if not match:
            return None
        return slugify(match.group(2)), urljoin(base, match.group(1))

    with ThreadPoolExecutor(max_workers=6) as pool:
        found = list(pool.map(portrait, profiles))
    return dict(item for item in found if item is not None)


def enrich(root: Path, series: str, portraits: dict[str, str]) -> int:
    path = root / series / "2026" / "standings_drivers.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    matched = 0
    for driver in document["data"]:
        driver_id = slugify(f"{driver.get('givenName', '')} {driver.get('familyName', '')}")
        image = portraits.get(driver_id) or portraits.get(slugify(driver.get("id", "")))
        if not image:
            family = slugify(driver.get("familyName", ""))
            family_matches = [url for key, url in portraits.items() if key == family or key.endswith(f"-{family}")]
            if len(family_matches) == 1:
                image = family_matches[0]
        if image:
            driver["imageUrl"] = image.replace("w_406", "w_1024").replace("w_440", "w_1024")
            matched += 1
        else:
            driver.pop("imageUrl", None)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return matched


def main() -> None:
    sources = {
        "f1": official_f1_portraits(),
        "f2": official_portraits("f2"),
        "f3": official_portraits("f3"),
        "indycar": indy_portraits("indycar"),
        "indynxt": indy_portraits("indynxt"),
    }
    configured = os.environ.get("PORTRAIT_SINGLE_ROOT")
    roots = (Path(configured),) if configured else (ROOT / "assets" / "data", ROOT / "data")
    for root in roots:
        for series, portraits in sources.items():
            matched = enrich(root, series, portraits)
            print(f"{root.name}/{series}: {matched} portraits")


if __name__ == "__main__":
    main()
