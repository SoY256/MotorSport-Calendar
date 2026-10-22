"""Extract completed FIA WEC classifications from official timing PDFs."""

from __future__ import annotations

import io
import html as html_lib
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, unquote, urljoin

from http_retry import read
from seasons import results_season


ROOT = Path(__file__).resolve().parents[1]
BASE = "https://fiawec.alkamelsystems.com/"
HEADERS = {"User-Agent": "MotorSport-Calendar/0.1 (+https://github.com/SoY256/MotorSport-Calendar)"}
ENTRY_LIST_URL = "https://www.fiawec.com/umbrella_media/wec26-entrylist-a4-6936d72065269710536636.pdf"
# The season being imported; main() moves it to the latest started season.
SEASON = 2026
STANDINGS_URL = f"https://www.fiawec.com/en/season/{SEASON}"


def timing_season() -> str:
    """Al Kamel season code, e.g. ``15_2026``."""
    return f"{SEASON - 2011}_{SEASON}"
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


def pdf_text(pdf: bytes) -> str:
    # Imported lazily so the pure parsing helpers stay testable without it.
    import pdfplumber

    return "\n".join(page.extract_text() or "" for page in pdfplumber.open(io.BytesIO(pdf)).pages)


def fetch(url: str) -> bytes:
    return read(url, HEADERS)


def entry_list_url() -> str:
    """The season's official entry list (linked from the season page)."""
    try:
        page = fetch(STANDINGS_URL).decode("utf-8", "replace")
    except Exception:
        page = ""
    links = re.findall(rf'href="([^"]*wec{SEASON % 100}-entry-?list[^"]*\.pdf)"', page, re.I)
    return urljoin("https://www.fiawec.com", links[0]) if links else ENTRY_LIST_URL


def completed_event_codes() -> list[str]:
    html = fetch(f"{BASE}?season={timing_season()}").decode("utf-8", "replace")
    codes = set(re.findall(r'<option[^>]+value="(\d+_[^"]+)"', html, re.I))
    return sorted(code for code in codes if not re.fullmatch(r"\d+_20\d{2}(?:-20\d{2})?", code))


EVENT_CODE_ALIASES = {
    "6 Hours of Imola": ("IMOLA",),
    "6 Hours of Spa-Francorchamps": ("SPA",),
    "24 Hours of Le Mans": ("LE MANS",),
    "6 Hours of São Paulo": ("SAO PAULO", "SÃO PAULO"),
    "Lone Star Le Mans": ("CIRCUIT OF THE AMERICAS", "COTA", "LONE STAR", "AUSTIN"),
    "6 Hours of Fuji": ("FUJI",),
    "6 Hours of Barcelona": ("BARCELONA", "CATALUNYA"),
    "6 Hours of Monza": ("MONZA",),
    "Qatar 1812 km": ("QATAR", "LUSAIL"),
    "6 Hours of Silverstone": ("SILVERSTONE",),
    "8 Hours of Bahrain": ("BAHRAIN", "SAKHIR"),
}


def event_code(event: dict, codes: list[str]) -> str | None:
    """Match an official timing event to the calendar by venue, never position.

    The timing site can repeat or omit event entries while a weekend is live.
    Positional ``zip(calendar, codes)`` therefore assigned old classifications
    to later rounds (including future races).  Venue identity is stable.
    """
    aliases = EVENT_CODE_ALIASES.get(event["name"], ())
    matches = [
        code for code in codes
        if any(alias in code.upper().replace("%20", " ") for alias in aliases)
    ]
    if len(matches) > 1:
        raise RuntimeError(f"Ambiguous WEC event code for {event['name']}: {matches}")
    return matches[0] if matches else None


def slug(value: str) -> str:
    plain = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return "-".join(re.findall(r"[a-z0-9]+", plain))


RACE_PAGE_ALIASES = {
    "6 Hours of Imola": "imola",
    "6 Hours of Spa-Francorchamps": "spa-francorchamps",
    "24 Hours of Le Mans": "24-hours-of-le-mans",
    "6 Hours of São Paulo": "sao-paulo",
    "Lone Star Le Mans": "lone-star",
    "6 Hours of Fuji": "fuji",
    "6 Hours of Barcelona": "barcelona",
    "6 Hours of Monza": "monza",
    "Qatar 1812 km": "qatar",
    "6 Hours of Silverstone": "silverstone",
    "8 Hours of Bahrain": "bahrain",
}


