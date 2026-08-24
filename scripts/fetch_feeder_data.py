"""Fetch the official 2026 Formula 2 and Formula 3 calendars and results."""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "data"
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


def slug(value: str) -> str:
    plain = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return "-".join(re.findall(r"[a-z0-9]+", plain))


def write(path: Path, data: object, url: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {"schemaVersion": 1, "lastSuccessfulUpdate": UPDATED, "source": {"name": "official-formula-series", "url": url}, "data": data}
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def page(url: str) -> str:
    with urlopen(Request(url, headers=HEADERS), timeout=45) as response:
        return response.read().decode("utf-8").replace('\\"', '"')


def session_objects(html: str) -> list[dict]:
    decoder = json.JSONDecoder()
    found: dict[str, dict] = {}
    for match in re.finditer(r'\{"session":"[^"]+","shortName":', html):
        try:
            item, _ = decoder.raw_decode(html[match.start():])
        except json.JSONDecodeError:
            continue
        # Prefer the occurrence that actually includes the classification.
        key = item.get("shortName", "")
        if key and (key not in found or len(item.get("results", [])) > len(found[key].get("results", []))):
            found[key] = item
    return list(found.values())


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
        "driver": {"id": slug(f"{raw.get('driverFirstName', '')}-{raw.get('driverLastName', '')}"), "code": raw.get("driverTLA"), "givenName": raw.get("driverFirstName"), "familyName": raw.get("driverLastName")},
        "team": {"id": slug(team_name), "name": team_name, "color": f"#{colour.lstrip('#')}"},
        "carNumber": raw.get("racingNumber"), "time": raw.get("displayTime") or raw.get("raceTime") or raw.get("gapToLeader"),
        "laps": int(raw["lapsCompleted"]) if str(raw.get("lapsCompleted", "")).isdigit() else None,
        "points": raw.get("racePoints"), "status": raw.get("completionStatusCode"), "classified": raw.get("completionStatusCode") == "OK", "components": {},
    }


def build(series: str) -> None:
    base = f"https://www.fiaformula{2 if series == 'f2' else 3}.com/en/racing/2026"
    events = []
    for number, row in enumerate(ROUNDS[series], 1):
        race_slug, name, circuit, locality, country, code, start, end = row
        url = f"{base}/{race_slug}"
        # The official page renders one selected classification at a time.
        # Merge all server-rendered session variants so Sprint and Feature
        # results are both stored offline.
        variants = [page(url)]
        if datetime.fromisoformat(end).replace(tzinfo=timezone.utc) < NOW:
            variants.extend(page(f"{url}?session={session}") for session in range(4))
        sessions_by_name: dict[str, dict] = {}
        for html in variants:
            for item in session_objects(html):
                key = item.get("shortName", "")
                if key and (key not in sessions_by_name or len(item.get("results", [])) > len(sessions_by_name[key].get("results", []))):
                    sessions_by_name[key] = item
        sessions = list(sessions_by_name.values())
        calendar_sessions, result_sessions = [], []
        for item in sessions:
            short = item.get("shortName", "")
            session_type = "R" if short == "Feature Race" else "SPRINT" if short == "Sprint Race" else "Q" if short == "Qualifying" else "FP1"
            stamp = utc(item, start)
            calendar_sessions.append({"type": session_type, "name": short or item.get("session", "Session"), "startTimeUtc": stamp, "startTimeTrack": item.get("startTime"), "trackTimeZone": item.get("timezone"), "cancelled": False})
            rows = [result_row(raw, index) for index, raw in enumerate(item.get("results", []), 1)]
            if rows:
                result_sessions.append({"type": session_type, "name": short, "startTimeUtc": stamp, "results": rows})
        if not calendar_sessions:
            calendar_sessions = [{"type": "R", "name": "Feature Race", "startTimeUtc": f"{end}T12:00:00Z", "cancelled": False}]
        filename = f"{number:02d}-{slug(name)}.json"
        event_id = f"{series}-2026-{number}"
        events.append({"id": event_id, "seriesId": series, "season": 2026, "round": number, "name": name, "cancelled": False,
                       "circuit": {"id": slug(circuit), "name": circuit, "locality": locality, "country": country, "countryCode": code},
                       "sessions": calendar_sessions, "resultsPath": f"events/{filename}"})
        write(OUT / series / "2026" / "events" / filename, {"eventId": event_id, "sessions": result_sessions}, url)
    write(OUT / series / "2026" / "calendar.json", events, base)

    drivers = []
    for pos, (given, family, nationality, team, points) in enumerate(DRIVERS[series], 1):
        drivers.append({"position": pos, "points": points, "wins": 0, "id": slug(f"{given}-{family}"), "code": "", "givenName": given, "familyName": family, "nationality": nationality, "teamIds": [team]})
    standings_url = f"https://www.fiaformula{2 if series == 'f2' else 3}.com/en/standings/2026/drivers"
    write(OUT / series / "2026" / "standings_drivers.json", drivers, standings_url)
    totals: dict[str, float] = {}
    for driver in drivers:
        team = driver["teamIds"][0]
        totals[team] = totals.get(team, 0) + driver["points"]
    teams = [{"position": pos, "points": points, "wins": 0, "id": team, "name": TEAM_NAMES[team], "nationality": None}
             for pos, (team, points) in enumerate(sorted(totals.items(), key=lambda item: item[1], reverse=True), 1)]
    write(OUT / series / "2026" / "standings_teams.json", teams, standings_url.replace("drivers", "teams"))


if __name__ == "__main__":
    build("f2")
    build("f3")
