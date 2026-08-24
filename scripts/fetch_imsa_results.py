"""Store completed 2026 IMSA classifications from official Alkamel JSON."""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urljoin
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://imsa.results.alkamelcloud.com/"
EVENTS = [
    "02_Daytona International Speedway", "06_Sebring International Raceway",
    "07_Long Beach Street Circuit", "09_Weathertech Raceway Laguna Seca",
    "11_Detroit Street Course", "14_Watkins Glen International",
    "15_Canadian Tire Motorsport Park", "16_Road America",
    "18_VIRginia International Raceway",
]
HEADERS = {"User-Agent": "MotorSport-Calendar/0.1 (+https://github.com/SoY256/MotorSport-Calendar)"}
MANUFACTURER_COLORS = {"Acura": "#E40521", "Aston Martin": "#006F62", "BMW": "#0066B1",
                       "Cadillac": "#D4AF37", "Chevrolet": "#F2C500", "Corvette": "#F2C500",
                       "Ferrari": "#E10600", "Ford": "#003478", "Lamborghini": "#DDB321",
                       "Lexus": "#222222", "Mercedes-AMG": "#00A19C", "Porsche": "#D5001C"}
TEAM_COLORS = {"Crowdstrike Racing by APR": "#E31B23", "Inter Europol Competition": "#C7D300",
               "AO Racing": "#E91E63", "United Autosports USA": "#0057B8",
               "Bryan Herta Autosport with PR1/Mathiasen": "#00A3E0", "Tower Motorsports": "#1E3A5F",
               "TDS Racing": "#D71920", "Pratt Miller Motorsports": "#F2C500", "Era Motorsport": "#1769AA",
               "Intersport Racing": "#F57C00", "JDC-Miller MotorSports": "#F2C500", "Af Corse Usa": "#E10600"}


def fetch(url: str) -> bytes:
    with urlopen(Request(url, headers=HEADERS), timeout=60) as response:
        return response.read()


def slug(value: str) -> str:
    plain = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return "-".join(re.findall(r"[a-z0-9]+", plain))


def result_url(event_code: str) -> str:
    html = fetch(f"{BASE}?season=26_2026&evvent={quote(event_code)}").decode("utf-8", "replace")
    hrefs = re.findall(r'href="([^"]+/\d{8,}_Race/(?:[^"/]+/)?03_Results_Race_[^"/]+\.JSON)"', html, re.I)
    if not hrefs:
        raise RuntimeError(f"No IMSA race JSON for {event_code}")
    weathertech = [href for href in hrefs if "WeatherTech" in href]
    if not weathertech:
        raise RuntimeError(f"No IMSA WeatherTech race JSON for {event_code}")
    official = [href for href in weathertech if "Unofficial" not in href]
    return urljoin(BASE, (official or weathertech)[-1])


def manufacturer_color(vehicle: str) -> str:
    return next((color for make, color in MANUFACTURER_COLORS.items() if make.lower() in vehicle.lower()), "#EF6C00")


def entrant_color(team: str, vehicle: str) -> str:
    return TEAM_COLORS.get(team, manufacturer_color(vehicle))


