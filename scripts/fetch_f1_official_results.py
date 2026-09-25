"""Overlay F1 classifications from the official formula1.com results pages."""

from __future__ import annotations

import html
import json
import os
import re
from html.parser import HTMLParser
from datetime import datetime, timezone
from pathlib import Path

from http_retry import read

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("MOTORSPORT_DATA_ROOT", ROOT / "data"))
BASE = "https://www.formula1.com"
HEADERS = {"User-Agent": "MotorSport-Calendar/0.1 (+https://github.com/SoY256/MotorSport-Calendar)"}
ROUTES = {
    "FP1": "practice/1",
    "FP2": "practice/2",
    "FP3": "practice/3",
    "Q": "qualifying",
    "SQ": "sprint-shootout",
    "SPRINT": "sprint-results",
    "R": "race-result",
}


class Tables(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_table = self.in_row = self.in_cell = False
        self.cell: list[str] = []
        self.row: list[str] = []
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "table" and not self.rows:
            self.in_table = True
        elif self.in_table and tag == "tr":
            self.in_row = True
            self.row = []
        elif self.in_row and tag in {"td", "th"}:
            self.in_cell = True
            self.cell = []

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.in_cell and tag in {"td", "th"}:
            text = " ".join(" ".join(self.cell).replace("\xa0", " ").split())
            self.row.append(html.unescape(text))
            self.in_cell = False
        elif self.in_row and tag == "tr":
            if self.row:
                self.rows.append(self.row)
            self.in_row = False
        elif self.in_table and tag == "table":
            self.in_table = False


def fetch(url: str) -> str:
    return read(url, HEADERS, timeout=40).decode("utf-8", "replace")


def race_pages(year: int) -> dict[int, tuple[str, str]]:
    body = fetch(f"{BASE}/en/results/{year}/races")
    matches = re.findall(
        rf'/en/results/{year}/races/(\d+)/([^/"?]+)/race-result', body
    )
    unique: list[tuple[str, str]] = []
    for item in matches:
        if item not in unique:
            unique.append(item)
    return {index + 1: (race_id, slug) for index, (race_id, slug) in enumerate(unique)}


def metadata(root: Path) -> tuple[dict[str, dict], dict[str, dict]]:
    drivers = json.loads((root / "standings_drivers.json").read_text(encoding="utf-8"))["data"]
    by_code = {driver.get("code"): driver for driver in drivers if driver.get("code")}
    teams: dict[str, dict] = {}
    for event_path in (root / "events").glob("*.json"):
        event = json.loads(event_path.read_text(encoding="utf-8"))["data"]
        for session in event.get("sessions", []):
            for result in session.get("results", []):
                team = result.get("team", {})
                if team.get("name"):
                    teams[team["name"].casefold()] = team
    return by_code, teams


def official_rows(body: str, session_type: str, drivers: dict[str, dict], teams: dict[str, dict]) -> list[dict]:
    parser = Tables()
    parser.feed(body)
    rows: list[dict] = []
    for cells in parser.rows[1:]:
        if len(cells) < 5 or not cells[0].isdigit():
            continue
        position = int(cells[0])
        number = int(cells[1]) if cells[1].isdigit() else None
        words = cells[2].split()
        code = words[-1] if words and len(words[-1]) == 3 else None
        known = drivers.get(code or "", {})
        given = known.get("givenName") or (words[0] if words else "")
        family = known.get("familyName") or " ".join(words[1:-1])
        official_team = cells[3]
        team = teams.get(official_team.casefold(), {})
        if not team:
            aliases = {
                "red bull racing": "red bull",
                "racing bulls": "rb f1 team",
                "cadillac": "cadillac f1 team",
            }
            team = teams.get(aliases.get(official_team.casefold(), ""), {})

        if session_type in {"R", "SPRINT"}:
            laps = int(cells[4]) if cells[4].isdigit() else None
            result_time = cells[5] if len(cells) > 5 else None
            points_text = cells[-1] if cells[-1].replace(".", "", 1).isdigit() else None
            points = float(points_text) if points_text is not None else None
        elif session_type in {"Q", "SQ"}:
            candidates = [value for value in cells[4:] if re.match(r"^(?:\d+:)?\d+\.\d+$", value)]
            result_time = candidates[-1] if candidates else None
            laps = None
            points = None
        else:
            result_time = cells[4]
            laps = int(cells[5]) if len(cells) > 5 and cells[5].isdigit() else None
            points = None
        rows.append({
            "position": position,
            "positionText": str(position),
            "driver": {
                "id": known.get("id") or f"f1-{code or number}",
                "code": code,
                "givenName": given,
                "familyName": family,
                "nationality": known.get("nationality"),
            },
            "team": {
                "id": team.get("id"),
                "name": team.get("name") or official_team,
                "color": team.get("color"),
            },
            "carNumber": number,
            "time": result_time,
            "laps": laps,
            "points": points,
            "status": None,
            "classified": True,
            "components": {},
        })
    return rows


def official_standings(root: Path) -> None:
    driver_path = root / "standings_drivers.json"
    driver_document = json.loads(driver_path.read_text(encoding="utf-8"))
    drivers = {item.get("code"): item for item in driver_document["data"]}
    parser = Tables()
    parser.feed(fetch(f"{BASE}/en/results/2026/drivers"))
    ordered_drivers: list[dict] = []
    for cells in parser.rows[1:]:
        if len(cells) < 5 or not cells[0].isdigit():
            continue
        match = re.search(r"([A-Z]{3})$", cells[1])
        if not match or match.group(1) not in drivers:
            continue
        item = drivers[match.group(1)]
        item["position"] = int(cells[0])
        item["points"] = float(cells[4])
        ordered_drivers.append(item)
    if ordered_drivers:
        driver_document["data"] = ordered_drivers
        driver_document["source"] = {"name": "formula1-official", "url": f"{BASE}/en/results/2026/drivers"}
        driver_path.write_text(json.dumps(driver_document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    team_path = root / "standings_teams.json"
    team_document = json.loads(team_path.read_text(encoding="utf-8"))
    aliases = {
        "red bull racing": "red bull",
        "racing bulls": "rb f1 team",
        "cadillac": "cadillac f1 team",
        "alpine": "alpine f1 team",
    }
    teams = {item["name"].casefold(): item for item in team_document["data"]}
    bundled_team_path = ROOT / "assets" / "data" / "f1" / "2026" / "standings_teams.json"
    if bundled_team_path.is_file():
        for item in json.loads(bundled_team_path.read_text(encoding="utf-8"))["data"]:
            teams.setdefault(item["name"].casefold(), item)
    parser = Tables()
    parser.feed(fetch(f"{BASE}/en/results/2026/team"))
    ordered_teams: list[dict] = []
    for cells in parser.rows[1:]:
        if len(cells) < 3 or not cells[0].isdigit():
            continue
        key = cells[1].casefold()
        item = teams.get(key) or teams.get(aliases.get(key, ""))
        if item is None:
            continue
        item["position"] = int(cells[0])
        item["points"] = float(cells[2])
        ordered_teams.append(item)
    if ordered_teams:
        team_document["data"] = ordered_teams
        team_document["source"] = {"name": "formula1-official", "url": f"{BASE}/en/results/2026/team"}
        team_path.write_text(json.dumps(team_document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    root = DATA / "f1" / "2026"
    calendar = json.loads((root / "calendar.json").read_text(encoding="utf-8"))["data"]
    pages = race_pages(2026)
    drivers, teams = metadata(root)
    official_standings(root)
    for event in calendar:
        if event.get("round") is None or event.get("cancelled"):
            continue
        page = pages.get(int(event["round"]))
        if page is None:
            continue
        race_id, slug = page
        path = root / event["resultsPath"]
        document = json.loads(path.read_text(encoding="utf-8"))
        sessions = {session["type"]: session for session in document["data"].get("sessions", [])}
        changed = False
        for scheduled in event.get("sessions", []):
            session_type = scheduled["type"]
            route = ROUTES.get(session_type)
            if route is None:
                continue
            target = sessions.get(session_type)
            # Existing classifications have already been verified. During the
            # live weekend query only completed, still-missing sessions so the
            # five-minute job reaches F1 quickly and does not hammer old pages.
            if target is not None and target.get("results"):
                continue
            start = datetime.fromisoformat(
                scheduled["startTimeUtc"].replace("Z", "+00:00")
            )
            if start > datetime.now(timezone.utc):
                continue
            try:
                body = fetch(f"{BASE}/en/results/2026/races/{race_id}/{slug}/{route}")
            except RuntimeError:
                continue
            rows = official_rows(body, session_type, drivers, teams)
            if not rows:
                continue
            if target is None:
                target = {
                    "type": session_type,
                    "name": scheduled["name"],
                    "startTimeUtc": scheduled["startTimeUtc"],
                    "results": [],
                }
                document["data"].setdefault("sessions", []).append(target)
            target["results"] = rows
            changed = True
            print(f"{event['name']} {session_type}: {len(rows)} official rows")
        if changed:
            document["source"] = {"name": "formula1-official", "url": f"{BASE}/en/results/2026/races/{race_id}/{slug}/race-result"}
            path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
