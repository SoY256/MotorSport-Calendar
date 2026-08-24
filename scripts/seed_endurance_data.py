"""Publish curated 2026 WEC and IMSA calendars from official championship schedules."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPDATED = "2026-08-24T10:00:00Z"

WEC = [
    (1, "6 Hours of Imola", "Imola Circuit", "Imola", "Italy", "ITA", "2026-04-19T11:00:00Z"),
    (2, "6 Hours of Spa-Francorchamps", "Circuit de Spa-Francorchamps", "Stavelot", "Belgium", "BEL", "2026-05-09T12:00:00Z"),
    (3, "24 Hours of Le Mans", "Circuit de la Sarthe", "Le Mans", "France", "FRA", "2026-06-13T14:00:00Z"),
    (4, "6 Hours of São Paulo", "Autódromo José Carlos Pace", "São Paulo", "Brazil", "BRA", "2026-07-12T14:30:00Z"),
    (5, "Lone Star Le Mans", "Circuit of the Americas", "Austin", "United States", "USA", "2026-09-06T17:00:00Z"),
    (6, "6 Hours of Fuji", "Fuji Speedway", "Oyama", "Japan", "JPN", "2026-09-27T02:00:00Z"),
    (7, "Qatar 1812 km", "Lusail International Circuit", "Lusail", "Qatar", "QAT", "2026-10-24T12:00:00Z"),
    (8, "8 Hours of Bahrain", "Bahrain International Circuit", "Sakhir", "Bahrain", "BHR", "2026-11-07T11:00:00Z"),
]

IMSA = [
    (1, "Rolex 24 at Daytona", "Daytona International Speedway", "Daytona Beach", "United States", "USA", "2026-01-24T18:40:00Z"),
    (2, "Twelve Hours of Sebring", "Sebring International Raceway", "Sebring", "United States", "USA", "2026-03-21T14:10:00Z"),
    (3, "Acura Grand Prix of Long Beach", "Long Beach Street Circuit", "Long Beach", "United States", "USA", "2026-04-18T20:00:00Z"),
    (4, "WeatherTech Raceway Laguna Seca", "WeatherTech Raceway Laguna Seca", "Monterey", "United States", "USA", "2026-05-03T19:00:00Z"),
    (5, "Detroit Sports Car Classic", "Detroit Street Circuit", "Detroit", "United States", "USA", "2026-05-30T19:00:00Z"),
    (6, "Six Hours of The Glen", "Watkins Glen International", "Watkins Glen", "United States", "USA", "2026-06-28T14:00:00Z"),
    (7, "Chevrolet Grand Prix", "Canadian Tire Motorsport Park", "Bowmanville", "Canada", "CAN", "2026-07-12T16:00:00Z"),
    (8, "Motul SportsCar Endurance Grand Prix", "Road America", "Elkhart Lake", "United States", "USA", "2026-08-02T16:00:00Z"),
    (9, "Michelin GT Challenge at VIR", "Virginia International Raceway", "Alton", "United States", "USA", "2026-08-23T16:10:00Z"),
    (10, "Battle on the Bricks", "Indianapolis Motor Speedway", "Indianapolis", "United States", "USA", "2026-09-20T19:00:00Z"),
    (11, "Motul Petit Le Mans", "Michelin Raceway Road Atlanta", "Braselton", "United States", "USA", "2026-10-03T16:00:00Z"),
]

WEC_DRIVERS = [
    (1, 75, "René", "Rast", "German", "bmw"),
    (1, 75, "Robin", "Frijns", "Dutch", "bmw"),
    (1, 75, "Kamui", "Kobayashi", "Japanese", "toyota"),
    (1, 75, "Mike", "Conway", "British", "toyota"),
    (1, 75, "Nyck", "de Vries", "Dutch", "toyota"),
    (3, 65, "Sheldon", "van der Linde", "South African", "bmw"),
]
WEC_TEAMS = [
    (1, 132, "toyota", "Toyota"),
    (2, 127, "bmw", "BMW"),
    (3, 88, "ferrari", "Ferrari"),
    (4, 60, "cadillac", "Cadillac"),
    (5, 41, "alpine", "Alpine"),
    (6, 40, "aston_martin", "Aston Martin"),
    (7, 15, "peugeot", "Peugeot"),
    (8, 6, "genesis", "Genesis"),
]
IMSA_DRIVERS = [
    (1, 2142, "Connor", "De Phillippi", "American", "bmw"),
    (1, 2142, "Neil", "Verhagen", "American", "bmw"),
    (2, 2127, "Nicky", "Catsburg", "Dutch", "corvette"),
    (2, 2127, "Tommy", "Milner", "American", "corvette"),
    (3, 2121, "Harry", "King", "British", "porsche"),
    (3, 2121, "Nick", "Tandy", "British", "porsche"),
]
IMSA_TEAMS = [
    (1, 2142, "bmw", "BMW M Team RLL"),
    (2, 2127, "corvette", "Corvette Racing"),
    (3, 2121, "porsche", "Porsche Penske Motorsport"),
]


def write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def document(data, source_url: str) -> dict:
    return {
        "schemaVersion": 1,
        "lastSuccessfulUpdate": UPDATED,
        "source": {"name": "official-championship", "url": source_url},
        "data": data,
    }


def publish_series(series_id: str, events: list[tuple], source_url: str, drivers: list[tuple], teams: list[tuple]) -> None:
    root = ROOT / "data" / series_id / "2026"
    calendar = []
    for round_number, name, circuit, locality, country, code, start in events:
        slug = f"{round_number:02d}-{name.lower().replace(' ', '-').replace('ã', 'a')}"
        event_id = f"{series_id}-2026-{round_number}"
        session = {"type": "R", "name": "Race", "startTimeUtc": start, "cancelled": False}
        calendar.append({
            "id": event_id,
            "seriesId": series_id,
            "season": 2026,
            "round": round_number,
            "name": name,
            "cancelled": False,
            "circuit": {"id": circuit.lower().replace(" ", "-"), "name": circuit, "locality": locality, "country": country, "countryCode": code},
            "sessions": [session],
            "resultsPath": f"events/{slug}.json",
        })
        write(root / "events" / f"{slug}.json", document({"eventId": event_id, "sessions": []}, source_url))
    write(root / "calendar.json", document(calendar, source_url))
    driver_rows = [{
        "position": pos, "points": points, "wins": 0,
        "id": f"{given}-{family}".lower().replace(" ", "-"), "code": "",
        "givenName": given, "familyName": family, "nationality": nationality,
        "teamIds": [team_id],
    } for pos, points, given, family, nationality, team_id in drivers]
    team_rows = [{"position": pos, "points": points, "wins": 0, "id": team_id, "name": name} for pos, points, team_id, name in teams]
    write(root / "standings_drivers.json", document(driver_rows, source_url))
    write(root / "standings_teams.json", document(team_rows, source_url))


def update_indexes() -> None:
    manifest_path = ROOT / "data" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["availableSeries"] = [
        {"id": "f1", "availableSeasons": [2026]},
        {"id": "imsa", "availableSeasons": [2026]},
        {"id": "wec", "availableSeasons": [2026]},
    ]
    write(manifest_path, manifest)
    series_path = ROOT / "data" / "series.json"
    series = json.loads(series_path.read_text(encoding="utf-8"))
    series["data"] = [
        {"id": "f1", "name": "Formula 1", "shortName": "F1", "color": "#E10600"},
        {"id": "imsa", "name": "IMSA WeatherTech", "shortName": "IMSA", "color": "#EF6C00"},
        {"id": "wec", "name": "FIA World Endurance Championship", "shortName": "WEC", "color": "#00695C"},
    ]
    write(series_path, series)


if __name__ == "__main__":
    publish_series("wec", WEC, "https://www.fiawec.com/en/season/2026", WEC_DRIVERS, WEC_TEAMS)
    publish_series("imsa", IMSA, "https://www.imsa.com/weathertech/weathertech-2026-schedule/", IMSA_DRIVERS, IMSA_TEAMS)
    update_indexes()
