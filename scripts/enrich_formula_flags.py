"""Copy official standings nationalities into stored F1/F2/F3 result rows."""

from __future__ import annotations

import json
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
FALLBACK_COUNTRIES = {
    "ayumu iwasa": "Japanese", "colton herta": "American", "dino beganovic": "Swedish",
    "frederik vesti": "Danish", "jak crawford": "American", "leonardo fornaroli": "Italian",
    "luke browning": "British", "paul aron": "EST", "ryo hirakawa": "Japanese",
    "cian shields": "British", "emerson fittipaldi": "Brazilian", "john bennett": "British",
    "mari boya": "Spanish", "nico varrone": "ARG", "fernando barrichello": "Brazilian",
    "fionn mclaughlin": "Irish", "jose garfias": "Mexican", "nandhavud bhirombhakdi": "Thai",
    "patrick heuzenroeder": "Australian", "ricardo escotto": "Mexican", "salim hanna": "Colombian",
    "woohyun shin": "KOR",
    "alex powell": "Jamaican",
}


def main() -> None:
    for data_root in (PROJECT / "assets" / "data", PROJECT / "data"):
      for series in ("f1", "f2", "f3"):
        root = data_root / series / "2026"
        standings = json.loads((root / "standings_drivers.json").read_text(encoding="utf-8"))["data"]
        standings_changed = False
        for item in standings:
            full_name = f"{item.get('givenName', '')} {item.get('familyName', '')}".strip().casefold()
            if not item.get("nationality") and FALLBACK_COUNTRIES.get(full_name):
                item["nationality"] = FALLBACK_COUNTRIES[full_name]
                standings_changed = True
        if standings_changed:
            document = json.loads((root / "standings_drivers.json").read_text(encoding="utf-8"))
            document["data"] = standings
            (root / "standings_drivers.json").write_text(
                json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        countries = {item["id"]: item.get("nationality") for item in standings}
        countries.update({f"{item['givenName']} {item['familyName']}".casefold(): item.get("nationality") for item in standings})
        for path in (root / "events").glob("*.json"):
            document = json.loads(path.read_text(encoding="utf-8"))
            changed = False
            for session in document.get("data", {}).get("sessions", []):
                for result in session.get("results", []):
                    driver = result.get("driver", {})
                    full_name = f"{driver.get('givenName', '')} {driver.get('familyName', '')}".strip().casefold()
                    nationality = countries.get(driver.get("id")) or countries.get(full_name) or FALLBACK_COUNTRIES.get(full_name)
                    if nationality:
                        driver["nationality"] = nationality
                        changed = True
            if changed:
                path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
