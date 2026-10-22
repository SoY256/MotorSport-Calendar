"""Compare curated calendars with the official published schedules.

F1 is rebuilt from Jolpica on every refresh, but the F2/F3, WEC, IMSA and
INDYCAR/INDY NXT calendars are curated by hand.  Promoters do cancel, move
and add rounds mid-season (WEC replaced Qatar/Bahrain with Barcelona/Monza in
2026), so this script is run once per day to flag any upcoming difference
between ``data/<series>/<season>/calendar.json`` and the official schedule.

Exit codes: 0 everything matches, 1 differences found, 2 a source could not
be checked (and no differences were found in the sources that could).
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from http_retry import read

ROOT = Path(__file__).resolve().parents[1]
HEADERS = {
    "User-Agent": "MotorSport-Calendar/0.1 (+https://github.com/SoY256/MotorSport-Calendar)",
    # imsa.com intermittently answers 403 to requests without an Accept header.
    "Accept": "text/html,application/xhtml+xml",
}
ISSUE_TITLE = "Official schedule changed"
PAIRING_WINDOW_DAYS = 10
MONTHS = {name: number for number, name in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}
MONTH_PATTERN = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?"
COUNTRY_CODES = {
    "Abu Dhabi": "ARE", "Australia": "AUS", "Austria": "AUT", "Azerbaijan": "AZE", "Bahrain": "BHR",
    "Belgium": "BEL", "Brazil": "BRA", "Canada": "CAN", "China": "CHN", "France": "FRA",
    "Germany": "DEU", "Great Britain": "GBR", "Hungary": "HUN", "Italy": "ITA", "Japan": "JPN",
    "Mexico": "MEX", "Monaco": "MCO", "Netherlands": "NLD", "Portugal": "PRT", "Qatar": "QAT",
    "Saudi Arabia": "SAU", "Singapore": "SGP", "Spain": "ESP", "Turkey": "TUR",
    "United Arab Emirates": "ARE", "United Kingdom": "GBR", "United States of America": "USA",
    "United States": "USA", "USA": "USA",
}


class ParseError(RuntimeError):
    """The official page no longer looks like the markup the parser expects."""


@dataclass(frozen=True)
class OfficialEvent:
    name: str
    key: str
    date: date


@dataclass(frozen=True)
class CalendarEvent:
    name: str
    key: str
    date: date
    cancelled: bool = False


@dataclass(frozen=True)
class Source:
    series: str
    label: str
    url: str
    parse: Callable[[str, int], list[OfficialEvent]]
    key: Callable[[dict], str]
    tolerance_days: int = 1


def page_text(html: str) -> str:
    text = re.sub(r"<(script|style)\b.*?</\1>", " ", html, flags=re.S | re.I)
    text = html_lib.unescape(re.sub(r"<[^>]+>", " ", text))
    return re.sub(r"\s+", " ", text).strip()


def month_number(value: str) -> int:
    try:
        return MONTHS[value.strip(". ").lower()[:3]]
    except KeyError as error:
        raise ParseError(f"Unknown month {value!r}") from error


def venue_key(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.lower()))


def country_code(text: str) -> str:
    """Longest country name that starts ``text`` (``"United Arab Emirates Yas..."``)."""
    for name in sorted(COUNTRY_CODES, key=len, reverse=True):
        if re.match(rf"{re.escape(name)}\b", text, re.I):
            return COUNTRY_CODES[name]
    raise ParseError(f"Unknown country in {text[:40]!r}; extend COUNTRY_CODES")


def parse_wec(html: str, season: int) -> list[OfficialEvent]:
    """Race days from the season strip on fiawec.com/en/season/<season>.

    Each race link is followed by an ISO3 country label and the race day.
    The page also lists next season, the prologue test and repeats every race
    for other layouts, so those entries are ignored or de-duplicated.
    """
    anchors = list(re.finditer(r'href="/en/race/([a-z0-9-]+)"', html))
    events: dict[str, OfficialEvent] = {}
    for index, anchor in enumerate(anchors):
        slug = anchor.group(1)
        if not slug.endswith(f"-{season}") or "prologue" in slug:
            continue
        end = anchors[index + 1].start() if index + 1 < len(anchors) else len(html)
        window = html[anchor.end():min(end, anchor.end() + 1500)]
        country = re.search(r">\s*([A-Z]{3})\s*</span>", window)
        day = re.search(r"<strong[^>]*>\s*(\d{1,2})\s*</strong>\s*<small[^>]*>\s*([A-Za-z]{3})", window)
        if not country or not day:
            continue
        event = OfficialEvent(slug.removesuffix(f"-{season}"), country.group(1),
                              date(season, month_number(day.group(2)), int(day.group(1))))
        previous = events.setdefault(slug, event)
        if previous != event:
            raise ParseError(f"Conflicting WEC entries for {slug}: {previous} / {event}")
    return sorted(events.values(), key=lambda item: item.date)


def parse_fia_feeder(html: str, season: int) -> list[OfficialEvent]:
    """Weekend end dates from fiaformula2.com / fiaformula3.com ``/Calendar``.

    Each round reads ``ROUND 13 [Next Race] Flag of Qatar Lusail Qatar 27 - 29
    Nov`` with the date before or after the flag text.  Short teaser cards
    without a flag repeat some rounds and are skipped.
    """
    text = page_text(html)
    marks = list(re.finditer(r"\bROUND\s+(\d+)\b", text, re.I))
    date_range = re.compile(
        rf"\b(\d{{1,2}})(?:\s+({MONTH_PATTERN}))?\s*[-\u2013]\s*(\d{{1,2}})\s+({MONTH_PATTERN})(?![a-z])", re.I)
    events: dict[int, OfficialEvent] = {}
    for index, mark in enumerate(marks):
        chunk = text[mark.end():marks[index + 1].start() if index + 1 < len(marks) else len(text)]
        flag = re.search(r"\bFlag of\s+(.+)", chunk)
        found = date_range.search(chunk)
        if not flag or not found:
            continue
        number = int(mark.group(1))
        location = re.split(r"\s+(?:\d|Sprint Race|Feature Race)", flag.group(1), maxsplit=1)[0]
        event = OfficialEvent(f"Round {number} {location}".strip(), country_code(flag.group(1)),
                              date(season, month_number(found.group(4)), int(found.group(3))))
        events.setdefault(number, event)
    return [events[number] for number in sorted(events)]


def parse_imsa(html: str, season: int) -> list[OfficialEvent]:
    """Race days from the IMSA WeatherTech schedule page, keyed by venue.

    All rounds but one are in the USA, so the venue name is the identity.
    """
    text = page_text(html)
    pattern = re.compile(
        rf"(?:Print Schedule|Buy Tickets|Event Details)\s+(?P<name>[^|]+?)\s+"
        rf"(?P<m1>{MONTH_PATTERN})\s+(?P<d1>\d{{1,2}})\s*[-\u2013]\s*(?P<m2>{MONTH_PATTERN})\s+(?P<d2>\d{{1,2}})\s+"
        rf"(?P<venue>.+?)\s+DURATION:", re.I)
    events: dict[tuple[str, date], OfficialEvent] = {}
    for found in pattern.finditer(text):
        name = re.split(r"(?:Print Schedule|Buy Tickets|Event Details)\s+", found.group("name"))[-1].strip()
        if re.search(r"\b(?:Roar|Test)\b", name, re.I):
            continue
        event = OfficialEvent(name, venue_key(found.group("venue")),
                              date(season, month_number(found.group("m2")), int(found.group("d2"))))
        events.setdefault((event.key, event.date), event)
    return sorted(events.values(), key=lambda item: item.date)


def country_key(event: dict) -> str:
    return event["circuit"]["countryCode"]


def circuit_key(event: dict) -> str:
    return venue_key(event["circuit"]["name"])


SOURCES = {
    "wec": Source("wec", "FIA WEC", "https://www.fiawec.com/en/season/{season}", parse_wec, country_key),
    "f2": Source("f2", "FIA Formula 2", "https://www.fiaformula2.com/Calendar", parse_fia_feeder, country_key),
    "f3": Source("f3", "FIA Formula 3", "https://www.fiaformula3.com/Calendar", parse_fia_feeder, country_key),
    "imsa": Source("imsa", "IMSA WeatherTech",
                   "https://www.imsa.com/weathertech/weathertech-{season}-schedule/", parse_imsa, circuit_key),
}
# Curated calendars without a parseable official schedule page.  They are only
# reported as unchecked while they still contain upcoming events.
UNCHECKED_SERIES = ("indycar", "indynxt")


def utc_date(value: str) -> date:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).date()


def calendar_events(calendar: list[dict], key: Callable[[dict], str]) -> list[CalendarEvent]:
    """Our events with the UTC date of their final session (race day)."""
    events = []
    for event in calendar:
        sessions = [session for session in event.get("sessions", []) if session.get("startTimeUtc")]
        if not sessions:
            continue
        final = max(utc_date(session["startTimeUtc"]) for session in sessions)
        events.append(CalendarEvent(event["name"], key(event), final, bool(event.get("cancelled"))))
    return events


def compare(ours: list[CalendarEvent], official: list[OfficialEvent], today: date,
            tolerance_days: int = 1) -> list[str]:
    """Upcoming differences between our calendar and the official schedule.

    Events are paired by identity key (country or venue) and the closest date
    within ``PAIRING_WINDOW_DAYS``; position in the list is never used.  Only
    pairs where either side is still upcoming are reported.
    """
    horizon = today - timedelta(days=1)
    active = [event for event in ours if not event.cancelled]
    candidates = sorted(
        (abs((mine.date - theirs.date).days), mine_index, theirs_index)
        for mine_index, mine in enumerate(active)
        for theirs_index, theirs in enumerate(official)
        if mine.key == theirs.key and abs((mine.date - theirs.date).days) <= PAIRING_WINDOW_DAYS
    )
    paired_ours: dict[int, int] = {}
    paired_official: set[int] = set()
    for _, mine_index, theirs_index in candidates:
        if mine_index not in paired_ours and theirs_index not in paired_official:
            paired_ours[mine_index] = theirs_index
            paired_official.add(theirs_index)

    differences = []
    for mine_index, mine in enumerate(active):
        theirs_index = paired_ours.get(mine_index)
        if theirs_index is None:
            if mine.date >= horizon:
                differences.append(
                    f"{mine.name} ({mine.key}, {mine.date.isoformat()}) is no longer on the official "
                    "schedule (cancelled or moved)")
            continue
        theirs = official[theirs_index]
        if (mine.date >= horizon or theirs.date >= horizon) and \
                abs((mine.date - theirs.date).days) > tolerance_days:
            differences.append(
                f"{mine.name} ({mine.key}): our race day {mine.date.isoformat()}, "
                f"official {theirs.date.isoformat()} ({theirs.name})")
    for theirs_index, theirs in enumerate(official):
        if theirs_index not in paired_official and theirs.date >= horizon:
            differences.append(
                f"Official event {theirs.name} ({theirs.key}, {theirs.date.isoformat()}) is missing "
                "from our calendar (new or moved)")
    return differences


def latest_season(data_root: Path, series: str) -> int | None:
    years = [int(path.name) for path in (data_root / series).glob("[0-9][0-9][0-9][0-9]")
             if (path / "calendar.json").is_file()]
    return max(years) if years else None


def load_calendar(data_root: Path, series: str, season: int) -> list[dict]:
    path = data_root / series / str(season) / "calendar.json"
    return json.loads(path.read_text(encoding="utf-8"))["data"]


def fetch_page(url: str) -> str:
    return read(url, HEADERS, timeout=45).decode("utf-8", "replace")


@dataclass
class Report:
    differences: dict[str, list[str]]
    failures: dict[str, str]
    notes: list[str]

    @property
    def exit_code(self) -> int:
        if any(self.differences.values()):
            return 1
        return 2 if self.failures else 0

    def render(self) -> str:
        lines = []
        for label, items in self.differences.items():
            if items:
                lines.append(f"### {label}: differences")
                lines.extend(f"- {item}" for item in items)
        if self.failures:
            lines.append("### Could not be checked")
            lines.extend(f"- {label}: {error}" for label, error in self.failures.items())
        matched = [label for label, items in self.differences.items() if not items]
        if matched:
            lines.append("### Matching the official schedule")
            lines.extend(f"- {label}" for label in matched)
        if self.notes:
            lines.append("### Notes")
            lines.extend(f"- {note}" for note in self.notes)
        return "\n".join(lines)


# Series whose next-season calendar is imported automatically once announced
# (scripts/fetch_next_season.py and the self-switching GT3 importer).
AUTO_NEXT_SEASON = {"f1", "wec"}


def page_season(html: str) -> int | None:
    """Season named in a page title ("F2 Calendar 2026"), if any."""
    title = re.search(r"<title>([^<]*)</title>", html, re.I)
    years = re.findall(r"\b(20\d\d)\b", title.group(1)) if title else []
    return int(years[-1]) if years else None


def seasons_to_check(data_root: Path, series: str, today: date) -> list[int]:
    """Every season that still has upcoming events (the running one and an
    announced next one), or the latest season when all are complete."""
    years = sorted(int(path.name) for path in (data_root / series).glob("[0-9][0-9][0-9][0-9]")
                   if (path / "calendar.json").is_file())
    active = [
        year for year in years
        if any(event.date >= today - timedelta(days=1)
               for event in calendar_events(load_calendar(data_root, series, year), lambda event: ""))
    ]
    return active or years[-1:]


def run_checks(data_root: Path, today: date, fetch: Callable[[str], str] = fetch_page) -> Report:
    report = Report({}, {}, [])
    for series, source in SOURCES.items():
        seasons = seasons_to_check(data_root, series, today)
        if not seasons:
            report.failures[source.label] = f"no calendar under {data_root / series}"
            continue
        for season in seasons:
            label = f"{source.label} {season}"
            url = source.url.format(season=season)
            try:
                html = fetch(url)
                shown = page_season(html)
                if "{season}" not in source.url and shown is not None and shown != season:
                    # The page shows a single (other) season.
                    report.notes.append(f"{label}: official page shows {shown}, not checked")
                    continue
                ours = calendar_events(load_calendar(data_root, series, season), source.key)
                official = source.parse(html, season)
                if not official:
                    raise ParseError("no events found on the official page")
            except Exception as error:  # noqa: BLE001 - every failure must be reported, never "no changes"
                report.failures[label] = f"{url}: {error}"
                continue
            report.differences[label] = compare(ours, official, today, source.tolerance_days)
        check_next_season(data_root, series, source, max(seasons), fetch, report)
    for series in UNCHECKED_SERIES:
        season = latest_season(data_root, series)
        if season is None:
            continue
        events = calendar_events(load_calendar(data_root, series, season), lambda event: "")
        if all(event.date < today - timedelta(days=1) for event in events):
            report.notes.append(f"{series} {season}: season complete, nothing to check")
        else:
            report.failures[f"{series} {season}"] = "upcoming events but no official schedule parser"
    return report


def check_next_season(data_root: Path, series: str, source: Source, latest: int,
                      fetch: Callable[[str], str], report: Report) -> None:
    """Report an announced next-season calendar that is not in data/ yet."""
    upcoming = latest + 1
    if series in AUTO_NEXT_SEASON or (data_root / series / str(upcoming) / "calendar.json").is_file():
        return
    url = source.url.format(season=upcoming)
    try:
        html = fetch(url)
        if page_season(html) not in (upcoming, None if "{season}" in source.url else -1):
            return
        events = source.parse(html, upcoming)
    except Exception:  # noqa: BLE001 - not announced yet
        return
    if len(events) >= 3:
        report.failures[f"{source.label} {upcoming}"] = (
            f"the official {upcoming} calendar ({len(events)} events) is published at {url}; "
            f"add data/{series}/{upcoming}/calendar.json"
        )


def gh(*args: str) -> str:
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def sync_github_issue(report: Report) -> None:
    issues = json.loads(gh("issue", "list", "--state", "open", "--search", f"{ISSUE_TITLE} in:title",
                           "--json", "number,title,body"))
    existing = next((issue for issue in issues if issue.get("title") == ISSUE_TITLE), None)
    if report.exit_code == 0:
        if existing:
            gh("issue", "close", str(existing["number"]), "--comment",
               "The daily check now matches the official schedules again.")
            print(f"Closed issue #{existing['number']}")
        return
    body = ("The daily official schedule check (`scripts/check_schedules.py`) found differences "
            "between the curated calendars in `data/` and the official schedules.\n\n"
            f"{report.render()}\n")
    if existing is None:
        print(gh("issue", "create", "--title", ISSUE_TITLE, "--body", body).strip())
    elif existing.get("body", "").strip() != body.strip():
        gh("issue", "edit", str(existing["number"]), "--body", body)
        print(f"Updated issue #{existing['number']}")
    else:
        print(f"Issue #{existing['number']} is already up to date")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-root", type=Path, default=ROOT / "data")
    parser.add_argument("--today", type=date.fromisoformat, default=datetime.now(timezone.utc).date())
    parser.add_argument("--github-issue", action="store_true",
                        help="open/update/close the tracking issue when running in GitHub Actions")
    args = parser.parse_args(argv)
    report = run_checks(args.data_root, args.today)
    print(report.render())
    print({0: "All checked calendars match the official schedules.",
           1: "Differences found.", 2: "Some sources could not be checked."}[report.exit_code])
    if args.github_issue:
        if os.environ.get("GITHUB_ACTIONS") == "true":
            sync_github_issue(report)
        else:
            print("--github-issue ignored outside GitHub Actions")
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
