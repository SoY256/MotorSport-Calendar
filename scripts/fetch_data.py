"""Build stable, versioned JSON data for the Flutter application."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import tempfile
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from http_retry import read
except ModuleNotFoundError:  # Imported as scripts.fetch_data by unit tests.
    from scripts.http_retry import read

SCHEMA_VERSION = 1
SOURCE_NAME = "jolpica-f1"
API_ROOT = "https://api.jolpi.ca"
USER_AGENT = "MotorSport-Calendar/0.1 (+https://github.com/SoY256/MotorSport-Calendar)"
SESSION_TYPES = {"FP1", "FP2", "FP3", "SQ", "SR", "S", "Q", "R"}


class DataValidationError(ValueError):
    """Raised when upstream data cannot be safely published."""


class JsonClient:
    def __init__(self, timeout: float = 20, retries: int = 3) -> None:
        self.timeout, self.retries = timeout, retries
        self._rate_lock = Lock()
        self._next_request = 0.0

    def _throttle(self) -> None:
        with self._rate_lock:
            delay = self._next_request - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            self._next_request = time.monotonic() + 0.4

    def get(self, url: str) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(self.retries):
            try:
                self._throttle()
                request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
                with urlopen(request, timeout=self.timeout) as response:
                    if response.status != 200:
                        raise DataValidationError(f"Unexpected HTTP status {response.status} for {url}")
                    payload = json.loads(response.read().decode("utf-8"))
                if not isinstance(payload, dict):
                    raise DataValidationError(f"Expected an object from {url}")
                return payload
            except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, DataValidationError) as error:
                last_error = error
                if attempt + 1 < self.retries:
                    retry_after = error.headers.get("Retry-After") if isinstance(error, HTTPError) else None
                    time.sleep(float(retry_after) if retry_after and retry_after.isdigit() else 2**attempt)
        raise RuntimeError(f"Failed to fetch {url} after {self.retries} attempts: {last_error}")


def utc_timestamp(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise DataValidationError("Session timestamp is missing")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise DataValidationError(f"Timestamp has no timezone: {value}")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return "-".join("".join(char if char.isalnum() else " " for char in normalized).split())


def require_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DataValidationError(f"{label} must be an object")
    return value


def adapt_schedule(payload: dict[str, Any], year: int) -> list[dict[str, Any]]:
    data = require_dict(payload.get("data"), "schedule.data")
    if data.get("year") != year or not isinstance(data.get("events"), list):
        raise DataValidationError("Schedule season or events are invalid")
    events: list[dict[str, Any]] = []
    for raw_event in data["events"]:
        raw_event = require_dict(raw_event, "schedule event")
        race = require_dict(raw_event.get("round"), "round")
        circuit = require_dict(raw_event.get("circuit"), "circuit")
        sessions = []
        for raw_session in raw_event.get("schedule", []):
            raw_session = require_dict(raw_session, "session")
            code = raw_session.get("code")
            if code not in SESSION_TYPES:
                continue
            sessions.append({
                "type": "SPRINT" if code in {"SR", "S"} else code,
                "name": raw_session.get("title") or code,
                "startTimeUtc": utc_timestamp(raw_session.get("timestamp")),
                "startTimeTrack": raw_session.get("local_timestamp"),
                "trackTimeZone": raw_session.get("timezone"),
                "cancelled": any(bool(item.get("is_cancelled")) for item in raw_session.get("sessions", [])),
            })
        if not sessions:
            raise DataValidationError(f"Event {race.get('name')} has no supported sessions")
        number, event_id, name = race.get("number"), race.get("id"), race.get("name")
        if not isinstance(number, int) and not race.get("is_cancelled"):
            raise DataValidationError(f"Active event {name} has no round number")
        if not all(isinstance(item, str) and item for item in (event_id, name, circuit.get("name"))):
            raise DataValidationError("Event identity is incomplete")
        results_filename = (f"{number:02d}-{slugify(name)}.json" if number
                            else f"cancelled-{slugify(name)}.json")
        events.append({
            "id": event_id, "seriesId": "f1", "season": year, "round": number, "name": name,
            "resultsPath": f"events/{results_filename}",
            "cancelled": bool(race.get("is_cancelled")),
            "circuit": {
                "id": circuit.get("id"), "name": circuit["name"], "locality": circuit.get("locality"),
                "country": circuit.get("country"), "countryCode": circuit.get("country_code"),
                "latitude": circuit.get("latitude"), "longitude": circuit.get("longitude"),
            },
            "sessions": sessions,
        })
    if not events:
        raise DataValidationError("Schedule contains no events")
    return sorted(events, key=lambda item: (item["round"] is None, item["round"] or 999))


def adapt_result(payload: dict[str, Any]) -> dict[str, Any]:
    data = require_dict(payload.get("data"), "result.data")
    code = data.get("code")
    if code not in SESSION_TYPES or not isinstance(data.get("results"), list):
        raise DataValidationError("Result session is invalid")
    results = []
    for raw in data["results"]:
        driver, team = require_dict(raw.get("driver"), "result.driver"), require_dict(raw.get("team"), "result.team")
        results.append({
            "position": raw.get("position"), "positionText": raw.get("position_text"),
            "driver": {"id": driver.get("id"), "code": driver.get("abbreviation"),
                       "givenName": driver.get("given_name"), "familyName": driver.get("family_name"),
                       "nationality": driver.get("country_code") or driver.get("nationality")},
            "team": {"id": team.get("id"), "name": team.get("name"), "color": team.get("primary_color")},
            "carNumber": raw.get("car_number"), "time": raw.get("time"), "laps": raw.get("laps"),
            "points": raw.get("points"), "status": raw.get("status"),
            "classified": raw.get("is_classified"), "components": raw.get("components", {}),
        })
    return {"type": "SPRINT" if code in {"SR", "S"} else code, "name": data.get("title") or code,
            "startTimeUtc": utc_timestamp(data.get("timestamp")), "results": results}


def adapt_standings(payload: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    try:
        lists = payload["MRData"]["StandingsTable"]["StandingsLists"]
        raw_items = lists[0]["DriverStandings" if kind == "drivers" else "ConstructorStandings"]
    except (KeyError, IndexError, TypeError) as error:
        raise DataValidationError(f"Invalid {kind} standings response") from error
    items = []
    for raw in raw_items:
        base = {"position": int(raw["position"]), "points": float(raw["points"]), "wins": int(raw["wins"])}
        if kind == "drivers":
            driver = raw["Driver"]
            base.update({"id": driver["driverId"], "code": driver.get("code"), "givenName": driver["givenName"],
                         "familyName": driver["familyName"], "nationality": driver.get("nationality"),
                         "teamIds": [team["constructorId"] for team in raw.get("Constructors", [])]})
        else:
            team = raw["Constructor"]
            base.update({"id": team["constructorId"], "name": team["name"], "nationality": team.get("nationality")})
        items.append(base)
    return items


def document(data: Any, updated: str, source_url: str) -> dict[str, Any]:
    return {"schemaVersion": SCHEMA_VERSION, "lastSuccessfulUpdate": updated,
            "source": {"name": SOURCE_NAME, "url": source_url}, "data": data}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def official_f1_portraits() -> dict[str, str]:
    html = read(
        "https://www.formula1.com/en/drivers",
        {"User-Agent": USER_AGENT, "Accept": "text/html"},
    ).decode("utf-8", "replace")
    portraits: dict[str, str] = {}
    for image, name in re.findall(
        r'<img src="([^"]+right\.webp)" alt="([^"]+)" role="presentation"',
        html,
        re.I,
    ):
        portraits[slugify(name)] = image.replace("&amp;", "&")
    return portraits


def build(client: JsonClient, output: Path, year: int) -> None:
    now = datetime.now(timezone.utc)
    updated = now.isoformat().replace("+00:00", "Z")
    schedule_url = f"{API_ROOT}/f1/alpha/schedules/{year}/"
    events = adapt_schedule(client.get(schedule_url), year)
    season_dir = output / "f1" / str(year)
    write_json(season_dir / "calendar.json", document(events, updated, schedule_url))
    results_by_event: dict[str, list[dict[str, Any]]] = {event["id"]: [] for event in events}
    for event in events:
        existing_path = season_dir / event["resultsPath"]
        if existing_path.is_file():
            try:
                existing = json.loads(existing_path.read_text(encoding="utf-8"))["data"]
                if existing.get("eventId") == event["id"] and isinstance(existing.get("sessions"), list):
                    results_by_event[event["id"]] = existing["sessions"]
            except (KeyError, TypeError, json.JSONDecodeError):
                pass
    jobs: dict[Any, tuple[str, str, bool]] = {}
    with ThreadPoolExecutor(max_workers=1) as pool:
        for event in events:
            for session in event["sessions"]:
                start = datetime.fromisoformat(session["startTimeUtc"].replace("Z", "+00:00"))
                if start > now or session["cancelled"]:
                    continue
                existing_session = next(
                    (item for item in results_by_event[event["id"]] if item.get("type") == session["type"]),
                    None,
                )
                # Historical classifications are immutable. Re-query only missing
                # sessions and the current live window, which avoids upstream rate
                # limits during the six-hour refresh.
                if existing_session is not None and start < now - timedelta(hours=12):
                    continue
                code = {"SPRINT": "SR"}.get(session["type"], session["type"])
                url = f"{API_ROOT}/f1/alpha/results/{event['id']}/{code}/"
                jobs[pool.submit(client.get, url)] = (event["id"], session["type"], existing_session is not None)
        for future in as_completed(jobs):
            event_id, session_type, had_existing = jobs[future]
            try:
                fresh = adapt_result(future.result())
                results_by_event[event_id] = [
                    item for item in results_by_event[event_id] if item.get("type") != session_type
                ] + [fresh]
            except RuntimeError as error:
                if not had_existing and "HTTP Error 404" not in str(error):
                    raise
    session_order = {code: index for index, code in enumerate(("FP1", "FP2", "FP3", "SQ", "SPRINT", "Q", "R"))}
    for event in events:
        session_results = sorted(results_by_event[event["id"]], key=lambda item: session_order[item["type"]])
        filename = (f"{event['round']:02d}-{slugify(event['name'])}.json" if event["round"]
                    else f"cancelled-{slugify(event['name'])}.json")
        write_json(season_dir / "events" / filename,
                   document({"eventId": event["id"], "sessions": session_results}, updated, schedule_url))
    portraits = official_f1_portraits()
    for kind, endpoint, filename in (
        ("drivers", "driverstandings", "standings_drivers.json"),
        ("teams", "constructorstandings", "standings_teams.json"),
    ):
        url = f"{API_ROOT}/ergast/f1/{year}/{endpoint}.json"
        standings = adapt_standings(client.get(url), kind)
        if kind == "drivers":
            for driver in standings:
                driver["imageUrl"] = portraits.get(
                    slugify(f"{driver['givenName']} {driver['familyName']}")
                )
        write_json(season_dir / filename, document(standings, updated, url))
    write_json(output / "series.json", document(
        [{"id": "f1", "name": "Formula 1", "shortName": "F1", "color": "#E10600"}], updated, schedule_url))
    write_json(output / "manifest.json", {
        "schemaVersion": SCHEMA_VERSION, "lastSuccessfulUpdate": updated,
        "source": {"name": SOURCE_NAME, "url": API_ROOT},
        "availableSeries": [{"id": "f1", "availableSeasons": [year]}],
    })


def publish(client: JsonClient, data_dir: Path, year: int) -> None:
    data_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="motorsport-data-", dir=data_dir.parent) as temp:
        staged = Path(temp) / "data"
        build(client, staged, year)
        backup = data_dir.with_name(f"{data_dir.name}.previous")
        if backup.exists():
            shutil.rmtree(backup)
        if data_dir.exists():
            data_dir.replace(backup)
        try:
            staged.replace(data_dir)
        except Exception:
            if backup.exists() and not data_dir.exists():
                backup.replace(data_dir)
            raise
        if backup.exists():
            shutil.rmtree(backup)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=datetime.now(timezone.utc).year)
    parser.add_argument("--output", type=Path, default=Path("data"))
    parser.add_argument("--timeout", type=float, default=20)
    parser.add_argument("--retries", type=int, default=3)
    args = parser.parse_args()
    try:
        publish(JsonClient(args.timeout, args.retries), args.output, args.year)
    except Exception as error:
        print(f"Data update failed; previous published data was preserved: {error}")
        return 1
    print(f"Published F1 {args.year} data to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
