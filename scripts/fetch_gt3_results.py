"""Import the SRO GT3 championships from their official websites.

GT World Challenge Europe (Endurance and Sprint Cups), America, Asia and
Australia, the Intercontinental GT Challenge and British GT share one SRO
website platform. Every page used here is server-rendered HTML:

* ``/calendar``                      championship rounds
* ``/event/<id>/<slug>``             timetable (local time and GMT)
* ``/results?filter_season_id=..``   classification links per session
* ``/results/<year>/<event>/<sess>`` classification table
* ``/standings?...``                 driver and team standings per class
* ``/driver/<id>/<slug>``            nationality and official portrait

Only GT3 machinery is imported: GT4 sessions, classes and standings that
share a British GT weekend are skipped.
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fetch_data import slugify
from http_retry import read

ROOT = Path(__file__).resolve().parents[1]
SEASON = 2026
USER_AGENT = "Mozilla/5.0 (compatible; SecarCalendar/1.0; +https://github.com/SoY256/MotorSport-Calendar)"
EUROPE = "https://www.gt-world-challenge-europe.com"

# id -> (site, name, short name, colour, cup filter, default race minutes)
SERIES: dict[str, dict[str, Any]] = {
    "gtwc-endurance": {
        "base": EUROPE,
        "name": "GT World Challenge Europe Endurance Cup",
        "short": "GTWC ENDURANCE",
        "color": "#0057B8",
        "cup": "Endurance Cup",
        "race_minutes": 180,
    },
    "gtwc-sprint": {
        "base": EUROPE,
        "name": "GT World Challenge Europe Sprint Cup",
        "short": "GTWC SPRINT",
        "color": "#00A3E0",
        "cup": "Sprint Cup",
        "race_minutes": 60,
    },
    "gtwc-america": {
        "base": "https://www.gt-world-challenge-america.com",
        "name": "GT World Challenge America",
        "short": "GTWC AMERICA",
        "color": "#3949AB",
        "race_minutes": 90,
    },
    "gtwc-asia": {
        "base": "https://www.gt-world-challenge-asia.com",
        "name": "GT World Challenge Asia",
        "short": "GTWC ASIA",
        "color": "#C2185B",
        "race_minutes": 60,
    },
    "gtwc-australia": {
        "base": "https://www.gt-world-challenge-australia.com",
        "name": "GT World Challenge Australia",
        "short": "GTWC AUSTRALIA",
        "color": "#F9A825",
        "race_minutes": 60,
    },
    "british-gt": {
        "base": "https://www.britishgt.com",
        "name": "British GT Championship",
        "short": "BRITISH GT",
        "color": "#2E7D32",
        "race_minutes": 120,
    },
    # IGTC runs last: its standings list names only, so nationalities and
    # portraits are borrowed from the GTWC driver profiles imported above.
    "igtc": {
        "base": "https://www.intercontinentalgtchallenge.com",
        "name": "Intercontinental GT Challenge",
        "short": "IGTC",
        "color": "#B8860B",
        "race_minutes": 360,
    },
}

SESSION_WORDS = re.compile(r"practice|qualif|pole|race|warm|shootout|test", re.I)
NOT_A_SESSION = re.compile(
    r"pit ?walk|parade|autograph|podium|grid|ceremony|gt4|finish|end of|after \d", re.I
)
NOT_A_ROUND = re.compile(r"gala|media day|test days?\b|prologue|awards", re.I)
TIME = re.compile(r"(\d{1,2}):(\d{2})\s*([ap]\.?m\.?)?", re.I)
MONTHS = {
    name: index
    for index, name in enumerate(
        ["january", "february", "march", "april", "may", "june", "july", "august",
         "september", "october", "november", "december"],
        start=1,
    )
}
# Site flags use IOC codes for a few countries; the app expects ISO 3166.
IOC_TO_ISO = {
    "POR": "PRT", "GER": "DEU", "NED": "NLD", "SUI": "CHE", "RSA": "ZAF", "UAE": "ARE",
    "INA": "IDN", "MAL": "MYS", "DEN": "DNK", "GRE": "GRC", "CRO": "HRV", "KSA": "SAU",
    "PHI": "PHL", "CHI": "CHL", "URU": "URY", "LAT": "LVA", "BUL": "BGR", "SLO": "SVN",
    "TPE": "TWN", "ENG": "GBR", "SCO": "GBR", "WAL": "GBR", "NIR": "GBR",
}
CIRCUITS = (
    ("paul ricard", "Circuit Paul Ricard", "Le Castellet"),
    ("brands hatch", "Brands Hatch", "West Kingsdown"),
    ("monza", "Autodromo Nazionale di Monza", "Monza"),
    ("spa", "Circuit de Spa-Francorchamps", "Stavelot"),
    ("misano", "Misano World Circuit", "Misano Adriatico"),
    ("magny", "Circuit de Nevers Magny-Cours", "Magny-Cours"),
    ("nurburgring", "Nürburgring", "Nürburg"),
    ("zandvoort", "Circuit Park Zandvoort", "Zandvoort"),
    ("barcelona", "Circuit de Barcelona-Catalunya", "Montmeló"),
    ("portimao", "Algarve International Circuit", "Portimão"),
    ("sonoma", "Sonoma Raceway", "Sonoma"),
    ("circuit of the americas", "Circuit of the Americas", "Austin"),
    ("sebring", "Sebring International Raceway", "Sebring"),
    ("road atlanta", "Michelin Raceway Road Atlanta", "Braselton"),
    ("road america", "Road America", "Elkhart Lake"),
    ("barber", "Barber Motorsports Park", "Birmingham"),
    ("indianapolis", "Indianapolis Motor Speedway Road Course", "Indianapolis"),
    ("indy 8", "Indianapolis Motor Speedway Road Course", "Indianapolis"),
    ("miami", "Homestead-Miami Speedway", "Homestead"),
    ("sepang", "Sepang International Circuit", "Sepang"),
    ("mandalika", "Pertamina Mandalika International Circuit", "Lombok"),
    ("fuji", "Fuji Speedway", "Oyama"),
    ("okayama", "Okayama International Circuit", "Mimasaka"),
    ("beijing", "Beijing Street Circuit", "Beijing"),
    ("shanghai", "Shanghai International Circuit", "Shanghai"),
    ("phillip island", "Phillip Island Grand Prix Circuit", "Phillip Island"),
    ("the bend", "The Bend Motorsport Park", "Tailem Bend"),
    ("queensland", "Queensland Raceway", "Ipswich"),
    ("darwin", "Hidden Valley Raceway", "Darwin"),
    ("sydney", "Sydney Motorsport Park", "Eastern Creek"),
    ("adelaide", "Adelaide Street Circuit", "Adelaide"),
    ("bathurst", "Mount Panorama Circuit", "Bathurst"),
    ("suzuka", "Suzuka Circuit", "Suzuka"),
    ("silverstone", "Silverstone Circuit", "Silverstone"),
    ("oulton", "Oulton Park", "Little Budworth"),
    ("snetterton", "Snetterton Circuit", "Snetterton"),
    ("donington", "Donington Park", "Castle Donington"),
    ("kyalami", "Kyalami Grand Prix Circuit", "Midrand"),
)
BRAND_COLORS = (
    ("ferrari", "#DC0000"),
    ("porsche", "#D5001C"),
    ("bmw", "#0066B1"),
    ("mercedes", "#00A19C"),
    ("mclaren", "#FF8000"),
    ("aston", "#00665E"),
    ("lamborghini", "#C9A227"),
    ("audi", "#BB0A30"),
    ("ford", "#1F4E9C"),
    ("corvette", "#E8B500"),
    ("chevrolet", "#E8B500"),
    ("lexus", "#5B6770"),
    ("toyota", "#EB0A1E"),
    ("acura", "#7A1F2B"),
    ("honda", "#7A1F2B"),
    ("nissan", "#C3002F"),
    ("cadillac", "#8A8D91"),
)
CLASS_PATTERNS = (
    ("PRO-AM", r"pro[- ]?am"),
    ("SILVER-AM", r"silver[- ]?am"),
    ("PRO", r"\bpro\b"),
    ("GOLD", r"\bgold\b"),
    ("SILVER", r"\bsilver\b"),
    ("BRONZE", r"\bbronze\b"),
    ("TROPHY", r"\btrophy\b"),
    ("MASTERS", r"\bmasters\b"),
    ("AM", r"\bam\b"),
)
SKIPPED_STANDINGS = re.compile(r"academy|china cup|pit stop|gt4|independent|junior|youngster|rookie", re.I)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def get(url: str) -> str:
    # Event slugs contain characters such as "ü" (Nürburgring).
    safe_url = quote(url, safe=":/?&=%#+,;")
    raw = read(safe_url, {"User-Agent": USER_AGENT, "Accept": "text/html"}, timeout=40, attempts=4)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        # Some SRO pages are served in Windows-1252 despite the declared UTF-8.
        return raw.decode("cp1252", "replace")


def round_cups(base: str) -> dict[str, str]:
    """Event name -> cup, from the round headers of the overall standings.

    Event pages mention both cups in news teasers, but every standings
    column is labelled with the cup its round belongs to.
    """
    page = get(f"{base}/standings?filter_standing_type=0_0_drivers")
    cups = {}
    for name, cup in re.findall(r'<th colspan="\d+">([^<]+)<span class="cup">([^<]+)</span>', page):
        label = clean(cup)
        for option in ("Endurance Cup", "Sprint Cup"):
            if option.lower() in label.lower():
                cups[slugify(clean(name))] = option
    return cups


def clean(value: str) -> str:
    text = re.sub(r"<!--[\s\S]*?-->", " ", value)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html_lib.unescape(text)).strip()


def strip_scripts(page: str) -> str:
    return re.sub(r"<script[\s\S]*?</script>|<!--[\s\S]*?-->", " ", page)


def country_code(code: str | None) -> str | None:
    if not code:
        return None
    upper = code.upper()
    return IOC_TO_ISO.get(upper, upper)


# --------------------------------------------------------------------------
# Calendar and timetable
# --------------------------------------------------------------------------


def calendar_entries(page: str) -> list[dict[str, Any]]:
    """Championship rounds (test days, media days and galas are skipped)."""
    page = strip_scripts(page)
    starts = [m.start() for m in re.finditer(r'<li class="(?:past-events|calendar)__list-item', page)]
    entries: dict[str, dict[str, Any]] = {}
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(page)
        block = page[start:end]
        link = re.search(r'href="(/event/(\d+)/[^"]+)"', block)
        if not link:
            continue
        text = clean(block)
        if not re.search(r"\bRound\b", text, re.I):
            continue
        flag = re.search(r"flag (?:size--tiny )?([a-z]{3})\b|flag ([a-z]{3}) size", block)
        code = (flag.group(1) or flag.group(2)) if flag else None
        entries.setdefault(link.group(2), {"path": link.group(1), "eventId": link.group(2), "flag": code})
    return list(entries.values())


def parse_date_range(text: str) -> tuple[date, date]:
    """'10 - 12 April 2026', '30 July 2026 - 2 August 2026', '31 March 2026'."""
    parts = [part.strip() for part in text.split(" - ")]
    end = re.match(r"(\d{1,2}) ([A-Za-z]+) (\d{4})$", parts[-1])
    if not end:
        raise ValueError(f"Unrecognised date range: {text}")
    end_date = date(int(end.group(3)), MONTHS[end.group(2).lower()], int(end.group(1)))
    if len(parts) == 1:
        return end_date, end_date
    start = re.match(r"(\d{1,2})(?: ([A-Za-z]+))?(?: (\d{4}))?$", parts[0])
    if not start:
        raise ValueError(f"Unrecognised date range: {text}")
    month = MONTHS[start.group(2).lower()] if start.group(2) else end_date.month
    year = int(start.group(3)) if start.group(3) else end_date.year
    return date(year, month, int(start.group(1))), end_date


def event_header(page: str) -> tuple[str, str, date, date]:
    """Name, country and dates from '<title>Name, Country, Dates | Site</title>'."""
    title = re.search(r"<title>([^<]+)</title>", page)
    if not title:
        raise ValueError("Event page has no title")
    head = html_lib.unescape(title.group(1)).split(" | ")[0]
    name, country, dates = (part.strip() for part in head.rsplit(", ", 2))
    start, end = parse_date_range(dates)
    return name, country, start, end


def event_cup(page: str, name: str = "", cups: dict[str, str] | None = None) -> str | None:
    if cups and slugify(name) in cups:
        return cups[slugify(name)]
    # Sprint Cup weekends run two races; Endurance Cup rounds run one.
    if re.search(r"<td>\s*Race 2\s*</td>", page):
        return "Sprint Cup"
    counts = {cup: len(re.findall(cup, page, re.I)) for cup in ("Endurance Cup", "Sprint Cup")}
    best = max(counts, key=lambda cup: counts[cup])
    return best if counts[best] else None


def clock_minutes(text: str) -> int | None:
    """Minutes after midnight for '14:45', '04:00 pm' or '12:15 a.m.'."""
    match = TIME.match(text.strip())
    if not match:
        return None
    hours, minutes = int(match.group(1)), int(match.group(2))
    meridiem = (match.group(3) or "").lower().replace(".", "")
    if meridiem == "pm" and hours != 12:
        hours += 12
    elif meridiem == "am" and hours == 12:
        hours = 0
    return hours * 60 + minutes


def timetable_rows(page: str, start: date, end: date) -> list[dict[str, Any]]:
    """Sessions with their UTC start, track-local start and UTC offset."""
    rows: list[dict[str, Any]] = []
    section = page[page.find('class="timetable"'):] if 'class="timetable"' in page else ""
    for caption, body in re.findall(
        r'timetable__caption">\s*<span>([^<]+)</span>[\s\S]*?<tbody[^>]*>([\s\S]*?)</tbody>', section
    ):
        day = re.search(r"(\d{1,2}) ([A-Za-z]+)", caption)
        if not day:
            continue
        month = MONTHS[day.group(2).lower()]
        year = end.year if month >= start.month or start.year == end.year else start.year
        if start.year != end.year:
            year = start.year if month >= start.month else end.year
        session_day = date(year, month, int(day.group(1)))
        for cells in re.findall(r"<tr>([\s\S]*?)</tr>", body):
            values = [clean(cell) for cell in re.findall(r"<td[^>]*>([\s\S]*?)</td>", cells)]
            if len(values) < 3:
                continue
            name, local_text, gmt_text = values[0], values[1], values[2]
            local_minutes = clock_minutes(local_text)
            gmt_minutes = clock_minutes(gmt_text)
            if not name or local_minutes is None or gmt_minutes is None:
                continue
            offset = (local_minutes - gmt_minutes) % 1440
            if offset > 14 * 60:
                offset -= 1440
            local_start = datetime(session_day.year, session_day.month, session_day.day) + timedelta(
                minutes=local_minutes
            )
            rows.append(
                {
                    "name": name,
                    "utc": (local_start - timedelta(minutes=offset)).replace(tzinfo=timezone.utc),
                    "local": local_start,
                    "offset": offset,
                }
            )
    return rows


def is_session(name: str) -> bool:
    return bool(SESSION_WORDS.search(name)) and not NOT_A_SESSION.search(name)


def session_type(name: str) -> str:
    text = re.sub(r"\s+", " ", name).strip()
    patterns = (
        (r"^(?:free )?practice ?(\d*)$", "FP"),
        (r"^qualifying ?(\d*)$", "Q"),
        (r"^race ?(\d*)$", "R"),
    )
    for pattern, prefix in patterns:
        match = re.match(pattern, text, re.I)
        if match:
            return prefix + match.group(1)
    if re.fullmatch(r"main race", text, re.I):
        return "R"
    return re.sub(r"[^A-Z0-9]+", "_", text.upper()).strip("_")


def session_key(name: str) -> str:
    key = re.sub(r"[^a-z0-9]", "", name.lower())
    # "Free Practice 1" (results) and "Practice 1" (timetable) are one session,
    # as are "Main Race" (GTWC Europe) and "Race" (IGTC) on a shared weekend.
    key = re.sub(r"^mainrace", "race", key)
    return re.sub(r"^(?:free|official)practice", "practice", key)


def race_minutes(series: str, event_name: str, session_name: str) -> int:
    for text in (session_name, event_name):
        hours = re.search(r"(\d+)\s*(?:h|hr|hrs|hour|hours)\b", text, re.I)
        if hours and 1 <= int(hours.group(1)) <= 24:
            return int(hours.group(1)) * 60
        minutes = re.search(r"(\d+)\s*(?:min|mins|minutes)\b", text, re.I)
        if minutes:
            return int(minutes.group(1))
    if re.search(r"1000\s*km", event_name, re.I):
        return 360
    if re.search(r"\b500\b", event_name):
        return 180
    return int(SERIES[series]["race_minutes"])


def default_minutes(series: str, event_name: str, name: str) -> int:
    lower = name.lower()
    if "race" in lower:
        return race_minutes(series, event_name, name)
    if "combined" in lower:
        return 5
    if "group" in lower or "shootout" in lower or "superpole" in lower or "top" in lower:
        return 15
    if "qualif" in lower:
        return 20 if "pre" not in lower else 60
    if "bronze" in lower or "warm" in lower:
        return 30
    return 60


def build_sessions(series: str, event_name: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = sorted((row for row in rows if is_session(row["name"])), key=lambda row: row["utc"])
    sessions: list[dict[str, Any]] = []
    used: set[str] = set()
    for index, row in enumerate(rows):
        minutes = default_minutes(series, event_name, row["name"])
        if "race" not in row["name"].lower():
            # Back-to-back qualifying groups: a session ends when the next starts.
            later = [other["utc"] for other in rows[index + 1:] if other["utc"] > row["utc"]]
            if later:
                gap = int((later[0] - row["utc"]).total_seconds() // 60)
                minutes = max(5, min(minutes, gap))
        kind = session_type(row["name"])
        unique = kind
        suffix = 2
        while unique in used:
            unique = f"{kind}_{suffix}"
            suffix += 1
        used.add(unique)
        sign = "+" if row["offset"] >= 0 else "-"
        offset = abs(row["offset"])
        sessions.append(
            {
                "type": unique,
                "name": row["name"],
                "startTimeUtc": iso(row["utc"]),
                "startTimeTrack": row["local"].strftime("%Y-%m-%d %H:%M:%S")
                + f"{sign}{offset // 60:02d}:{offset % 60:02d}",
                "cancelled": False,
                "durationMinutes": minutes,
            }
        )
    return sessions


def circuit_for(name: str, country: str, code: str | None) -> dict[str, Any]:
    plain = slugify(name).replace("-", " ")
    for key, circuit, locality in CIRCUITS:
        if key in plain:
            return {
                "id": slugify(circuit),
                "name": circuit,
                "locality": locality,
                "country": country,
                "countryCode": code,
            }
    return {"id": slugify(name), "name": name, "locality": None, "country": country, "countryCode": code}


# --------------------------------------------------------------------------
# Results
# --------------------------------------------------------------------------


def result_links(page: str) -> list[tuple[str, str]]:
    """(session name, absolute path) pairs from a meeting results page.

    The session selector is preferred: some race links on the sites are
    broken (``/results/2026/sonoma-raceway/``) while the selector ids work.
    """
    links: list[tuple[str, str]] = []
    selector = page.find('id="filter_race_id"')
    meeting = re.search(r'name="filter_meeting_id"[\s\S]*?<option value="(\d+)"[^>]*selected', page)
    season = re.search(r'name="filter_season_id"[\s\S]*?<option value="(\d+)"[^>]*selected', page)
    if selector >= 0 and meeting and season:
        options = page[selector:page.find("</select>", selector)]
        for value, name in re.findall(r'<option value="(\d+)"[^>]*>([^<]+)', options):
            links.append(
                (
                    clean(name),
                    f"/results?filter_season_id={season.group(1)}&filter_meeting_id={meeting.group(1)}"
                    f"&filter_race_id={value}",
                )
            )
    if links:
        return links
    seen = set()
    for path, name in re.findall(r'<a href="(/results/\d{4}/[^"]+)">([^<]+)</a>', page):
        path = html_lib.unescape(path)
        if path not in seen and not path.endswith("/"):
            seen.add(path)
            links.append((clean(name), path))
    return links


def brand_color(car: str) -> str | None:
    lower = car.lower()
    for key, color in BRAND_COLORS:
        if key in lower:
            return color
    return None


def classification(page: str) -> list[dict[str, str]]:
    """Rows of the session table keyed by the lower-case column header."""
    table = re.search(r'<table class="table session">([\s\S]*?)</table>', page)
    if not table:
        return []
    headers = [clean(cell).lower() for cell in re.findall(r"<th[^>]*>([\s\S]*?)</th>", table.group(1))]
    body = re.search(r"<tbody[^>]*>([\s\S]*?)</tbody>", table.group(1))
    rows = []
    for row in re.findall(r"<tr[^>]*>([\s\S]*?)</tr>", body.group(1) if body else ""):
        cells = [clean(cell) for cell in re.findall(r"<td[^>]*>([\s\S]*?)</td>", row)]
        if len(cells) >= len(headers) and any(cells):
            rows.append(dict(zip(headers, cells)))
    return rows


def is_gt3_class(value: str) -> bool:
    return not re.search(r"\bgt4\b|\bgt2\b|\btcr?\b", value, re.I)


def result_rows(
    rows: list[dict[str, str]],
    race: bool,
    nationality: dict[str, str],
) -> list[dict[str, Any]]:
    results = []
    classified = [row for row in rows if is_gt3_class(row.get("class", ""))]
    for index, row in enumerate(classified, start=1):
        number = row.get("car #") or row.get("car") or row.get("no") or ""
        crew = [name.strip() for name in re.split(r",|/", row.get("drivers", "")) if name.strip()]
        team = row.get("team", "")
        car = row.get("car", "") if row.get("car #") else ""
        raw_position = row.get("pos", "")
        position = int(raw_position) if raw_position.isdigit() else None
        # Mixed GT3/GT4 grids: re-number the GT3 field.
        if position is not None:
            position = index if len(classified) != len(rows) else position
        laps_text = row.get("laps", "")
        laps = int(laps_text) if laps_text.isdigit() else None
        gap = row.get("gap", "").strip()
        best = (row.get("time") or row.get("best lap") or "").strip() or None
        if race:
            if position == 1:
                time = f"{laps} laps" if laps else best
            elif position is None:
                time = raw_position or "NC"
            else:
                time = gap if not gap or not re.match(r"^\d", gap) or "lap" in gap.lower() else f"+{gap}"
                time = time or best
        else:
            time = best
        components: dict[str, Any] = {"car": car}
        category = row.get("class", "").strip()
        if category:
            components["category"] = category
        if gap:
            components["gap"] = gap
        if best and race:
            components["bestLap"] = best
        nations = [nationality.get(slugify(name), "") for name in crew]
        results.append(
            {
                "position": position,
                "positionText": str(position) if position is not None else (raw_position or "NC"),
                "driver": {
                    "id": slugify("-".join(crew)) or f"car-{number}",
                    "code": number,
                    "givenName": " / ".join(crew),
                    "familyName": "",
                    "nationality": ",".join(code for code in nations if code) or None,
                },
                "team": {"id": slugify(team), "name": team, "color": brand_color(car)},
                "carNumber": number,
                "time": time,
                "laps": laps,
                "points": None,
                "status": category or None,
                "classified": position is not None,
                "components": components,
            }
        )
    return results


# --------------------------------------------------------------------------
# Natsoft classification PDFs (GTWC Australia, Bathurst 12 Hour)
# --------------------------------------------------------------------------

BRANDS = re.compile(
    r"^(Audi|Mercedes|Ferrari|Porsche|BMW|McLaren|Lamborghini|Aston|Ford|Chevrolet|Corvette|Lexus|"
    r"Nissan|Honda|Acura|Toyota|Bentley|Maserati|Callaway|Ginetta|Cadillac|Mustang)",
    re.I,
)
NATSOFT_ROW = re.compile(r"^(\d+|NC|DNF|DNS|DSQ|DQ|RET)\s+(\d+)\s+(.+)$")
CLOCK = re.compile(r"^(?:(\d+):)?(\d+):(\d+(?:\.\d+)?)\*?$")


def seconds(value: str) -> float | None:
    match = CLOCK.match(value)
    if not match:
        return None
    return int(match.group(1) or 0) * 3600 + int(match.group(2)) * 60 + float(match.group(3))


def full_name(abbreviated: str, known: dict[str, str]) -> str:
    """'B.Feeney' -> 'Broc Feeney' when one known driver matches."""
    match = re.match(r"^([A-Z])[a-z]?\.\s*(.+)$", abbreviated.strip())
    if not match:
        return abbreviated.strip()
    initial, surname = match.group(1), match.group(2)
    candidates = [
        name for slug, name in known.items()
        if slug.endswith("-" + slugify(surname)) and name[:1].upper() == initial
    ]
    return candidates[0] if len(candidates) == 1 else f"{initial}. {surname}"


def natsoft_classification(text: str, known: dict[str, str]) -> tuple[str, list[dict[str, str]]]:
    """Session title and rows from a Natsoft CLASSIFICATION page."""
    lines = [line.strip() for line in text.splitlines()]
    title = lines[2].split(" - ")[-1].strip() if len(lines) > 2 else ""
    race = "Race.Time" in text
    merged: list[str] = []
    for line in lines:
        if merged and merged[-1].endswith("/"):
            merged[-1] += line
        else:
            merged.append(line)
    rows = []
    for line in merged:
        match = NATSOFT_ROW.match(line)
        if not match:
            continue
        tokens = match.group(3).split()
        split = None
        for index in range(len(tokens) - 2, -1, -1):
            token = tokens[index]
            if re.fullmatch(r"[A-Z][A-Z-]{0,4}", token) and tokens[index + 1].isdigit():
                split = index
                break
        if split is None:
            continue
        body, category, tail = tokens[:split], tokens[split], tokens[split + 1:]
        drivers: list[str] = []
        team: list[str] = []
        vehicle: list[str] = []
        nation = re.search(r"\(([A-Z]{3})\)", " ".join(body))
        if nation:
            # Qualifying lists the driver who set the time: "Jayden Ojeda (AUS)".
            before = " ".join(body).split(nation.group(0))[0].strip()
            after = " ".join(body).split(nation.group(0), 1)[1].strip()
            name = next(
                (known_name for known_name in sorted(known.values(), key=len, reverse=True)
                 if before.endswith(known_name)),
                " ".join(before.split()[-2:]),
            )
            drivers = [name]
            team = [before[: len(before) - len(name)].strip()]
            vehicle = after.split()
        else:
            index = next((i for i, token in enumerate(body) if re.match(r"^[A-Z][a-z]?\.", token)), None)
            if index is None:
                continue
            end = index
            while end + 1 < len(body) and not BRANDS.match(body[end + 1]) and (
                "/" in body[end + 1] or body[end].endswith("/")
            ):
                end += 1
            team = body[:index]
            crew = " ".join(body[index:end + 1])
            drivers = [full_name(part, known) for part in crew.split("/") if part.strip()]
            vehicle = body[end + 1:]
        times = [token for token in tail[1:] if CLOCK.match(token)]
        rows.append(
            {
                "pos": match.group(1),
                "car #": match.group(2),
                "class": category,
                "drivers": ", ".join(drivers),
                "team": " ".join(team).strip(),
                "car": " ".join(vehicle),
                "laps": tail[0],
                "total": times[0] if race and times else "",
                "best lap": (times[-1] if race else times[0]).rstrip("*") if times else "",
            }
        )
    winner = rows[0] if rows else None
    if winner and winner.get("total"):
        lead = seconds(winner["total"]) or 0
        for row in rows[1:]:
            if not row["laps"].isdigit() or not winner["laps"].isdigit():
                continue
            down = int(winner["laps"]) - int(row["laps"])
            if down > 0:
                row["gap"] = f"{down} lap" + ("s" if down > 1 else "")
            elif row.get("total") and seconds(row["total"]) is not None:
                row["gap"] = f"+{seconds(row['total']) - lead:.3f}"
    elif rows:
        lead = seconds(rows[0]["best lap"])
        for row in rows[1:]:
            value = seconds(row["best lap"])
            if lead is not None and value is not None:
                row["gap"] = f"+{value - lead:.3f}"
    return title, rows


def pdf_text(url: str) -> str:
    import io

    import pdfplumber  # Lazy: only the PDF fallback needs it.

    raw = read(quote(url, safe=":/?&=%"), {"User-Agent": USER_AGENT}, timeout=60, attempts=3)
    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages[:4])


# --------------------------------------------------------------------------
# Standings and driver profiles
# --------------------------------------------------------------------------


def standing_class(label: str) -> str:
    lower = label.lower()
    for name, pattern in CLASS_PATTERNS:
        if re.search(pattern, lower):
            return name
    return "OVERALL"


def standing_options(page: str) -> list[tuple[str, str]]:
    start = page.find('id="filter_standing_type"')
    if start < 0:
        return []
    end = page.find("</select>", start)
    return [
        (value, clean(label))
        for value, label in re.findall(r'<option[^>]*value="([^"]+)"[^>]*>([^<]+)', page[start:end])
    ]


def standings_table(page: str) -> list[dict[str, Any]]:
    """Position, name, optional profile link and total from a standings page."""
    table = re.search(r'<table class="table standing[^"]*">([\s\S]*?)</table>', page)
    if not table:
        return []
    headers = [clean(cell).lower() for cell in re.findall(r"<th[^>]*>([\s\S]*?)</th>", table.group(1))]
    body = re.search(r"<tbody[^>]*>([\s\S]*?)</tbody>", table.group(1))
    total_index = headers.index("total") if "total" in headers else 2
    rows = []
    for row in re.findall(r"<tr[^>]*>([\s\S]*?)</tr>", body.group(1) if body else ""):
        raw_cells = re.findall(r"<td[^>]*>([\s\S]*?)</td>", row)
        cells = [clean(cell) for cell in raw_cells]
        if len(cells) < 3 or not cells[0].isdigit():
            continue
        link = re.search(r'href="(/driver/\d+/[^"]*)"', raw_cells[1])
        try:
            points = float(cells[total_index] or 0)
        except ValueError:
            continue
        rows.append(
            {
                "position": int(cells[0]),
                "name": cells[1],
                "profile": link.group(1) if link else None,
                "extra": cells[2] if total_index > 2 else "",
                "points": points,
            }
        )
    return rows


def driver_profile(base: str, profile: str) -> dict[str, str]:
    page = get(f"{base}{profile}")
    flag = re.search(r"profile__flag flag ([a-z]{3})", page)
    photo = re.search(r"(?:/|%2F)images(?:/|%2F)drivers(?:/|%2F)(photo_\d+\.\w+)", page)
    return {
        "nationality": country_code(flag.group(1)) if flag else "",
        "portraitSource": f"{base}/images/drivers/{photo.group(1)}" if photo else "",
    }


def split_name(name: str) -> tuple[str, str]:
    parts = name.split(" ", 1)
    return (parts[0], parts[1]) if len(parts) == 2 else (name, "")


FACES = "assets/portraits/faces/gt3"


def face_asset(slug: str) -> str | None:
    """Bundled, face-detected crop built by scripts/gt3_headshots.py."""
    path = f"{FACES}/{slug}.jpg"
    return path if (ROOT / path).is_file() else None


# --------------------------------------------------------------------------
# Series import
# --------------------------------------------------------------------------


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def write_json(path: Path, value: Any, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        if compact
        else json.dumps(value, ensure_ascii=False, indent=2)
    )
    path.write_text(text + "\n", encoding="utf-8")


def document(source: str, url: str, data: Any, updated: str) -> dict[str, Any]:
    return {"schemaVersion": 1, "lastSuccessfulUpdate": updated, "source": {"name": source, "url": url}, "data": data}


def known_profiles(data_root: Path) -> dict[str, dict[str, str]]:
    """Driver slug -> stored profile data across every GT3 series."""
    known: dict[str, dict[str, str]] = {}
    for series in SERIES:
        stored = load_json(data_root / series / str(SEASON) / "standings_drivers.json") or {}
        for driver in stored.get("data", []):
            slug = driver.get("id")
            if slug and (driver.get("nationality") or driver.get("portraitSource")):
                known.setdefault(
                    slug,
                    {
                        "nationality": driver.get("nationality", ""),
                        "portraitSource": driver.get("portraitSource", ""),
                        "profile": driver.get("profile", ""),
                    },
                )
    return known


def import_series(series: str, data_root: Path, pool: ThreadPoolExecutor) -> None:
    config = SERIES[series]
    base = config["base"]
    folder = data_root / series / str(SEASON)
    updated = iso(now_utc())
    profiles = known_profiles(data_root)
    nationality = {slug: info.get("nationality", "") for slug, info in profiles.items()}

    calendar_page = get(f"{base}/calendar")
    entries = calendar_entries(calendar_page)
    cups = round_cups(base) if config.get("cup") else {}
    event_pages = dict(zip(
        [entry["eventId"] for entry in entries],
        pool.map(lambda entry: get(base + entry["path"]), entries),
    ))
    events = []
    for entry in entries:
        page = strip_scripts(event_pages[entry["eventId"]])
        name, country, start, end = event_header(page)
        if NOT_A_ROUND.search(name):
            continue
        if config.get("cup") and event_cup(page, name, cups) != config["cup"]:
            continue
        # The URL slug can name the format ("indianpolis-8-hour") when the
        # page title only names the circuit.
        sessions = build_sessions(
            series, f"{name} {entry['path'].replace('-', ' ')}", timetable_rows(page, start, end)
        )
        if not sessions:
            # Timetable not published yet: keep the round on its final day.
            sessions = [
                {
                    "type": "R",
                    "name": "Race",
                    "startTimeUtc": iso(datetime(end.year, end.month, end.day, 12, tzinfo=timezone.utc)),
                    "cancelled": False,
                    "durationMinutes": race_minutes(series, name, "Race"),
                    "timeTbc": True,
                }
            ]
        results_link = re.search(r'href="(/results\?filter_season_id=\d+&(?:amp;)?filter_meeting_id=\d+)"', page)
        events.append(
            {
                "entry": entry,
                "name": name,
                "country": country,
                "start": start,
                "sessions": sessions,
                "resultsUrl": base + html_lib.unescape(results_link.group(1)) if results_link else None,
            }
        )
    if not events:
        raise RuntimeError(f"{series}: no championship rounds found")
    events.sort(key=lambda item: item["sessions"][0]["startTimeUtc"])

    # Standings first: their full names resolve abbreviated PDF crews.
    driver_pages, team_pages = standings_pages(series)
    standings_html = dict(zip(
        [url for url, _, _ in driver_pages + team_pages],
        pool.map(lambda page: get(page[0]), driver_pages + team_pages),
    ))
    known_names = {
        slugify(row["name"]): row["name"]
        for url, _, _ in driver_pages
        for row in standings_table(standings_html[url])
    }
    season_results: dict[str, str] = {}

    calendar = []
    race_winners: list[list[str]] = []
    team_wins: dict[str, int] = {}
    latest_crew: dict[str, dict[str, Any]] = {}
    now = now_utc()
    for round_number, item in enumerate(events, start=1):
        event_id = f"{series}-{SEASON}-{round_number}"
        results_path = f"events/{round_number:02d}-{slugify(item['name'])}.json"
        code = country_code(item["entry"]["flag"])
        calendar.append(
            {
                "id": event_id,
                "seriesId": series,
                "season": SEASON,
                "round": round_number,
                "name": item["name"],
                "cancelled": False,
                "circuit": circuit_for(item["name"], item["country"], code),
                "sessions": item["sessions"],
                "resultsPath": results_path,
            }
        )
        previous = load_json(folder / results_path) or {}
        previous_data = previous.get("data", {}) if previous.get("data", {}).get("eventId") == event_id else {}
        stored = {session["type"]: session for session in previous_data.get("sessions", [])}
        ended = {
            session["type"]: session
            for session in item["sessions"]
            if datetime.fromisoformat(session["startTimeUtc"].replace("Z", "+00:00"))
            + timedelta(minutes=session["durationMinutes"])
            <= now
        }
        imported = fetch_results(
            series, item, ended, stored, now, pool, nationality, known_names, season_results, data_root, calendar[-1]
        )
        sessions_out = []
        for session in item["sessions"]:
            kind = session["type"]
            chosen = imported.get(kind) or stored.get(kind)
            if chosen and chosen.get("results") and kind in ended:
                chosen["name"] = session["name"]
                chosen["startTimeUtc"] = session["startTimeUtc"]
                sessions_out.append(chosen)
        for session in sessions_out:
            for row in session["results"]:
                crew = [part.strip() for part in row["driver"]["givenName"].split(" / ") if part.strip()]
                for driver in crew:
                    latest_crew[slugify(driver)] = row
            if session["type"].startswith("R") and session["results"]:
                winner = session["results"][0]
                if winner.get("position") == 1:
                    race_winners.append(
                        [slugify(part) for part in winner["driver"]["givenName"].split(" / ")]
                    )
                    team_wins[winner["team"]["id"]] = team_wins.get(winner["team"]["id"], 0) + 1
        write_json(
            folder / results_path,
            document(
                "sro-official-results",
                item["resultsUrl"] or base,
                {"eventId": event_id, "sessions": sessions_out},
                updated,
            ),
            compact=True,
        )

    write_json(
        folder / "calendar.json",
        document("sro-official-calendar", f"{base}/calendar", calendar, updated),
    )
    write_standings(
        series, folder, pool, profiles, latest_crew, race_winners, team_wins, updated,
        driver_pages, team_pages, standings_html,
    )
    print(f"{series}: {len(calendar)} rounds")


def session_end(session: dict[str, Any]) -> datetime:
    return datetime.fromisoformat(session["startTimeUtc"].replace("Z", "+00:00")) + timedelta(
        minutes=session["durationMinutes"]
    )


def fetch_results(
    series: str,
    item: dict[str, Any],
    ended: dict[str, dict[str, Any]],
    stored: dict[str, dict[str, Any]],
    now: datetime,
    pool: ThreadPoolExecutor,
    nationality: dict[str, str],
    known_names: dict[str, str],
    season_results: dict[str, str],
    data_root: Path,
    event: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Fresh classifications for ended sessions that still need them.

    Sessions that ended more than three days ago and are already stored are
    final and are not downloaded again.
    """
    base = SERIES[series]["base"]

    def needed(kind: str, session: dict[str, Any]) -> bool:
        age = now - session_end(session)
        if stored.get(kind, {}).get("results"):
            return age < timedelta(days=3)  # provisional -> final updates
        # Some sessions (e.g. bronze-only practice) never get a classification:
        # stop asking after two weeks, except for a first import.
        return not stored or age < timedelta(days=14)

    due = {kind: session for kind, session in ended.items() if needed(kind, session)}
    if not due:
        return {}
    by_key = {session_key(session["name"]): kind for kind, session in due.items()}
    imported: dict[str, dict[str, Any]] = {}

    def store(kind: str, url: str, rows: list[dict[str, Any]], source: str = "sro-official-results") -> None:
        session = due[kind]
        imported[kind] = {
            "type": kind,
            "name": session["name"],
            "startTimeUtc": session["startTimeUtc"],
            "source": {"name": source, "url": url},
            "results": rows,
        }

    # 1. HTML classifications linked from the meeting results page.
    links: list[tuple[str, str]] = []
    if item["resultsUrl"]:
        try:
            links = result_links(get(item["resultsUrl"]))
        except Exception as error:  # keep previous classifications on outages
            print(f"{series} {item['name']}: results index failed ({error})", file=sys.stderr)
    jobs = [(by_key[session_key(name)], base + path) for name, path in links if session_key(name) in by_key]

    def download(job: tuple[str, str]) -> tuple[str, str, str | None]:
        kind, url = job
        try:
            return kind, url, get(url)
        except Exception as error:
            print(f"{series} {kind}: {error}", file=sys.stderr)
            return kind, url, None

    for kind, url, page in pool.map(download, jobs):
        if page:
            rows = result_rows(classification(page), kind.startswith("R"), nationality)
            if rows:
                store(kind, url, rows)

    # 2. Natsoft PDFs (GTWC Australia, Bathurst) on the event results page.
    if not links:
        if not season_results:
            try:
                index = get(f"{base}/results")
                for name, path in re.findall(r"<td>([^<]+)</td>\s*<td>[^<]*</td>\s*<td>\s*<a[^>]+href=\"(/results/\d{4}/[^\"]+)\"", index):
                    season_results[slugify(clean(name))] = path
            except Exception as error:
                print(f"{series}: season results failed ({error})", file=sys.stderr)
        path = season_results.get(slugify(item["name"]))
        pdfs: list[str] = []
        if path:
            try:
                page = get(base + html_lib.unescape(path))
                pdfs = [html_lib.unescape(link) for link in re.findall(r'href="(/images/results/[^"]+\.pdf)"', page, re.I)]
            except Exception as error:
                print(f"{series} {item['name']}: event results failed ({error})", file=sys.stderr)
        pdfs = [base + link for link in dict.fromkeys(pdfs)]

        def parse(url: str) -> tuple[str, str, list[dict[str, str]], bool]:
            try:
                text = pdf_text(url)
            except Exception as error:
                print(f"{series} pdf {url}: {error}", file=sys.stderr)
                return url, "", [], False
            title, rows = natsoft_classification(text, known_names)
            final = bool(re.search(r"F\s*I\s*N\s*A\s*L", text[:600]))
            return url, title, rows, final

        finals: set[str] = set()
        for url, title, rows, final in pool.map(parse, pdfs):
            kind = by_key.get(session_key(title))
            if not kind or not rows or (kind in finals and not final):
                continue
            store(kind, url, result_rows(rows, kind.startswith("R"), nationality), "natsoft-official-classification")
            if final:
                finals.add(kind)

    # 3. IGTC rounds shared with a GT World Challenge weekend (Spa, Indianapolis).
    if series == "igtc":
        missing = {key: kind for key, kind in by_key.items() if kind not in imported}
        for sibling in SERIES:
            if sibling == series or not missing:
                continue
            calendar = (load_json(data_root / sibling / str(SEASON) / "calendar.json") or {}).get("data", [])
            for other in calendar:
                if other["circuit"]["id"] != event["circuit"]["id"]:
                    continue
                gap = abs(
                    datetime.fromisoformat(other["sessions"][-1]["startTimeUtc"].replace("Z", "+00:00"))
                    - datetime.fromisoformat(event["sessions"][-1]["startTimeUtc"].replace("Z", "+00:00"))
                )
                if gap > timedelta(days=1):
                    continue
                document_ = load_json(data_root / sibling / str(SEASON) / other["resultsPath"]) or {}
                for session in document_.get("data", {}).get("sessions", []):
                    kind = missing.pop(session_key(session["name"]), None)
                    if kind and session.get("results"):
                        store(kind, session.get("source", {}).get("url", ""), session["results"])
    return imported


