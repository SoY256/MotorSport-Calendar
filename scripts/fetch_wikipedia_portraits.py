"""Find conservative, identity-checked portrait fallbacks for missing drivers."""

from __future__ import annotations

import json
import re
import sys
import time
import unicodedata
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
HEADERS = {"User-Agent": "MotorSport-Calendar/0.1 (+https://github.com/SoY256/MotorSport-Calendar)"}
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def normalized(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    return re.sub(r"[^a-z0-9]+", "-", value.encode("ascii", "ignore").decode().lower()).strip("-")


def api(params: dict[str, str]) -> dict:
    url = "https://en.wikipedia.org/w/api.php?" + urlencode(params)
    with urlopen(Request(url, headers=HEADERS), timeout=30) as response:
        return json.load(response)


def portrait(name: str) -> str | None:
    direct = api({
        "action": "query",
        "format": "json",
        "titles": name,
        "redirects": "1",
        "prop": "extracts|pageimages",
        "exintro": "1",
        "explaintext": "1",
        "piprop": "original|thumbnail",
        "pithumbsize": "640",
    })
    searched = api({
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": f'"{name}" racing driver',
        "gsrlimit": "5",
        "prop": "extracts|pageimages",
        "exintro": "1",
        "explaintext": "1",
        "piprop": "original|thumbnail",
        "pithumbsize": "640",
    })
    wanted = normalized(name)
    pages = list(direct.get("query", {}).get("pages", {}).values())
    pages += list(searched.get("query", {}).get("pages", {}).values())
    for page in pages:
        title = re.sub(r"\s*\([^)]*\)\s*$", "", page.get("title", ""))
        extract = page.get("extract", "").lower()
        if normalized(title) != wanted:
            continue
        if not any(term in extract for term in ("racing driver", "race car driver", "motorsport driver")):
            continue
        image = page.get("thumbnail", {}).get("source") or page.get("original", {}).get("source")
        if image and not image.lower().endswith(".svg"):
            return image
    return None


def main() -> None:
    output = ROOT / "data" / "sources" / "wikipedia_driver_portraits.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    found = json.loads(output.read_text(encoding="utf-8")) if output.exists() else {}
    for series in ("f1", "f2", "f3", "wec", "imsa", "indycar", "indynxt"):
        source = ROOT / "assets" / "data" / series / "2026" / "standings_drivers.json"
        drivers = json.loads(source.read_text(encoding="utf-8"))["data"]
        for driver in drivers:
            if driver.get("imageUrl") and series not in ("indycar", "indynxt"):
                continue
            name = f"{driver['givenName']} {driver['familyName']}"
            if name in found:
                continue
            try:
                image = portrait(name)
            except Exception as error:
                print(f"ERROR {series}/{name}: {error}")
                continue
            if image:
                found[name] = image
                print(f"FOUND {series}/{name}")
            else:
                print(f"MISS  {series}/{name}")
            time.sleep(0.08)
    output.write_text(json.dumps(found, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(found)} verified portraits")


if __name__ == "__main__":
    main()
