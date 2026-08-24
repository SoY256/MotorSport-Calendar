"""Store completed 2026 INDYCAR race classifications from the official API."""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
API = "https://www.indycar.com/api/results"
SERIES_ID = "b856a4f1-e85c-4fac-8c36-fd58d962227a"
HEADERS = {"User-Agent": "MotorSport-Calendar/0.1 (+https://github.com/SoY256/MotorSport-Calendar)"}
DRIVER_COUNTRIES = {
    "alex-palou": "ESP", "kyle-kirkwood": "USA", "christian-lundgaard": "DNK", "david-malukas": "USA",
    "pato-o-ward": "MEX", "josef-newgarden": "USA", "marcus-ericsson": "SWE", "felix-rosenqvist": "SWE",
    "scott-mclaughlin": "NZL", "will-power": "AUS", "rinus-veekay": "NLD", "scott-dixon": "NZL",
    "kyffin-simpson": "CYM", "graham-rahal": "USA", "marcus-armstrong": "NZL", "alexander-rossi": "USA",
    "santino-ferrucci": "USA", "romain-grosjean": "FRA", "nolan-siegel": "USA", "louis-foster": "GBR",
    "dennis-hauger": "NOR", "christian-rasmussen": "DNK", "caio-collet": "BRA", "mick-schumacher": "DEU",
    "sting-ray-robb": "USA", "conor-daly": "USA", "takuma-sato": "JPN", "jack-harvey": "GBR",
    "jacob-abel": "USA", "helio-castroneves": "BRA", "ed-carpenter": "USA", "ryan-hunter-reay": "USA",
    "katherine-legge": "GBR",
}
TEAM_COLORS = {"chip-ganassi-racing": "#0B5BA7", "andretti-global": "#E31B23", "andretti-global-w-curb-agajanian": "#E31B23",
               "arrow-mclaren": "#FF6C0C", "team-penske": "#143B78", "meyer-shank-w-curb-agajanian": "#E91E63",
               "juncos-hollinger-racing": "#4A148C", "rahal-letterman-lanigan-racing": "#1F4E79",
               "a-j-foyt-enterprises": "#D71920", "ecr": "#00529B", "dale-coyne-racing": "#222222",
               "dreyer-reinbold-racing": "#C0A062", "abel-motorsports": "#111111", "hmd-motorsports-w-aj-foyt-racing": "#202A44"}


def get(url: str):
    with urlopen(Request(url, headers=HEADERS), timeout=45) as response:
        return json.loads(response.read().decode("utf-8"))


def slug(value: str) -> str:
    plain = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return "-".join(re.findall(r"[a-z0-9]+", plain))


