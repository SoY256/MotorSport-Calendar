"""Copy official standings nationalities into stored F1/F2/F3 result rows."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "assets" / "data"
FALLBACK_COUNTRIES = {
    "ayumu iwasa": "Japanese", "colton herta": "American", "dino beganovic": "Swedish",
    "frederik vesti": "Danish", "jak crawford": "American", "leonardo fornaroli": "Italian",
    "luke browning": "British", "paul aron": "EST", "ryo hirakawa": "Japanese",
    "cian shields": "British", "emerson fittipaldi": "Brazilian", "john bennett": "British",
    "mari boya": "Spanish", "nico varrone": "ARG", "fernando barrichello": "Brazilian",
    "fionn mclaughlin": "Irish", "jose garfias": "Mexican", "nandhavud bhirombhakdi": "Thai",
    "patrick heuzenroeder": "Australian", "ricardo escotto": "Mexican", "salim hanna": "Colombian",
    "woohyun shin": "KOR",
}


def main() -> None:
    for series in ("f1", "f2", "f3"):
        root = ROOT / series / "2026"
        standings = json.loads((root / "standings_drivers.json").read_text(encoding="utf-8"))["data"]
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