def race_pages(season_html: str) -> list[str]:
    pages = re.findall(rf'href="(/en/race/[a-z0-9-]+-{SEASON})"', season_html)
    return sorted({page for page in pages if "prologue" not in page})


def race_page_for(event: dict, pages: list[str]) -> str | None:
    alias = RACE_PAGE_ALIASES.get(event["name"])
    matches = [page for page in pages if alias and alias in page]
    if len(matches) > 1:
        raise RuntimeError(f"Ambiguous WEC race page for {event['name']}: {matches}")
    return matches[0] if matches else None


def session_type(name: str) -> str:
    """Stable session type; only the race keeps the shared type ``R``."""
    if name.strip().casefold() == "race":
        return "R"
    compact = re.sub(r"[^A-Z0-9]+", "_", slug(name).upper()).strip("_")
    compact = compact.replace("FREE_PRACTICE_", "FP")
    return compact or "SESSION"


def official_timetable(page_html: str) -> list[dict]:
    """Every session listed on an official fiawec.com race page, in order."""
    sessions = []
    pattern = re.compile(
        r'<div class="fw-bold lh-sm[^"]*">\s*([^<]+?)\s*</div>\s*'
        r'<div class="[^"]*">\s*<span[^>]*data-timestamp="(\d+)"',
        re.S,
    )
    seen = set()
    for raw_name, stamp in pattern.findall(page_html):
        name = " ".join(html_lib.unescape(raw_name).split())
        start = datetime.fromtimestamp(int(stamp), timezone.utc)
        key = (name, start)
        if key in seen:
            continue
        seen.add(key)
        sessions.append({
            "type": session_type(name),
            "name": name,
            "startTimeUtc": start.isoformat().replace("+00:00", "Z"),
            "cancelled": False,
        })
    sessions.sort(key=lambda item: item["startTimeUtc"])
    return sessions


def refresh_timetable(event: dict, pages: list[str]) -> None:
    """Replace the event sessions with the official timetable when available."""
    page = race_page_for(event, pages)
    if page is None:
        return
    try:
        sessions = official_timetable(fetch(f"https://www.fiawec.com{page}").decode("utf-8", "replace"))
    except Exception as error:  # keep the previous verified timetable
        print(f"{event['name']}: timetable unavailable: {error}", file=sys.stderr)
        return
    if sum(1 for item in sessions if item["type"] == "R") != 1:
        print(f"{event['name']}: timetable without a single race; kept", file=sys.stderr)
        return
    previous = {item["type"]: item for item in event.get("sessions", [])}
    for item in sessions:
        if "durationMinutes" in previous.get(item["type"], {}):
            item["durationMinutes"] = previous[item["type"]]["durationMinutes"]
    event["sessions"] = sessions


def race_session(event: dict) -> dict:
    return next(item for item in event["sessions"] if item["type"] == "R")


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


class ClassificationUnavailable(RuntimeError):
    """The official final race classification has not been published yet."""


def classification_url(code: str, total_hours: int, hrefs: list[str] | None = None) -> str:
    """Return the final race classification, never an intermediate hourly one.

    Alkamel publishes ``Classification_Race_Hour N`` after every hour of the
    race. The last hour's document (``..._Final.PDF`` once verified) is the
    only complete result.
    """
    if hrefs is None:
        hrefs = event_hrefs(code)
    found = [
        (href, hour)
        for href in hrefs
        for hour in re.findall(r"/03_Classification_Race_Hour(?:%20|\s)(\d+)[^/?]*\.PDF$", href, re.I)
    ]
    finals = [href for href, _hour in found if re.search(r"[_ ]Final\.PDF$|%20Final\.PDF$", href, re.I)]
    complete = [href for href, hour in found if int(hour) >= total_hours]
    chosen = finals or complete
    if not chosen:
        raise ClassificationUnavailable(f"No final race classification PDF for {code}")
    return urljoin(BASE, chosen[-1])


def fastest_lap_url(code: str, hrefs: list[str] | None = None) -> str:
    if hrefs is None:
        hrefs = event_hrefs(code)
    found = [href for href in hrefs if re.search(r"07_FastestLapByDriver_Race_Hour[^/?]+\.PDF$", href, re.I)]
    if not found:
        raise RuntimeError(f"No race fastest-lap PDF for {code}")
    return urljoin(BASE, found[-1])