def main() -> None:
    root = ROOT / "assets" / "data" / "indycar" / "2026"
    calendar_doc = json.loads((root / "calendar.json").read_text(encoding="utf-8"))
    official = get(f"{API}/SeasonDropDown?id={SERIES_ID}")
    season = next(item for item in official if item["Year"] == "2026")
    completed = list(reversed(season["Events"]))
    events = calendar_doc["data"]
    if len(completed) > len(events):
        raise RuntimeError("Official result count is larger than the app calendar")
    updated = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    driver_teams: dict[str, str] = {}
    for event, official_event in zip(events, completed):
        race = next(item for item in official_event["Sessions"] if item["SessionName"] == "Race")
        details = get(f"{API}/EventsSessionDetails?id={race['EventsSessionID']}")
        rows = []
        for raw in details.get("records", []):
            team = raw.get("TeamName") or ""
            driver_teams[raw.get("DriverName") or ""] = slug(team)
            rows.append({
                "position": raw.get("PositionFinish"), "positionText": str(raw.get("PositionFinish") or "–"),
                "driver": {"id": slug(raw.get("DriverName") or "driver"), "code": "", "givenName": raw.get("FirstName"), "familyName": raw.get("LastName"), "nationality": DRIVER_COUNTRIES.get(slug(raw.get("DriverName") or ""))},
                "team": {"id": slug(team), "name": team, "color": TEAM_COLORS.get(slug(team), "#D71920")},
                "carNumber": raw.get("CarNumber"), "time": raw.get("ElapsedTime") or raw.get("Difference"),
                "laps": raw.get("LapsComplete"), "points": raw.get("PointsEarned"), "status": raw.get("Status"),
                "classified": raw.get("Status") == "Running", "components": {},
            })
        if not rows:
            raise RuntimeError(f"No official records for {official_event['EventName']}")
        payload = {
            "schemaVersion": 1, "lastSuccessfulUpdate": updated,
            "source": {"name": "official-indycar", "url": f"{API}/EventsSessionDetails?id={race['EventsSessionID']}"},
            "data": {"eventId": event["id"], "sessions": [{"type": "R", "name": "Race", "startTimeUtc": event["sessions"][-1]["startTimeUtc"], "results": rows}]},
        }
        (root / event["resultsPath"]).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # INDYCAR publishes a drivers' championship, not a separate teams'
    # championship. For the app's team tab, aggregate the official driver
    # points by entrant instead of leaving the screen empty.
    point_summary = get(f"{API}/YearPointSummary?year=2026&id={SERIES_ID}")
    drivers = []
    for raw in point_summary.get("DriverList", []):
        name = raw.get("DriverName") or "Unknown"
        parts = name.rsplit(" ", 1)
        drivers.append({"position": raw.get("OverallPosition"), "points": raw.get("TotalPoints", 0),
                        "wins": raw.get("TotalWins", 0), "id": slug(name), "code": "",
                        "givenName": parts[0], "familyName": parts[-1] if len(parts) > 1 else "",
                        "nationality": DRIVER_COUNTRIES.get(slug(name)), "teamIds": [driver_teams[name]] if name in driver_teams else [],
                        "teamNames": [next((row["team"]["name"] for event in events if event.get("resultsPath") for row in json.loads((root / event["resultsPath"]).read_text(encoding="utf-8"))["data"]["sessions"][0]["results"] if row["driver"]["id"] == slug(name)), "")],
                        "teamColors": [TEAM_COLORS.get(driver_teams[name], "#607D8B")] if name in driver_teams else []})
    driver_doc = {"schemaVersion": 1, "lastSuccessfulUpdate": updated,
                  "source": {"name": "official-indycar", "url": f"{API}/YearPointSummary?year=2026&id={SERIES_ID}"},
                  "data": drivers}
    (root / "standings_drivers.json").write_text(json.dumps(driver_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    team_names = {team_id: next((name for name, value in driver_teams.items() if value == team_id), team_id) for team_id in set(driver_teams.values())}
    for event in events:
        if not event.get("resultsPath"): continue
        sessions = json.loads((root / event["resultsPath"]).read_text(encoding="utf-8"))["data"]["sessions"]
        if not sessions: continue
        for row in sessions[0]["results"]:
            team_names[row["team"]["id"]] = row["team"]["name"]
    totals: dict[str, float] = {}
    for driver in drivers:
        for team_id in driver.get("teamIds", []):
            totals[team_id] = totals.get(team_id, 0) + float(driver.get("points", 0))
    teams = [{"position": position, "points": points, "wins": 0, "id": team_id,
              "name": team_names.get(team_id, team_id.replace("-", " ").title()), "color": TEAM_COLORS.get(team_id, "#607D8B"), "nationality": None}
             for position, (team_id, points) in enumerate(sorted(totals.items(), key=lambda item: item[1], reverse=True), 1)]
    team_doc = {"schemaVersion": 1, "lastSuccessfulUpdate": updated,
                "source": {"name": "derived-from-official-indycar-driver-standings", "url": "https://www.indycar.com/standings/"},
                "data": teams}
    (root / "standings_teams.json").write_text(json.dumps(team_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
