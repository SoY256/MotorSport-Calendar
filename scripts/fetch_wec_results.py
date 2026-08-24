"""Extract completed 2026 FIA WEC classifications from official timing PDFs."""

from __future__ import annotations

import io
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urljoin
from urllib.request import Request, urlopen

import pdfplumber

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://fiawec.alkamelsystems.com/"
EVENTS = ["01_IMOLA", "02_SPA FRANCORCHAMPS", "03_LE MANS", "04_SAO PAULO"]
HEADERS = {"User-Agent": "MotorSport-Calendar/0.1 (+https://github.com/SoY256/MotorSport-Calendar)"}


def fetch(url: str) -> bytes:
    with urlopen(Request(url, headers=HEADERS), timeout=60) as response:
        return response.read()


def slug(value: str) -> str:
    plain = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return "-".join(re.findall(r"[a-z0-9]+", plain))


def classification_url(code: str) -> str:
    index_url = f"{BASE}?evvent={quote(code)}&season=15_2026"
    html = fetch(index_url).decode("utf-8", "replace")
    hrefs = re.findall(r'href="([^"]+Classification_Race_Hour[^"?]+\.PDF)"', html, re.I)
    if not hrefs:
        # Le Mans uses Hour 24 while shorter rounds use their final numbered hour.
        hrefs = re.findall(r'href="([^"]+Classification[^"?]+Race[^"?]+\.PDF)"', html, re.I)
    if not hrefs:
        raise RuntimeError(f"No race classification PDF for {code}")
    return urljoin(BASE, hrefs[-1])


def parse_rows(pdf: bytes) -> list[dict]:
    text = "\n".join(page.extract_text() or "" for page in pdfplumber.open(io.BytesIO(pdf)).pages)
    rows = []
    pattern = re.compile(
        r"^(\d+)\s+(\w+)\s+(.+?)\s+((?:[A-Z]\.?\s+[A-ZÀ-ÖØ-Ý?' -]+)(?:\s+/\s+(?:[A-Z]\.?\s+[A-ZÀ-ÖØ-Ý?' -]+))+?)\s+(.+?)\s+(HYPERCAR|LMGT3|LMP2(?: P/A)?)\s+[A-Z]\s+(\d+)\s*(.+)$"
    )
    for line in text.splitlines():
        match = pattern.match(line.strip())
        if not match:
            continue
        position, number, team, drivers, car, category, laps, tail = match.groups()
        driver_names = " / ".join(part.strip() for part in drivers.split("/"))
        rows.append({
            "position": int(position), "positionText": position,
            "driver": {"id": slug(driver_names), "code": number, "givenName": driver_names, "familyName": ""},
            "team": {"id": slug(team), "name": team, "color": "#00695C"}, "carNumber": number,
            "time": tail.split()[0] if tail else None, "laps": int(laps), "points": None, "status": category,
            "classified": True, "components": {"car": car, "category": category},
        })
    if len(rows) < 10:
        raise RuntimeError(f"Only {len(rows)} WEC rows parsed")
    return rows


def main() -> None:
    root = ROOT / "assets" / "data" / "wec" / "2026"
    calendar = json.loads((root / "calendar.json").read_text(encoding="utf-8"))["data"]
    updated = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    for event, code in zip(calendar, EVENTS):
        url = classification_url(code)
        rows = parse_rows(fetch(url))
        payload = {"schemaVersion": 1, "lastSuccessfulUpdate": updated,
                   "source": {"name": "fia-wec-alkamel-official-timing", "url": url},
                   "data": {"eventId": event["id"], "sessions": [{"type": "R", "name": "Race", "startTimeUtc": event["sessions"][-1]["startTimeUtc"], "results": rows}]}}
        (root / event["resultsPath"]).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{event['name']}: {len(rows)}", file=sys.stderr)


if __name__ == "__main__":
    main()
