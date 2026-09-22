"""Fetch the official 2026 Formula 2 and Formula 3 calendars and results."""

from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from http_retry import read

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get("MOTORSPORT_DATA_ROOT", ROOT / "assets" / "data"))
NOW = datetime.now(timezone.utc)
UPDATED = NOW.isoformat().replace("+00:00", "Z")
HEADERS = {"User-Agent": "MotorSport-Calendar/0.1 (+https://github.com/SoY256/MotorSport-Calendar)"}

ROUNDS = {
    "f2": [
        ("melbourne", "Australian Grand Prix", "Albert Park Grand Prix Circuit", "Melbourne", "Australia", "AUS", "2026-03-06", "2026-03-08"),
        ("miami-gardens", "Miami Grand Prix", "Miami International Autodrome", "Miami", "United States", "USA", "2026-05-01", "2026-05-03"),
        ("montreal", "Canadian Grand Prix", "Circuit Gilles Villeneuve", "Montreal", "Canada", "CAN", "2026-05-22", "2026-05-24"),
        ("monte-carlo", "Monaco Grand Prix", "Circuit de Monaco", "Monte Carlo", "Monaco", "MCO", "2026-06-04", "2026-06-07"),
        ("barcelona", "Barcelona Grand Prix", "Circuit de Barcelona-Catalunya", "Barcelona", "Spain", "ESP", "2026-06-12", "2026-06-14"),
        ("spielberg", "Austrian Grand Prix", "Red Bull Ring", "Spielberg", "Austria", "AUT", "2026-06-26", "2026-06-28"),
        ("silverstone", "British Grand Prix", "Silverstone Circuit", "Silverstone", "United Kingdom", "GBR", "2026-07-03", "2026-07-05"),
        ("spa-francorchamps", "Belgian Grand Prix", "Circuit de Spa-Francorchamps", "Stavelot", "Belgium", "BEL", "2026-07-17", "2026-07-19"),
        ("budapest", "Hungarian Grand Prix", "Hungaroring", "Budapest", "Hungary", "HUN", "2026-07-24", "2026-07-26"),
        ("monza", "Italian Grand Prix", "Autodromo Nazionale di Monza", "Monza", "Italy", "ITA", "2026-09-04", "2026-09-06"),
        ("madrid", "Madrid Grand Prix", "Madring", "Madrid", "Spain", "ESP", "2026-09-11", "2026-09-13"),
        ("baku", "Azerbaijan Grand Prix", "Baku City Circuit", "Baku", "Azerbaijan", "AZE", "2026-09-24", "2026-09-26"),
        ("lusail", "Qatar Grand Prix", "Lusail International Circuit", "Lusail", "Qatar", "QAT", "2026-11-27", "2026-11-29"),
        ("yas-marina", "Abu Dhabi Grand Prix", "Yas Marina Circuit", "Abu Dhabi", "United Arab Emirates", "ARE", "2026-12-04", "2026-12-06"),
    ],
    "f3": [],
}
ROUNDS["f3"] = [row for row in ROUNDS["f2"] if row[0] in {
    "melbourne", "monte-carlo", "barcelona", "spielberg", "silverstone",
    "spa-francorchamps", "budapest", "monza", "madrid",
}]