def standings_pages(series: str) -> tuple[list[tuple[str, str, str]], list[tuple[str, str, str]]]:
    """(url, class, label) lists for driver and team standings."""
    config = SERIES[series]
    base = config["base"]
    if series == "igtc":
        drivers = [(f"{base}/standings?filter_igtcstandingtype_id=2", "OVERALL", "Drivers")]
        teams = [(f"{base}/standings?filter_igtcstandingtype_id=4", "OVERALL", "GT3 Manufacturers")]
        return drivers, teams
    first = get(f"{base}/standings")
    options = standing_options(first)
    for value, _ in list(options):
        # Some sites only list the driver options on a drivers page.
        if value.endswith("_teams"):
            options += standing_options(get(f"{base}/standings?filter_standing_type={value[:-6]}_drivers"))
            break
    seen = set()
    drivers, teams = [], []
    for value, label in options:
        if value in seen or SKIPPED_STANDINGS.search(label):
            continue
        seen.add(value)
        if config.get("cup"):
            if config["cup"].lower() not in label.lower():
                continue
        elif re.search(r"endurance cup|sprint cup", label, re.I):
            continue
        url = f"{base}/standings?filter_standing_type={value}"
        target = drivers if value.endswith("_drivers") else teams if value.endswith("_teams") else None
        if target is not None:
            target.append((url, standing_class(label), label))
    return drivers, teams