def event_hrefs(code: str, html: str | None = None) -> list[str]:
    """FIA WEC timing documents that belong to ``code`` itself.

    The timing site answers requests for an older event with the documents of
    the current one, so every link is checked against the event folder; the
    support-series folders on the same page are ignored as well.
    """
    if html is None:
        html = fetch(f"{BASE}?evvent={quote(code)}&season={timing_season()}").decode("utf-8", "replace")
    prefix = f"Results/{timing_season()}/{code}/".casefold()
    hrefs = []
    for href in re.findall(r'href="([^"]+\.PDF)"', html, re.I):
        plain = unquote(html_lib.unescape(href))
        if plain.casefold().startswith(prefix) and re.search(r"/\d+_FIA WEC/", plain):
            hrefs.append(href)
    return hrefs


def session_key(name: str) -> str:
    """Compare timetable names with timing folder names.

    ``Qualifying - LMP2 & LMGT3`` (fiawec.com) and ``Qualifying LMP2-LMGT3``
    (Al Kamel) both become ``qualifyinglmp2lmgt3``.
    """
    return re.sub(r"[^a-z0-9]", "", name.casefold())


def session_classifications(hrefs: list[str]) -> dict[str, str]:
    """Session key -> best overall classification PDF (final preferred)."""
    folders: dict[str, list[str]] = {}
    for href in hrefs:
        plain = unquote(html_lib.unescape(href))
        match = re.search(r"/\d+_FIA WEC/\d{12}_([^/]+)/03_Classification_[^/]+\.PDF$", plain, re.I)
        if match and not match.group(1).casefold().startswith("race"):
            folders.setdefault(session_key(match.group(1)), []).append(href)
    chosen = {}
    for key, links in folders.items():
        finals = [link for link in links if re.search(r"Final\.PDF$", link, re.I)]
        chosen[key] = urljoin(BASE, (finals or links)[-1])
    return chosen


def fastest_lap_record(pdf: bytes) -> str:
    text = pdf_text(pdf)
    match = re.search(
        r"^1\s+\S+\s+.+?\s+HYPERCAR\s+(.+?)\s+(\d+:\d+\.\d+)\s+\d+\s+\d+\s+\d+\.\d+$",
        text,
        re.M,
    )
    if not match:
        raise RuntimeError("No overall WEC fastest lap parsed")
    return f"{match.group(2)} • {display_name(match.group(1))} ({SEASON})"


def manufacturer_color(car: str) -> str:
    return next((color for make, color in MANUFACTURER_COLORS.items() if make.lower() in car.lower()), "#607D8B")


def entry_nationalities(pdf: bytes) -> dict[str, str]:
    text = pdf_text(pdf)
    mappings = {}
    for full_name, country in re.findall(r"([A-ZÀ-ÖØ-Ý' -]{2,})\s+\(([A-Z]{3})\)", text):
        mappings[full_name.strip().split()[-1].upper()] = country
    if not mappings:
        print(text[:8000], file=sys.stderr)
        raise RuntimeError("No driver nationalities parsed from the WEC entry list")
    return {**KNOWN_DRIVER_COUNTRIES, **mappings}


NAME_CHARS = r"[A-ZÀ-ÖØ-Ý?'-]+(?![a-z])"
# All co-drivers are captured and surnames may span several upper-case words
# ("S. VAN DER LINDE", "N. DE VRIES"). Car names start with a mixed-case word
# ("Toyota TR010") except BMW, which therefore never belongs to a surname.
DRIVER_NAMES = (
    rf"(?:[A-Z]\.?\s+{NAME_CHARS}(?:\s+{NAME_CHARS})*\s+/\s+)*"
    rf"[A-Z]\.?\s+{NAME_CHARS}(?:\s+(?!BMW\b){NAME_CHARS})*"
)
CATEGORIES = r"(HYPERCAR|LMGT3|LMP2(?: P/A)?)"
# Bump when session parsing changes so stored classifications are re-read.
SESSION_PARSER = 3


def clean_drivers(drivers: str, nationalities: dict[str, str]) -> tuple[str, str]:
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
    return " / ".join(clean_names), ",".join(countries)


ENTRY_LINE = re.compile(
    rf"^(\d+)\s*(.+?)\s+({DRIVER_NAMES})\s+(.+?)\s+{CATEGORIES}\s+[A-Z](?:\s+(.*))?$"
)


