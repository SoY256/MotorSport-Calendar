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
ENTRY_LIST_URL = "https://www.fiawec.com/umbrella_media/wec26-entrylist-a4-6936d72065269710536636.pdf"
MANUFACTURER_COLORS = {"Toyota": "#EB0A1E", "Ferrari": "#E10600", "Cadillac": "#C6A15B",
                       "BMW": "#0066B1", "Alpine": "#005BAA", "Aston Martin": "#006F62",
                       "Peugeot": "#003B70", "Genesis": "#C36B28", "Porsche": "#D5001C",
                       "Corvette": "#F2C500", "Ford": "#003478", "Lexus": "#222222",
                       "McLaren": "#FF8000", "Mercedes": "#00A19C"}
STANDING_COLORS = {"toyota": "#EB0A1E", "ferrari": "#E10600", "cadillac": "#C6A15B",
                   "bmw": "#0066B1", "alpine": "#005BAA", "aston_martin": "#006F62",
                   "peugeot": "#003B70", "genesis": "#C36B28", "porsche": "#D5001C"}
KNOWN_DRIVER_COUNTRIES = {
    "AL-KHELAIFI": "QAT", "CLOSMENIL": "FRA", "QUINN": "GBR", "GARG": "USA", "HANLEY": "GBR",
    "KEATING": "USA", "MCDONALD": "GBR", "TUCK": "GBR", "LAURSEN": "DNK", "MATEU": "ESP",
    "MILESI": "FRA", "SCHMID": "CHE", "TOLEDO": "ESP", "BLATTNER": "USA", "HANSSON": "DNK",
    "PIN": "FRA", "SCHNEIDER": "BRA", "BARRICHELLO": "BRA", "MASSON": "FRA", "PEARSON": "GBR",
    "TRULLI": "ITA", "PERRODO": "FRA", "POORDAD": "USA", "KURTZ": "USA", "LEVORATO": "ITA",
    "SAUCY": "CHE", "DAVID": "FRA", "FELBERMAYR": "AUT", "AGUILERA": "MEX", "ALLEN": "AUS",
    "ANDLAUER": "FRA", "COTTINGHAM": "GBR", "EDGAR": "GBR", "FARANO": "CAN", "GOUNON": "FRA",
    "HANSES": "DEU", "RIED": "DEU", "SMIECHOWSKI": "POL", "TAYLOR": "USA", "OHTA": "JPN",
    "PAUWELS": "BEL", "HANAFIN": "GBR", "KERN": "DEU", "PATRESE": "ITA", "WADOUX": "FRA",
    "BECHE": "CHE", "FOSSARD": "FRA", "JAKOBSEN": "DNK", "JENSEN": "DNK", "VAXIVIERE": "FRA",
    "FIDANI": "CAN", "DEMPSEY": "USA", "HYETT": "USA", "IBRAHIM": "IDN", "LAFARGUE": "FRA",
    "THOMPSON": "CAN", "UMBRĂRESCU": "ROU", "CULLEN": "IRL", "GÉRUS": "FRA", "KUBICA": "POL",
    "LINDH": "SWE", "PERA": "ITA", "ALVAREZ": "MEX", "GELAEL": "IDN", "VANDOORNE": "BEL",
    "YOLUÇ": "TUR", "BOGUSLAVSKIY": "RUS", "DILLMANN": "FRA", "KIMURA": "JPN", "LUTKE": "CAN",
    "ROMPUY": "BEL", "VAUTIER": "FRA", "LOMKO": "RUS", "RINICELLA": "ITA", "STEVENS": "GBR",
    "SHAHIN": "AUS", "ROBICHON": "CAN",
}


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


def manufacturer_color(car: str) -> str:
    return next((color for make, color in MANUFACTURER_COLORS.items() if make.lower() in car.lower()), "#607D8B")


def entry_nationalities(pdf: bytes) -> dict[str, str]:
    text = "\n".join(page.extract_text() or "" for page in pdfplumber.open(io.BytesIO(pdf)).pages)
    mappings = {}
    for full_name, country in re.findall(r"([A-ZÀ-ÖØ-Ý' -]{2,})\s+\(([A-Z]{3})\)", text):
        mappings[full_name.strip().split()[-1].upper()] = country
    if not mappings:
        print(text[:8000], file=sys.stderr)
        raise RuntimeError("No driver nationalities parsed from the WEC entry list")
    return {**KNOWN_DRIVER_COUNTRIES, **mappings}


def parse_rows(pdf: bytes, nationalities: dict[str, str]) -> list[dict]:
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
        clean_names, countries = [], []
        for part in drivers.split("/"):
            tokens = part.strip().split()
            matched = next(((index, nationalities[token.upper()]) for index, token in reversed(list(enumerate(tokens))) if token.upper() in nationalities), None)
            if matched:
                index, country = matched
                clean_names.append(" ".join(tokens[:index + 1]))
                countries.append(country)
            else:
                clean_names.append(part.strip())
        driver_names = " / ".join(clean_names)
        flags = ",".join(countries)
        rows.append({
            "position": int(position), "positionText": position,
            "driver": {"id": slug(driver_names), "code": number, "givenName": driver_names, "familyName": "", "nationality": flags or None},
            "team": {"id": slug(team), "name": team, "color": manufacturer_color(f"{team} {car}")}, "carNumber": number,
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
    nationalities = entry_nationalities(fetch(ENTRY_LIST_URL))
    for event, code in zip(calendar, EVENTS):
        url = classification_url(code)
        rows = parse_rows(fetch(url), nationalities)
        payload = {"schemaVersion": 1, "lastSuccessfulUpdate": updated,
                   "source": {"name": "fia-wec-alkamel-official-timing", "url": url},
                   "data": {"eventId": event["id"], "sessions": [{"type": "R", "name": "Race", "startTimeUtc": event["sessions"][-1]["startTimeUtc"], "results": rows}]}}
        (root / event["resultsPath"]).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{event['name']}: {len(rows)}", file=sys.stderr)
    driver_path = root / "standings_drivers.json"
    driver_doc = json.loads(driver_path.read_text(encoding="utf-8"))
    for driver in driver_doc["data"]:
        driver["teamColors"] = [STANDING_COLORS.get(team_id, "#607D8B") for team_id in driver.get("teamIds", [])]
    driver_path.write_text(json.dumps(driver_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    team_path = root / "standings_teams.json"
    team_doc = json.loads(team_path.read_text(encoding="utf-8"))
    for team in team_doc["data"]:
        team["color"] = STANDING_COLORS.get(team["id"], "#607D8B")
    team_path.write_text(json.dumps(team_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