def write_standings(
    series: str,
    folder: Path,
    pool: ThreadPoolExecutor,
    profiles: dict[str, dict[str, str]],
    latest_crew: dict[str, dict[str, Any]],
    race_winners: list[list[str]],
    team_wins: dict[str, int],
    updated: str,
    driver_pages: list[tuple[str, str, str]],
    team_pages: list[tuple[str, str, str]],
    pages: dict[str, str],
) -> None:
    base = SERIES[series]["base"]
    if not driver_pages:
        raise RuntimeError(f"{series}: no driver standings found")

    driver_rows = []
    seen_rows: set[tuple[str, str]] = set()
    for url, category, _ in driver_pages:
        for row in standings_table(pages[url]):
            # One row per driver and class, even if two tables share a class.
            key = (category, slugify(row["name"]))
            if key not in seen_rows:
                seen_rows.add(key)
                driver_rows.append((category, row))
    missing = sorted(
        {row["profile"] for _, row in driver_rows if row["profile"] and slugify(row["name"]) not in profiles}
    )

    def lookup(profile: str) -> tuple[str, dict[str, str] | None]:
        try:
            return profile, driver_profile(base, profile)
        except Exception as error:
            print(f"{series} driver {profile}: {error}", file=sys.stderr)
            return profile, None

    fetched = dict(pool.map(lookup, missing))
    wins: dict[str, int] = {}
    for crew in race_winners:
        for slug in crew:
            wins[slug] = wins.get(slug, 0) + 1

    drivers = []
    for category, row in driver_rows:
        slug = slugify(row["name"])
        info = dict(profiles.get(slug, {}))
        if row["profile"] and fetched.get(row["profile"]):
            info.update(fetched[row["profile"]])
            info["profile"] = f"{base}{row['profile']}"
        crew = latest_crew.get(slug)
        team_name = crew["team"]["name"] if crew else (row["extra"] if series == "igtc" else "")
        team_color = crew["team"]["color"] if crew else brand_color(row["extra"])
        given, family = split_name(row["name"])
        drivers.append(
            {
                "position": row["position"],
                "points": row["points"],
                "wins": wins.get(slug, 0) if category in ("OVERALL", "PRO") else 0,
                "id": slug,
                "code": crew["carNumber"] if crew else "",
                "givenName": given,
                "familyName": family,
                "nationality": info.get("nationality", ""),
                "teamIds": [slugify(team_name)] if team_name else [],
                "teamNames": [team_name] if team_name else [],
                "teamColors": [team_color] if team_color else [],
                "category": category,
                "imageUrl": face_asset(slug),
                "portraitSource": info.get("portraitSource", ""),
                "profile": info.get("profile", ""),
            }
        )
    teams = []
    seen_teams: set[tuple[str, str]] = set()
    for url, category, _ in team_pages:
        for row in standings_table(pages[url]):
            team_id = slugify(row["name"])
            if (category, team_id) in seen_teams:
                continue
            seen_teams.add((category, team_id))
            color = None
            for crew in latest_crew.values():
                if crew["team"]["id"] == team_id:
                    color = crew["team"]["color"]
                    break
            teams.append(
                {
                    "position": row["position"],
                    "points": row["points"],
                    "wins": team_wins.get(team_id, 0) if category == "OVERALL" else 0,
                    "id": team_id,
                    "name": row["name"],
                    "category": category,
                    "color": color or brand_color(row["name"]),
                }
            )
    if not drivers:
        raise RuntimeError(f"{series}: driver standings are empty")
    write_json(folder / "standings_drivers.json", document("sro-official-standings", f"{base}/standings", drivers, updated))
    write_json(folder / "standings_teams.json", document("sro-official-standings", f"{base}/standings", teams, updated))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--series", help="Comma-separated GT3 series ids (default: all)")
    args = parser.parse_args(argv)
    data_root = Path(os.environ.get("MOTORSPORT_DATA_ROOT", ROOT / "assets" / "data"))
    selected = [item.strip() for item in args.series.split(",")] if args.series else list(SERIES)
    failures = 0
    with ThreadPoolExecutor(max_workers=6) as pool:
        for series in SERIES:
            if series not in selected:
                continue
            try:
                import_series(series, data_root, pool)
            except Exception as error:
                failures += 1
                print(f"{series}: import failed ({error})", file=sys.stderr)
    return 1 if failures == len(selected) else 0


if __name__ == "__main__":
    raise SystemExit(main())