def classification_entries(text: str) -> list[tuple]:
    """``(position | None, car, team, drivers, car model, category, tail)``.

    Classified cars are listed in running order; qualifying adds an "HP"
    marker for Hyperpole qualifiers and may glue the car number to the team
    ("12007Aston" = P12, car #007), so positions come from the order. Cars
    listed after the classified ones without a position are not classified.
    """
    entries: list[tuple] = []
    expected = 1
    for raw in text.splitlines():
        line = re.sub(r"^HP\s+", "", raw.strip())
        prefix = str(expected)
        if line.startswith(prefix):
            match = ENTRY_LINE.match(line[len(prefix):].lstrip())
            if match:
                entries.append((expected, *match.groups()))
                expected += 1
                continue
        match = ENTRY_LINE.match(line)
        if match and entries:
            entries.append((None, *match.groups()))
    return entries


def result_row(position, number, team, drivers, car, category, nationalities) -> dict:
    driver_names, flags = clean_drivers(drivers, nationalities)
    return {
        "position": position, "positionText": str(position) if position else "NC",
        "driver": {"id": slug(driver_names), "code": number, "givenName": driver_names, "familyName": "", "nationality": flags or None},
        "team": {"id": slug(team), "name": team, "color": manufacturer_color(f"{team} {car}")}, "carNumber": number,
        "points": None, "status": category, "classified": position is not None,
        "components": {"car": car, "category": category},
    }


def parse_session_rows(pdf: bytes, nationalities: dict[str, str], text: str | None = None) -> list[dict]:
    """Practice, qualifying, Hyperpole and warm-up classifications.

    Line layout: ``Pos No Team Drivers Car Cat Tyre BestLap BestLapNo TotalLaps Gap Kph``.
    """
    text = pdf_text(pdf) if text is None else text
    rows = []
    for position, number, team, drivers, car, category, tail in classification_entries(text):
        tail = tail or ""
        best = re.search(r"\b(\d+:\d{2}\.\d{3})\b", tail)
        after = tail[best.end():].split() if best else []
        numbers = [int(value) for value in after[:2] if value.isdigit()]
        gap = re.search(r"\+(\d+(?::\d{2})?\.\d{3})", tail)
        row = result_row(position, number, team, drivers, car, category, nationalities)
        row["time"] = best.group(1) if best else None
        row["laps"] = numbers[-1] if numbers else None
        if gap:
            row["components"]["gap"] = f"+{gap.group(1)}"
        rows.append(row)
    if sum(1 for row in rows if row["classified"]) < 3:
        raise RuntimeError(f"Only {len(rows)} WEC session rows parsed")
    return rows


def parse_rows(pdf: bytes, nationalities: dict[str, str], text: str | None = None) -> list[dict]:
    """Race classification: ``... Tyre Laps Time|Gap ...``."""
    text = pdf_text(pdf) if text is None else text
    rows = []
    for position, number, team, drivers, car, category, tail in classification_entries(text):
        # Laps have at most three digits; the time may follow without a
        # space in the PDF text ("38124:01:..." = 381 laps, 24:01:...).
        match = re.match(r"(\d{1,3})\s*(.*)", tail or "")
        row = result_row(position, number, team, drivers, car, category, nationalities)
        row["laps"] = int(match.group(1)) if match else None
        row["time"] = (match.group(2).split() or [None])[0] if match else None
        rows.append(row)
    if sum(1 for row in rows if row["classified"]) < 10:
        raise RuntimeError(f"Only {len(rows)} WEC rows parsed")
    return rows