DRIVERS = {
    "f2": [
        ("Nikola", "Tsolov", "Bulgarian", "campos", 167), ("Gabriele", "Mini", "Italian", "prema", 147),
        ("Rafael", "Câmara", "Brazilian", "invicta", 145), ("Alexander", "Dunne", "Irish", "rodin", 108),
        ("Noel", "Leon", "Mexican", "aix", 94), ("Kush", "Maini", "Indian", "dams", 88),
        ("Dino", "Beganovic", "Swedish", "hitech", 79), ("Laurens", "van Hoepen", "Dutch", "trident", 65),
        ("Martinius", "Stenshorne", "Norwegian", "rodin", 59), ("Tasanapol", "Inthraphuvasak", "Thai", "art", 59),
        ("Joshua", "Dürksen", "Paraguayan", "aix", 42), ("Rafael", "Villagomez", "Mexican", "van-amersfoort", 38),
        ("Ritomo", "Miyata", "Japanese", "art", 34), ("Oliver", "Goethe", "German", "mp", 29),
        ("Sebastian", "Montoya", "Colombian", "prema", 28), ("Colton", "Herta", "American", "hitech", 26),
        ("Roman", "Bilinski", "Polish", "dams", 24),
    ],
    "f3": [
        ("Freddie", "Slater", "British", "trident", 130), ("Ugo", "Ugochukwu", "American", "campos", 122),
        ("Théophile", "Naël", "French", "van-amersfoort", 75), ("Ernesto", "Rivera", "Mexican", "campos", 72),
        ("Brando", "Badoer", "Italian", "van-amersfoort", 71), ("Noah", "Stromsted", "Danish", "trident", 59),
        ("Hiyu", "Yamakoshi", "Japanese", "van-amersfoort", 55), ("Maciej", "Gladysz", "Polish", "art", 54),
        ("Bruno", "Del Pino", "Spanish", "mp", 49), ("Pedro", "Clerot", "Brazilian", "rodin", 48),
        ("Tuukka", "Taponen", "Finnish", "mp", 46), ("Taito", "Kato", "Japanese", "art", 45),
        ("Jin", "Nakamura", "Japanese", "hitech", 39), ("Mattia", "Colnaghi", "Italian", "mp", 39),
        ("James", "Wharton", "Australian", "art", 28), ("Enzo", "Deligny", "French", "rodin", 28),
        ("Louis", "Sharp", "New Zealander", "rodin", 21), ("Gerrard", "Xie", "Chinese", "dams", 20),
        ("Kanato", "Le", "Japanese", "hitech", 20), ("Alessandro", "Giusti", "French", "dams", 17),
        ("Yevan", "David", "Sri Lankan", "aix", 15), ("Matteo", "De Palo", "Italian", "trident", 7),
        ("Nicola", "Lacorte", "Italian", "prema", 6), ("Brad", "Benavides", "American", "aix", 6),
        ("Christian", "Ho", "Singaporean", "dams", 2),
    ],
}

TEAM_NAMES = {
    "campos": "Campos Racing", "prema": "PREMA Racing", "invicta": "Invicta Racing", "rodin": "Rodin Motorsport",
    "aix": "AIX Racing", "dams": "DAMS Lucas Oil", "hitech": "Hitech TGR", "trident": "Trident",
    "art": "ART Grand Prix", "van-amersfoort": "Van Amersfoort Racing", "mp": "MP Motorsport",
}
TEAM_COLOURS = {"campos": "#E5D100", "prema": "#E10600", "invicta": "#26A9E0", "rodin": "#F36F21", "aix": "#00A651", "dams": "#0067B1", "hitech": "#ED1C24", "trident": "#183883", "art": "#EE3124", "van-amersfoort": "#F58220", "mp": "#F15A29"}
DRIVER_NATIONALITIES = {f"{given} {family}": nationality for values in DRIVERS.values() for given, family, nationality, _, _ in values}


def slug(value: str) -> str:
    plain = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return "-".join(re.findall(r"[a-z0-9]+", plain))


