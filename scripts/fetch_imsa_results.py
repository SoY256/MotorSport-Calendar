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
    official = [href for href in hrefs if "Unofficial" not in href]
    return urljoin(BASE, (official or hrefs)[-1])


def main() -> None:
    root = ROOT / "assets" / "data" / "imsa" / "2026"
    calendar = json.loads((root / "calendar.json").read_text(encoding="utf-8"))["data"]
    updated = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    for event, event_code in zip(calendar, EVENTS):
        url = result_url(event_code)
        raw = json.loads(fetch(url).decode("utf-8-sig"))
        rows = []
        for item in raw.get("classification", []):
            drivers = item.get("drivers") or []
            names = " / ".join(f"{driver.get('firstname', '')} {driver.get('surname', '')}".strip() for driver in drivers)
            team = item.get("team") or ""
            rows.append({
                "position": item.get("position"), "positionText": str(item.get("position") or "–"),
                "driver": {"id": slug(names), "code": item.get("number"), "givenName": names, "familyName": ""},
                "team": {"id": slug(team), "name": team, "color": "#EF6C00"}, "carNumber": item.get("number"),
                "time": item.get("elapsed_time") or item.get("gap_first"),
                "laps": int(item["laps"]) if str(item.get("laps", "")).isdigit() else None,
                "points": None, "status": item.get("status"), "classified": not item.get("not_finished", False),
                "components": {"car": item.get("vehicle"), "category": item.get("class")},
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
                base = {"points": item.get("total_points", 0), "wins": 0, "category": category}
                if kind == "drivers":
                    parts = name.rsplit(" ", 1)
                    base.update({"id": slug(name), "code": "", "givenName": parts[0], "familyName": parts[-1] if len(parts) > 1 else "", "nationality": None, "teamIds": []})
                else:
                    base.update({"id": slug(name), "name": name, "nationality": None})
                entries.append(base)
        entries.sort(key=lambda item: (item.get("category", ""), -float(item["points"])))
        category_positions: dict[str, int] = {}
        for item in entries:
            category = item.pop("category")
            category_positions[category] = category_positions.get(category, 0) + 1
            item["position"] = category_positions[category]
        standings_doc = {"schemaVersion": 1, "lastSuccessfulUpdate": updated,
                         "source": {"name": "imsa-alkamel-official-points", "url": BASE}, "data": entries}
        (root / filename).write_text(json.dumps(standings_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
