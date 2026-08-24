"""Extract completed 2026 FIA WEC classifications from official timing PDFs."""

from __future__ import annotations

import io
import html as html_lib
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
STANDINGS_URL = "https://www.fiawec.com/en/season/2026"
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
    "HANSON": "GBR", "HABSBURG": "AUT", "DELÉTRAZ": "CHE", "CASSIDY": "NZL",
    "MARTINS": "FRA", "POURCHAIRE": "FRA", "HARPER": "GBR", "HAWKSWORTH": "GBR",
    "ADAM": "GBR", "GÜVEN": "TUR", "FARFUS": "BRA", "DRUDI": "ITA",
    "SARGEANT": "USA", "GATTUSO": "ITA", "VARRONE": "ARG", "POWELL": "GBR",
    "PRIAULX": "GBR",
}


def fetch(url: str) -> bytes:
    with urlopen(Request(url, headers=HEADERS), timeout=60) as response:
        return response.read()


def slug(value: str) -> str:
    plain = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return "-".join(re.findall(r"[a-z0-9]+", plain))


def clean_html(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html_lib.unescape(value)).strip()


def standings_table(page: str, title: str) -> str:
    start = page.find(title)
    if start < 0:
        raise RuntimeError(f"Missing WEC standings table: {title}")
    body_start = page.find("<tbody", start)
    body_start = page.find(">", body_start) + 1
    body_end = page.find("</tbody>", body_start)
    if body_start <= 0 or body_end < 0:
        raise RuntimeError(f"Malformed WEC standings table: {title}")
    return page[body_start:body_end]


def standings_rows(table: str) -> list[str]:
    return re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.I | re.S)


def standings_cells(row: str) -> list[str]:
    return [clean_html(cell) for cell in re.findall(r"<(?:td|th)[^>]*>(.*?)</(?:td|th)>", row, re.I | re.S)]


def manufacturer_from_row(row: str) -> str:
    match = re.search(r'<img[^>]+alt="([^"]+)"', row, re.I)
    if match:
        return html_lib.unescape(match.group(1)).strip()
    cells = standings_cells(row)
    if len(cells) > 1 and cells[1]:
        return cells[1]
    raise RuntimeError(f"Missing manufacturer in WEC standings row: {clean_html(row)[:240]}")


def points_from_cell(value: str) -> float:
    match = re.search(r"-?\d+(?:\.\d+)?", value)
    return float(match.group()) if match else 0.0


def display_name(value: str) -> str:
    small = {"de", "da", "do", "dos", "van", "von", "der", "di"}
    words = []
    for index, word in enumerate(value.lower().split()):
        words.append(word if index and word in small else word.capitalize())
    return " ".join(words)


def canonical_manufacturer(value: str) -> str:
    return next((name for name in MANUFACTURER_COLORS if name.casefold() == value.casefold()), value)


def full_standings(page: str, nationalities: dict[str, str], driver_wins: dict[tuple[str, str], int],
                   team_wins: dict[tuple[str, str], int], updated: str) -> tuple[dict, dict]:
    drivers: list[dict] = []
    teams: list[dict] = []
    driver_tables = {
        "HYPERCAR": "FIA Hypercar World Endurance Drivers Championship",
        "LMGT3": "FIA Endurance Trophy for LMGT3 Drivers",
    }
    for category, title in driver_tables.items():
        for row in standings_rows(standings_table(page, title)):
            cells = standings_cells(row)
            links = re.findall(r'<a[^>]+href="/en/driver/[^"]+"[^>]*>(.*?)</a>', row, re.I | re.S)
            if len(cells) < 5 or not links:
                continue
            position = int(cells[0])
            manufacturer = canonical_manufacturer(manufacturer_from_row(row))
            number = cells[2].lstrip("#")
            points = points_from_cell(cells[-1])
            for raw_name in links:
                name = display_name(clean_html(raw_name))
                parts = name.split()
                surname = parts[-1]
                team_id = slug(manufacturer)
                drivers.append({
                    "position": position, "points": points,
                    "wins": driver_wins.get((category, surname.upper()), 0),
                    "id": slug(name), "code": number,
                    "givenName": " ".join(parts[:-1]), "familyName": surname,
                    "nationality": nationalities.get(surname.upper(), ""),
                    "teamIds": [team_id], "teamNames": [manufacturer],
                    "teamColors": [MANUFACTURER_COLORS.get(manufacturer, "#607D8B")],
                    "category": category,
                })

    team_tables = {
        "HYPERCAR": "FIA Hypercar World Endurance Manufacturers’ Championship",
        "LMGT3": "FIA Endurance Trophy for LMGT3 Teams",
    }
    for category, title in team_tables.items():
        for row in standings_rows(standings_table(page, title)):
            cells = standings_cells(row)
            if len(cells) < 4:
                continue
            manufacturer = canonical_manufacturer(manufacturer_from_row(row))
            if category == "HYPERCAR":
                name = manufacturer
                number = ""
            else:
                number = cells[2].lstrip("#")
                name = cells[3]
            team_id = slug(f"{category}-{number}-{name}")
            teams.append({
                "position": int(cells[0]), "points": points_from_cell(cells[-1]),
                "wins": team_wins.get((category, number or slug(manufacturer)), 0),
                "id": team_id, "name": f"#{number} {name}" if number else name,
                "category": category,
                "color": MANUFACTURER_COLORS.get(manufacturer, "#607D8B"),
            })
    source = {"name": "fia-wec-official-championship", "url": STANDINGS_URL}
    return ({"schemaVersion": 1, "lastSuccessfulUpdate": updated, "source": source, "data": drivers},
            {"schemaVersion": 1, "lastSuccessfulUpdate": updated, "source": source, "data": teams})


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
    driver_wins: dict[tuple[str, str], int] = {}
    team_wins: dict[tuple[str, str], int] = {}
    for event, code in zip(calendar, EVENTS):
        url = classification_url(code)
        rows = parse_rows(fetch(url), nationalities)
        for category in ("HYPERCAR", "LMGT3"):
            winner = next((row for row in rows if row["components"]["category"] == category), None)
            if not winner:
                continue
            for driver in winner["driver"]["givenName"].split(" / "):
                key = (category, driver.split()[-1].upper())
                driver_wins[key] = driver_wins.get(key, 0) + 1
            if category == "HYPERCAR":
                combined = f"{winner['team']['name']} {winner['components']['car']}"
                make = next((name for name in MANUFACTURER_COLORS if name.lower() in combined.lower()), "")
                team_key = slug(make)
            else:
                team_key = winner["carNumber"]
            key = (category, team_key)
            team_wins[key] = team_wins.get(key, 0) + 1
        payload = {"schemaVersion": 1, "lastSuccessfulUpdate": updated,
                   "source": {"name": "fia-wec-alkamel-official-timing", "url": url},
                   "data": {"eventId": event["id"], "sessions": [{"type": "R", "name": "Race", "startTimeUtc": event["sessions"][-1]["startTimeUtc"], "results": rows}]}}
        (root / event["resultsPath"]).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{event['name']}: {len(rows)}", file=sys.stderr)
    driver_doc, team_doc = full_standings(
        fetch(STANDINGS_URL).decode("utf-8", "replace"), nationalities, driver_wins, team_wins, updated,
    )
    (root / "standings_drivers.json").write_text(
        json.dumps(driver_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    (root / "standings_teams.json").write_text(
        json.dumps(team_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    print(f"WEC standings: {len(driver_doc['data'])} drivers, {len(team_doc['data'])} teams", file=sys.stderr)


if __name__ == "__main__":
    main()