def write(path: Path, data: object, url: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {"schemaVersion": 1, "lastSuccessfulUpdate": UPDATED, "source": {"name": "official-formula-series", "url": url}, "data": data}
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def page(url: str) -> str:
    return read(url, HEADERS, timeout=45).decode("utf-8").replace('\\"', '"')


def api_key(html: str) -> str:
    match = re.search(r'"key":\{"public":"([^"]+)"', html)
    if not match:
        raise RuntimeError("Official page does not expose the public results API key")
    return match.group(1)


def embedded_array(html: str, key: str) -> list[dict]:
    marker = f'"{key}":['
    start = html.find(marker)
    if start < 0:
        raise RuntimeError(f"Official page does not contain {key}")
    value, _ = json.JSONDecoder().raw_decode(html[start + len(marker) - 1:])
    if not isinstance(value, list):
        raise RuntimeError(f"Official {key} payload is not a list")
    return value


def official_portraits(series: str) -> dict[str, str]:
    number = 2 if series == "f2" else 3
    html = page(f"https://www.fiaformula{number}.com/en/drivers")
    portraits: dict[str, str] = {}
    pattern = r'href="/en/drivers/([^"]+)"[\s\S]*?<img src="([^"]+right\.webp)" alt="" role="presentation"'
    for profile, image in re.findall(pattern, html, re.I):
        portraits[slug(profile)] = image.replace("&amp;", "&")
    return portraits


def official_sessions(series: str, html: str) -> list[dict]:
    """Load every classification listed by the official race hub.

    The race page server-renders only the currently selected classification.
    The complete session list contains stable links to the same public API used
    by the page, so query each completed session explicitly instead of assuming
    that changing a page query parameter changes the server-rendered result.
    """
    key = api_key(html)
    sessions = embedded_array(html, "meetingSessions")
    loaded: list[dict] = []
    for session in sessions:
        item = dict(session)
        if item.get("state") != "completed":
            item["results"] = []
            loaded.append(item)
            continue
        value = str(item.get("value") or "")
        parsed = urlparse(value)
        query = parse_qs(parsed.query)
        meeting = query.get("meeting", [None])[0]
        number = query.get("session", [item.get("sessionNumber")])[0]
        kind = str(item.get("sessionType") or "").lower()
        if not meeting or not number or kind not in {"practice", "qualifying", "race"}:
            raise RuntimeError(f"Incomplete official session link: {value}")
        url = f"https://api.formula1.com/v2/core-fom-results/{series}/{kind}?meeting={meeting}&session={number}"
        payload = json.loads(read(url, {**HEADERS, "apikey": key}, timeout=45))
        official = payload.get("sessionResults")
        if not isinstance(official, dict):
            raise RuntimeError(f"Official API returned no classification for {value}")
        loaded.append(official)
    return loaded


def session_type(item: dict) -> str:
    short = str(item.get("shortName") or "")
    session = str(item.get("session") or "")
    if short == "Sprint Race":
        return "SPRINT"
    if short == "Feature Race":
        return "R"
    if short.startswith("Feature Race "):
        return f"R{short.rsplit(' ', 1)[-1]}"
    if "Qualifying" in short:
        number = re.search(r"(\d+)$", short)
        if number:
            return f"Q{number.group(1)}"
        if "Group A" in short:
            return "QA"
        if "Group B" in short:
            return "QB"
        return "Q"
    if "Practice" in short:
        return "FP1"
    raise RuntimeError(f"Unknown official session type: {short or session}")


def utc(session: dict, fallback_date: str) -> str:
    value = session.get("startTime") or f"{fallback_date}T12:00:00"
    offset = session.get("gmtOffset") or "+00:00"
    parsed = datetime.fromisoformat(value + offset)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def result_row(raw: dict, position: int) -> dict:
    team_name = raw.get("teamName") or ""
    colour = raw.get("teamColourCode") or "777777"
    return {
        "position": int(raw.get("positionNumber") or position), "positionText": raw.get("displayPosition") or str(position),
        "driver": {"id": slug(f"{raw.get('driverFirstName', '')}-{raw.get('driverLastName', '')}"), "code": raw.get("driverTLA"), "givenName": raw.get("driverFirstName"), "familyName": raw.get("driverLastName"), "nationality": raw.get("driverCountryCode") or raw.get("countryCode") or DRIVER_NATIONALITIES.get(f"{raw.get('driverFirstName', '')} {raw.get('driverLastName', '')}")},
        "team": {"id": slug(team_name), "name": team_name, "color": f"#{colour.lstrip('#')}"},
        "carNumber": raw.get("racingNumber"), "time": raw.get("displayTime") or raw.get("raceTime") or raw.get("gapToLeader"),
        "laps": int(raw["lapsCompleted"]) if str(raw.get("lapsCompleted", "")).isdigit() else None,
        "points": raw.get("racePoints"), "status": raw.get("completionStatusCode"), "classified": raw.get("completionStatusCode") == "OK", "components": {},
    }


def build(series: str) -> None:
    base = f"https://www.fiaformula{2 if series == 'f2' else 3}.com/en/racing/2026"
    events = []
    driver_metadata: dict[str, dict] = {}
    for number, row in enumerate(ROUNDS[series], 1):
        race_slug, name, circuit, locality, country, code, start, end = row
        url = f"{base}/{race_slug}"
        html = page(url)
        sessions = official_sessions(series, html)
        calendar_sessions, result_sessions = [], []
        for item in sessions:
            short = item.get("shortName", "")
            classification = session_type(item)
            stamp = utc(item, start)
            calendar_sessions.append({"type": classification, "name": short or item.get("session", "Session"), "startTimeUtc": stamp, "startTimeTrack": item.get("startTime"), "trackTimeZone": item.get("timezone"), "cancelled": False})
            rows = [result_row(raw, index) for index, raw in enumerate(item.get("results", []), 1)]
            for result in rows:
                driver_metadata[result["driver"]["id"]] = {
                    "nationality": result["driver"].get("nationality"),
                    "teamId": result["team"]["id"],
                    "code": result["driver"].get("code") or "",
                }
            if rows:
                result_sessions.append({"type": classification, "name": short, "startTimeUtc": stamp, "results": rows})
        if not calendar_sessions:
            calendar_sessions = [{"type": "R", "name": "Feature Race", "startTimeUtc": f"{end}T12:00:00Z", "cancelled": False}]
        filename = f"{number:02d}-{slug(name)}.json"
        event_id = f"{series}-2026-{number}"
        events.append({"id": event_id, "seriesId": series, "season": 2026, "round": number, "name": name, "cancelled": False,
                       "circuit": {"id": slug(circuit), "name": circuit, "locality": locality, "country": country, "countryCode": code},
                       "sessions": calendar_sessions, "resultsPath": f"events/{filename}"})
        write(OUT / series / "2026" / "events" / filename, {"eventId": event_id, "sessions": result_sessions}, url)
    write(OUT / series / "2026" / "calendar.json", events, base)

    standings_url = f"https://www.fiaformula{2 if series == 'f2' else 3}.com/en/standings/2026/drivers"
    portraits = official_portraits(series)
    raw_drivers = embedded_array(page(standings_url), "standings")
    drivers = []
    for raw in raw_drivers:
        given, family = raw.get("driverFirstName", ""), raw.get("driverLastName", "")
        driver_id = slug(f"{given}-{family}")
        metadata = driver_metadata.get(driver_id, {})
        drivers.append({
            "position": int(raw["displayPosition"]),
            "points": raw.get("championshipPoints", 0),
            "wins": 0,
            "id": driver_id,
            "code": raw.get("driverTLA") or metadata.get("code", ""),
            "givenName": given,
            "familyName": family,
            "nationality": metadata.get("nationality"),
            "teamIds": [metadata["teamId"]] if metadata.get("teamId") else [],
            "imageUrl": portraits.get(driver_id),
        })
    write(OUT / series / "2026" / "standings_drivers.json", drivers, standings_url)
    teams_url = standings_url.replace("drivers", "teams")
    raw_teams = embedded_array(page(teams_url), "standings")
    teams = [{
        "position": int(raw["displayPosition"]),
        "points": raw.get("championshipPoints", 0),
        "wins": 0,
        "id": slug(raw["teamName"]),
        "name": raw["teamName"],
        "nationality": None,
        "color": f"#{(raw.get('teamColourCode') or '777777').lstrip('#')}",
    } for raw in raw_teams]
    write(OUT / series / "2026" / "standings_teams.json", teams, teams_url)


if __name__ == "__main__":
    build("f2")
    build("f3")
