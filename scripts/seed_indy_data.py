"""Publish 2026 INDYCAR and INDY NXT calendars and official driver standings."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPDATED = "2026-08-24T12:00:00Z"
SOURCE = "https://www.indycar.com/"

TRACKS = {
    "St. Petersburg": ("Streets of St. Petersburg", "St. Petersburg", "2026-03-01T17:00:00Z"),
    "Phoenix": ("Phoenix Raceway", "Avondale", "2026-03-07T20:00:00Z"),
    "Arlington": ("Streets of Arlington", "Arlington", "2026-03-15T17:30:00Z"),
    "Barber": ("Barber Motorsports Park", "Birmingham", "2026-03-29T17:00:00Z"),
    "Long Beach": ("Long Beach Street Circuit", "Long Beach", "2026-04-19T21:30:00Z"),
    "IMS Road": ("Indianapolis Motor Speedway Road Course", "Indianapolis", "2026-05-09T20:30:00Z"),
    "Indianapolis 500": ("Indianapolis Motor Speedway", "Indianapolis", "2026-05-24T14:00:00Z"),
    "Detroit": ("Detroit Street Circuit", "Detroit", "2026-05-31T16:30:00Z"),
    "WWTR": ("World Wide Technology Raceway", "Madison", "2026-06-08T01:00:00Z"),
    "Road America": ("Road America", "Elkhart Lake", "2026-06-21T18:00:00Z"),
    "Mid-Ohio": ("Mid-Ohio Sports Car Course", "Lexington", "2026-07-05T16:30:00Z"),
    "Nashville": ("Nashville Superspeedway", "Lebanon", "2026-07-19T19:00:00Z"),
    "Portland": ("Portland International Raceway", "Portland", "2026-08-09T20:00:00Z"),
    "Markham": ("Streets of Markham", "Markham", "2026-08-16T16:00:00Z"),
    "Washington": ("Streets of Washington, D.C.", "Washington", "2026-08-23T17:00:00Z"),
    "Milwaukee 1": ("Milwaukee Mile", "West Allis", "2026-08-29T18:30:00Z"),
    "Milwaukee 2": ("Milwaukee Mile", "West Allis", "2026-08-30T17:00:00Z"),
    "Laguna Seca": ("WeatherTech Raceway Laguna Seca", "Monterey", "2026-09-06T18:30:00Z"),
}

INDYCAR = ["St. Petersburg", "Phoenix", "Arlington", "Barber", "Long Beach", "IMS Road", "Indianapolis 500", "Detroit", "WWTR", "Road America", "Mid-Ohio", "Nashville", "Portland", "Markham", "Washington", "Milwaukee 1", "Milwaukee 2", "Laguna Seca"]
NXT = ["St. Petersburg", "Arlington", "Barber", "Barber", "IMS Road", "IMS Road", "Detroit", "WWTR", "Road America", "Road America", "Mid-Ohio", "Mid-Ohio", "Nashville", "Portland", "Milwaukee 2", "Laguna Seca", "Laguna Seca"]

INDYCAR_STANDINGS = [
    ("Alex", "Palou", 553, 6, "chip_ganassi", "Spanish"), ("Kyle", "Kirkwood", 462, 2, "andretti", "American"),
    ("Christian", "Lundgaard", 443, 2, "arrow_mclaren", "Danish"), ("David", "Malukas", 411, 0, "penske", "American"),
    ("Pato", "O'Ward", 399, 1, "arrow_mclaren", "Mexican"), ("Josef", "Newgarden", 352, 2, "penske", "American"),
    ("Scott", "McLaughlin", 345, 0, "penske", "New Zealander"), ("Felix", "Rosenqvist", 344, 1, "meyer_shank", "Swedish"),
    ("Marcus", "Ericsson", 329, 1, "andretti", "Swedish"), ("Rinus", "VeeKay", 295, 0, "juncos", "Dutch"),
]
NXT_STANDINGS = [
    ("Enzo", "Fittipaldi", 476, 4, "hmd", "Brazilian"), ("Nikita", "Johnson", 475, 2, "cape", "American"),
    ("Tymek", "Kucharczyk", 458, 1, "hmd", "Polish"), ("Max", "Taylor", 396, 1, "andretti", "American"),
    ("Lochie", "Hughes", 386, 1, "andretti", "Australian"), ("Alessandro", "de Tullio", 378, 2, "foyt", "American"),
    ("Myles", "Rowe", 344, 1, "abel", "American"), ("Jack", "Beeton", 316, 0, "hmd", "Australian"),
    ("Matteo", "Nannini", 307, 2, "cape", "Italian"), ("JM", "Correa", 299, 0, "cusick", "American"),
]

def doc(data, url=SOURCE):
    return {"schemaVersion": 1, "lastSuccessfulUpdate": UPDATED, "source": {"name": "official-indycar", "url": url}, "data": data}

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def publish(series_id, schedule, standings):
    root = ROOT / "data" / series_id / "2026"
    events = []
    occurrences = {}
    for round_no, key in enumerate(schedule, 1):
        circuit, locality, start = TRACKS[key]
        occurrences[key] = occurrences.get(key, 0) + 1
        if schedule.count(key) > 1:
            day_offset = occurrences[key] - 1
            stamp = start[:8] + f"{int(start[8:10]) + day_offset:02d}" + start[10:]
            name = f"{key.replace(' 2', '').replace(' 1', '')} Race {occurrences[key]}"
        else:
            stamp, name = start, key
        event_id = f"{series_id}-2026-{round_no}"
        filename = f"{round_no:02d}-race.json"
        events.append({"id": event_id, "seriesId": series_id, "season": 2026, "round": round_no, "name": name, "cancelled": False, "circuit": {"id": circuit.lower().replace(' ', '-'), "name": circuit, "locality": locality, "country": "United States" if locality != "Markham" else "Canada", "countryCode": "USA" if locality != "Markham" else "CAN"}, "sessions": [{"type": "R", "name": "Race", "startTimeUtc": stamp, "cancelled": False}], "resultsPath": f"events/{filename}"})
        write(root / "events" / filename, doc({"eventId": event_id, "sessions": []}))
    write(root / "calendar.json", doc(events))
    drivers = [{"position": i, "points": points, "wins": wins, "id": f"{given}-{family}".lower().replace(' ', '-'), "code": "", "givenName": given, "familyName": family, "nationality": nationality, "teamIds": [team]} for i, (given, family, points, wins, team, nationality) in enumerate(standings, 1)]
    write(root / "standings_drivers.json", doc(drivers, "https://www.indycar.com/standings/" if series_id == "indycar" else "https://www.indynxt.com/standings"))
    write(root / "standings_teams.json", doc([]))

publish("indycar", INDYCAR, INDYCAR_STANDINGS)
publish("indynxt", NXT, NXT_STANDINGS)

manifest = json.loads((ROOT / "data/manifest.json").read_text(encoding="utf-8"))
manifest["availableSeries"] = [{"id": i, "availableSeasons": [2026]} for i in ["f1", "imsa", "indycar", "indynxt", "wec"]]
write(ROOT / "data/manifest.json", manifest)
series = json.loads((ROOT / "data/series.json").read_text(encoding="utf-8"))
series["data"] = [
    {"id": "f1", "name": "Formula 1", "shortName": "F1", "color": "#E10600"},
    {"id": "imsa", "name": "IMSA WeatherTech", "shortName": "IMSA", "color": "#EF6C00"},
    {"id": "indycar", "name": "NTT INDYCAR SERIES", "shortName": "INDYCAR", "color": "#D71920"},
    {"id": "indynxt", "name": "INDY NXT by Firestone", "shortName": "INDY NXT", "color": "#E31837"},
    {"id": "wec", "name": "FIA World Endurance Championship", "shortName": "WEC", "color": "#00695C"},
]
write(ROOT / "data/series.json", series)
for name in ["manifest.json", "series.json"]:
    shutil.copy2(ROOT / "data" / name, ROOT / "assets/data" / name)
for series_id in ["indycar", "indynxt"]:
    target = ROOT / "assets/data" / series_id
    if target.exists(): shutil.rmtree(target)
    shutil.copytree(ROOT / "data" / series_id, target)