def main() -> None:
    global SEASON, STANDINGS_URL
    data_root = Path(os.environ.get("MOTORSPORT_DATA_ROOT", ROOT / "assets" / "data"))
    SEASON = results_season(data_root / "wec", SEASON)
    STANDINGS_URL = f"https://www.fiawec.com/en/season/{SEASON}"
    root = data_root / "wec" / str(SEASON)
    calendar_path = root / "calendar.json"
    calendar_doc = json.loads(calendar_path.read_text(encoding="utf-8"))
    calendar = calendar_doc["data"]
    events = completed_event_codes()
    updated = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    nationalities = entry_nationalities(fetch(entry_list_url()))
    driver_wins: dict[tuple[str, str], int] = {}
    team_wins: dict[tuple[str, str], int] = {}
    now = datetime.now(timezone.utc)
    try:
        pages = race_pages(fetch(STANDINGS_URL).decode("utf-8", "replace"))
    except Exception as error:
        print(f"WEC race pages unavailable: {error}", file=sys.stderr)
        pages = []
    for event in calendar:
        refresh_timetable(event, pages)
        session = race_session(event)
        scheduled_end = datetime.fromisoformat(
            session["startTimeUtc"].replace("Z", "+00:00")
        ) + timedelta(minutes=int(session.get("durationMinutes", 360)))
        code = event_code(event, events)
        results_path = root / event["resultsPath"]
        previous: dict[str, dict] = {}
        if results_path.is_file():
            try:
                kept = json.loads(results_path.read_text(encoding="utf-8"))
                previous = {item["type"]: item for item in kept["data"].get("sessions", []) if item.get("results")}
            except (KeyError, ValueError):
                previous = {}
        first_start = min(
            datetime.fromisoformat(item["startTimeUtc"].replace("Z", "+00:00")) for item in event["sessions"]
        )
        if code is None or first_start > now:
            payload = {"schemaVersion": 1, "lastSuccessfulUpdate": updated,
                       "source": {"name": "fia-wec-official", "url": STANDINGS_URL},
                       "data": {"eventId": event["id"], "sessions": []}}
            results_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            continue
        hrefs = event_hrefs(code)
        sessions_out: dict[str, dict] = {}
        source_url = STANDINGS_URL
        # Practice, qualifying, Hyperpole and warm-up classifications.
        documents = session_classifications(hrefs)
        for item in event["sessions"]:
            if item["type"] == "R":
                continue
            end = datetime.fromisoformat(item["startTimeUtc"].replace("Z", "+00:00")) + timedelta(
                minutes=int(item.get("durationMinutes", 60))
            )
            url = documents.get(session_key(item["name"]))
            if end > now or url is None:
                if item["type"] in previous:
                    sessions_out[item["type"]] = previous[item["type"]]
                continue
            earlier = previous.get(item["type"])
            earlier_source = (earlier or {}).get("source", {})
            if (
                earlier_source.get("url") == url
                and earlier_source.get("parser") == SESSION_PARSER
                and re.search(r"Final\.PDF$", url, re.I)
            ):
                # Final classifications never change; skip the download.
                sessions_out[item["type"]] = earlier
                continue
            try:
                rows = parse_session_rows(fetch(url), nationalities)
            except Exception as error:  # keep the last verified classification
                print(f"{event['name']} {item['name']}: {error}", file=sys.stderr)
                if item["type"] in previous:
                    sessions_out[item["type"]] = previous[item["type"]]
                continue
            sessions_out[item["type"]] = {
                "type": item["type"], "name": item["name"], "startTimeUtc": item["startTimeUtc"],
                "source": {"name": "fia-wec-alkamel-official-timing", "url": url, "parser": SESSION_PARSER},
                "results": rows,
            }
            print(f"{event['name']} {item['name']}: {len(rows)}", file=sys.stderr)
        race_rows = None
        if scheduled_end <= now:
            try:
                url = classification_url(code, max(1, int(session.get("durationMinutes", 360)) // 60), hrefs)
            except ClassificationUnavailable as error:
                print(f"{event['name']}: {error}", file=sys.stderr)
            else:
                race_rows = parse_rows(fetch(url), nationalities)
                source_url = url
                sessions_out["R"] = {"type": "R", "name": "Race", "startTimeUtc": session["startTimeUtc"],
                                     "source": {"name": "fia-wec-alkamel-official-timing", "url": url},
                                     "results": race_rows}
                try:
                    event["circuit"]["lapRecord"] = fastest_lap_record(fetch(fastest_lap_url(code, hrefs)))
                except RuntimeError as error:
                    # The fastest-lap PDF can follow the classification by some minutes.
                    print(f"{event['name']}: lap record unavailable: {error}", file=sys.stderr)
        if race_rows is None and "R" in previous:
            sessions_out["R"] = previous["R"]
            race_rows = previous["R"]["results"]
        order = {item["type"]: index for index, item in enumerate(event["sessions"])}
        payload = {"schemaVersion": 1, "lastSuccessfulUpdate": updated,
                   "source": {"name": "fia-wec-alkamel-official-timing", "url": source_url},
                   "data": {"eventId": event["id"],
                            "sessions": sorted(sessions_out.values(), key=lambda item: order.get(item["type"], 999))}}
        results_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if not race_rows:
            continue
        rows = race_rows
        print(f"{event['name']}: {len(rows)}", file=sys.stderr)
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
    calendar_doc["lastSuccessfulUpdate"] = updated
    calendar_path.write_text(
        json.dumps(calendar_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
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