def main() -> None:
    root = ROOT / "assets" / "data" / "imsa" / "2026"
    calendar = json.loads((root / "calendar.json").read_text(encoding="utf-8"))["data"]
    updated = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    driver_countries: dict[str, str] = {}
    driver_teams: dict[str, tuple[str, str, str]] = {}
    car_teams: dict[tuple[str, str], tuple[str, str, str]] = {}
    driver_wins: dict[tuple[str, str], int] = {}
    team_wins: dict[tuple[str, str], int] = {}
    for event, event_code in zip(calendar, EVENTS):
        url = result_url(event_code)
        raw = json.loads(fetch(url).decode("utf-8-sig"))
        rows = []
        winning_classes: set[str] = set()
        for item in raw.get("classification", []):
            drivers = item.get("drivers") or []
            for driver in drivers:
                full_name = f"{driver.get('firstname', '')} {driver.get('surname', '')}".strip()
                if driver.get("country"):
                    driver_countries[full_name] = driver["country"]
            names = " / ".join(f"{driver.get('firstname', '')} {driver.get('surname', '')}".strip() for driver in drivers)
            team = item.get("team") or ""
            manufacturer = item.get("vehicle") or ""
            team_color = entrant_color(team, manufacturer)
            item_category = (item.get("class") or "").replace("GTDPRO", "GTD PRO")
            car_teams[(item_category, str(item.get("number") or ""))] = (slug(team), team, team_color)
            for driver in drivers:
                full_name = f"{driver.get('firstname', '')} {driver.get('surname', '')}".strip()
                driver_teams[full_name] = (slug(team), team, team_color)
            if item_category not in winning_classes:
                winning_classes.add(item_category)
                team_wins[(item_category, str(item.get("number") or ""))] = team_wins.get((item_category, str(item.get("number") or "")), 0) + 1
                for driver in drivers:
                    full_name = f"{driver.get('firstname', '')} {driver.get('surname', '')}".strip()
                    driver_wins[(item_category, full_name)] = driver_wins.get((item_category, full_name), 0) + 1
            rows.append({
                "position": item.get("position"), "positionText": str(item.get("position") or "–"),
                "driver": {"id": slug(names), "code": item.get("number"), "givenName": names, "familyName": "",
                           "nationality": ",".join(driver.get("country") for driver in drivers if driver.get("country")) or None},
                "team": {"id": slug(team), "name": team, "color": manufacturer_color(manufacturer)}, "carNumber": item.get("number"),
                "time": item.get("elapsed_time") or item.get("gap_first"),
                "laps": int(item["laps"]) if str(item.get("laps", "")).isdigit() else None,
                "points": None, "status": item.get("status"), "classified": not item.get("not_finished", False),
                "components": {"car": item.get("vehicle"), "category": (item.get("class") or "").replace("GTDPRO", "GTD PRO")},
            })
        if not rows:
            raise RuntimeError(f"No IMSA rows for {event_code}")
        payload = {"schemaVersion": 1, "lastSuccessfulUpdate": updated,
                   "source": {"name": "imsa-alkamel-official-timing", "url": url},
                   "data": {"eventId": event["id"], "sessions": [{"type": "R", "name": "Race", "startTimeUtc": event["sessions"][-1]["startTimeUtc"], "results": rows}]}}
        (root / event["resultsPath"]).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{event['name']}: {len(rows)}")

    standings_html = fetch(f"{BASE}?season=26_2026&evvent={quote(EVENTS[-1])}").decode("utf-8", "replace")
    for kind, pattern, filename in (
        ("drivers", r'href="([^"]+IWSC[^\"]+Drivers\.json)"', "standings_drivers.json"),
        ("teams", r'href="([^"]+IWSC[^\"]+Teams\.json)"', "standings_teams.json"),
    ):
        entries = []
        for href in dict.fromkeys(re.findall(pattern, standings_html, re.I)):
            source = json.loads(fetch(urljoin(BASE, href)).decode("utf-8-sig"))
            category = source.get("championship", {}).get("name", "").replace("IWSC ", "").replace(f" {kind.upper()}", "")
            for item in source.get("classification", []):
                name = item.get("key") or "Unknown"
                normalized_category = category.replace("GTDPRO", "GTD PRO")
                base = {"points": item.get("total_points", 0), "wins": driver_wins.get((normalized_category, name), 0) if kind == "drivers" else team_wins.get((normalized_category, str(name)), 0), "category": category}
                if kind == "drivers":
                    parts = name.rsplit(" ", 1)
                    team_id, team_name, team_color = driver_teams.get(name, ("", "", ""))
                    base.update({"id": slug(name), "code": "", "givenName": parts[0], "familyName": parts[-1] if len(parts) > 1 else "", "nationality": driver_countries.get(name), "teamIds": [team_id] if team_id else [], "teamNames": [team_name] if team_name else [], "teamColors": [team_color] if team_color else []})
                else:
                    team_id, team_name, team_color = car_teams.get((normalized_category, str(name)), (slug(name), name, "#607D8B"))
                    base.update({"id": team_id, "name": f"{team_name} · #{name}" if team_name != name else name, "color": team_color, "nationality": None})
                entries.append(base)
        entries.sort(key=lambda item: (item.get("category", ""), -float(item["points"])))
        category_positions: dict[str, int] = {}
        for item in entries:
            category = item["category"].replace("GTDPRO", "GTD PRO")
            item["category"] = category
            category_positions[category] = category_positions.get(category, 0) + 1
            item["position"] = category_positions[category]
        standings_doc = {"schemaVersion": 1, "lastSuccessfulUpdate": updated,
                         "source": {"name": "imsa-alkamel-official-points", "url": BASE}, "data": entries}
        (root / filename).write_text(json.dumps(standings_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
