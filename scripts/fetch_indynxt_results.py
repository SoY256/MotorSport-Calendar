"""Store completed 2026 INDY NXT classifications from the official API."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fetch_indycar_results import ROOT, get, slug

API = "https://www.indynxt.com/api/results"
SERIES_ID = "09341e09-3216-4f89-a45f-db697d72ee13"
DRIVER_COUNTRIES = {
    "enzo-fittipaldi": "BRA", "nikita-johnson": "USA", "tymek-kucharczyk": "POL", "max-taylor": "USA",
    "lochie-hughes": "AUS", "alessandro-de-tullio": "USA", "myles-rowe": "USA", "jack-beeton": "AUS",
    "matteo-nannini": "ITA", "jm-correa": "USA", "josh-pierson": "USA", "max-garcia": "USA",
    "seb-murray": "GBR", "salvador-de-alba": "MEX", "niels-koolen": "NLD", "bryce-aron": "USA",
    "jordan-missig": "USA", "nicolas-stati": "AUS", "colin-kaminsky": "USA", "james-roe": "IRL",
    "alexander-koreiba": "USA", "nicholas-monteiro": "BRA", "carson-etter": "USA", "ricardo-escotto": "MEX",
    "nolan-allaer": "USA", "jacob-abel": "USA", "bart-harrison": "USA", "yuven-sundaramoorthy": "USA",
}


def main() -> None:
    root = ROOT / "assets" / "data" / "indynxt" / "2026"
    calendar_doc = json.loads((root / "calendar.json").read_text(encoding="utf-8"))
    official = get(f"{API}/SeasonDropDown?id={SERIES_ID}")
    season = next(item for item in official if item["Year"] == "2026")
    completed = list(reversed(season["Events"]))
    events = calendar_doc["data"]
    updated = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    entrant_points: dict[str, float] = {}
    driver_teams: dict[str, str] = {}
    team_names: dict[str, str] = {}
    for event, official_event in zip(events, completed):
        race = next(item for item in official_event["Sessions"] if item["SessionName"] == "Race")
        details = get(f"{API}/EventsSessionDetails?id={race['EventsSessionID']}")
        rows = []
        for raw in details.get("records", []):
            team = raw.get("TeamName") or ""
            team_id = slug(team)
            driver_teams[raw.get("DriverName") or ""] = team_id
            team_names[team_id] = team
            entrant_points[team_id] = entrant_points.get(team_id, 0) + float(raw.get("PointsEarned") or 0)
            rows.append({
                "position": raw.get("PositionFinish"), "positionText": str(raw.get("PositionFinish") or "–"),
                "driver": {"id": slug(raw.get("DriverName") or "driver"), "code": "", "givenName": raw.get("FirstName"), "familyName": raw.get("LastName"), "nationality": DRIVER_COUNTRIES.get(slug(raw.get("DriverName") or ""))},
                "team": {"id": team_id, "name": team, "color": "#E31837"}, "carNumber": raw.get("CarNumber"),
                "time": raw.get("ElapsedTime") or raw.get("Difference"), "laps": raw.get("LapsComplete"),
                "points": raw.get("PointsEarned"), "status": raw.get("Status"), "classified": raw.get("Status") == "Running", "components": {},
            })
        if not rows:
            raise RuntimeError(f"No official records for {official_event['EventName']}")
        payload = {"schemaVersion": 1, "lastSuccessfulUpdate": updated,
                   "source": {"name": "official-indynxt", "url": f"{API}/EventsSessionDetails?id={race['EventsSessionID']}"},
                   "data": {"eventId": event["id"], "sessions": [{"type": "R", "name": "Race", "startTimeUtc": event["sessions"][-1]["startTimeUtc"], "results": rows}]}}
        (root / event["resultsPath"]).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    point_summary = get(f"{API}/YearPointSummary?year=2026&id={SERIES_ID}")
    drivers = []
    for raw in point_summary.get("DriverList", []):
        name = raw.get("DriverName") or "Unknown"
        parts = name.rsplit(" ", 1)
        drivers.append({"position": raw.get("OverallPosition"), "points": raw.get("TotalPoints", 0),
                        "wins": raw.get("TotalWins", 0), "id": slug(name), "code": "",
                        "givenName": parts[0], "familyName": parts[-1] if len(parts) > 1 else "",
                        "nationality": DRIVER_COUNTRIES.get(slug(name)), "teamIds": [driver_teams[name]] if name in driver_teams else [],
                        "teamNames": [team_names[driver_teams[name]]] if name in driver_teams else []})
    driver_doc = {"schemaVersion": 1, "lastSuccessfulUpdate": updated,
                  "source": {"name": "official-indynxt", "url": f"{API}/YearPointSummary?year=2026&id={SERIES_ID}"}, "data": drivers}
    (root / "standings_drivers.json").write_text(json.dumps(driver_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    teams = [{"position": position, "points": points, "wins": 0, "id": team_id,
              "name": team_names.get(team_id, team_id.replace("-", " ").title()), "nationality": None}
             for position, (team_id, points) in enumerate(sorted(entrant_points.items(), key=lambda item: item[1], reverse=True), 1)]
    team_doc = {"schemaVersion": 1, "lastSuccessfulUpdate": updated,
                "source": {"name": "derived-from-official-indynxt-results", "url": "https://www.indynxt.com/Results"}, "data": teams}
    (root / "standings_teams.json").write_text(json.dumps(team_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
