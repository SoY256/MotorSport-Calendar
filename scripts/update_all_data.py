"""Atomically refresh and publish every supported motorsport series."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from fetch_gt3_results import SERIES as GT3_SERIES  # noqa: E402
from seasons import current_season, results_season, season_dirs, season_started  # noqa: E402
from standings_progress import file_progress  # noqa: E402

SERIES = ("f1", "f2", "f3", "imsa", "indycar", "indynxt", "wec", *GT3_SERIES)


DEFAULT_SEASON = 2026


def run(script: str, env: dict[str, str], *args: str) -> None:
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), *args],
        cwd=ROOT,
        env=env,
        check=True,
    )


def write_indexes(data_root: Path) -> None:
    updated = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    manifest = {
        "schemaVersion": 1,
        "lastSuccessfulUpdate": updated,
        "source": {"name": "multi-source-official-refresh", "url": "https://github.com/SoY256/MotorSport-Calendar"},
        # `availableSeasons` keeps only the season users follow now (older app
        # versions load just that one); `publishedSeasons` lists every season
        # with data, e.g. a next-season calendar.
        "availableSeries": [
            {
                "id": series,
                "availableSeasons": [current_season(data_root / series, DEFAULT_SEASON)],
                "publishedSeasons": season_dirs(data_root / series) or [DEFAULT_SEASON],
            }
            for series in SERIES
        ],
    }
    descriptions = {
        "f1": ("Formula 1", "F1", "#E10600"),
        "f2": ("Formula 2", "F2", "#1565C0"),
        "f3": ("Formula 3", "F3", "#7B1FA2"),
        "imsa": ("IMSA WeatherTech", "IMSA", "#EF6C00"),
        "indycar": ("NTT INDYCAR SERIES", "INDYCAR", "#D71920"),
        "indynxt": ("INDY NXT by Firestone", "INDY NXT", "#E31837"),
        "wec": ("FIA World Endurance Championship", "WEC", "#00695C"),
        **{
            series: (config["name"], config["short"], config["color"])
            for series, config in GT3_SERIES.items()
        },
    }
    series_doc = {
        "schemaVersion": 1,
        "lastSuccessfulUpdate": updated,
        "source": manifest["source"],
        "data": [
            {"id": key, "name": value[0], "shortName": value[1], "color": value[2]}
            for key, value in descriptions.items()
        ],
    }
    (data_root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (data_root / "series.json").write_text(json.dumps(series_doc, indent=2) + "\n", encoding="utf-8")


def validate(data_root: Path) -> None:
    now = datetime.now(timezone.utc)
    for series in SERIES:
        seasons = season_dirs(data_root / series)
        if not seasons:
            raise RuntimeError(f"No season data for {series}")
        for year in seasons:
            validate_season(data_root, series, year, now)


def validate_season(data_root: Path, series: str, year: int, now: datetime) -> None:
    season = data_root / series / str(year)
    started = season_started(data_root / series, year, now)
    for name in ("calendar.json", "standings_drivers.json", "standings_teams.json"):
        document = json.loads((season / name).read_text(encoding="utf-8"))
        if document.get("schemaVersion") != 1 or not isinstance(document.get("data"), list):
            raise RuntimeError(f"Invalid {series}/{year}/{name}")
        # A season that has not started yet has no standings.
        if name.startswith("standings_") and not document["data"] and started:
            raise RuntimeError(f"Empty {series}/{year}/{name}")
    calendar = json.loads((season / "calendar.json").read_text(encoding="utf-8"))["data"]
    if not calendar:
        raise RuntimeError(f"Empty {series} calendar")
    for event in calendar:
        if any(int(session.get("durationMinutes", 0)) <= 0 for session in event.get("sessions", [])):
            raise RuntimeError(f"Missing session duration: {series}/{event['id']}")
        result = season / event["resultsPath"]
        if not result.is_file():
            raise RuntimeError(f"Missing result document: {result}")
        result_document = json.loads(result.read_text(encoding="utf-8"))
        result_data = result_document.get("data", {})
        if result_data.get("eventId") != event["id"]:
            raise RuntimeError(f"Wrong event id in result document: {result}")
        scheduled = {session["type"]: session for session in event.get("sessions", [])}
        for classification in result_data.get("sessions", []):
            session_type = classification.get("type")
            if session_type not in scheduled:
                raise RuntimeError(
                    f"Unscheduled result type {session_type}: {series}/{event['id']}"
                )
            start = datetime.fromisoformat(
                scheduled[session_type]["startTimeUtc"].replace("Z", "+00:00")
            )
            end = start + timedelta(
                minutes=int(scheduled[session_type].get("durationMinutes", 120))
            )
            official_f1 = series == 'f1' and classification.get('source', {}).get('name') == 'formula1-official'
            if classification.get("results") and (start if official_f1 else end) > now:
                raise RuntimeError(
                    f"Future session has results: {series}/{event['id']}/{session_type}"
                )


def classified_sessions(series_dir: Path) -> int:
    count = 0
    for path in series_dir.glob("*/events/*.json"):
        try:
            sessions = json.loads(path.read_text(encoding="utf-8"))["data"].get("sessions", [])
        except (KeyError, ValueError):
            continue
        count += sum(1 for session in sessions if session.get("results"))
    return count


def keep_published_results(staged: Path, target: Path) -> None:
    """Keep a series' published data when its new output lost most of its
    classifications: a changed or failing source (the FIA WEC timing site in
    October 2026) must never be published as "no results"."""
    if not target.is_dir():
        return
    for published in sorted(path for path in target.iterdir() if path.is_dir() and path.name != "sources"):
        before = classified_sessions(published)
        after = classified_sessions(staged / published.name)
        if before >= 4 and after < before / 2:
            print(
                f"{published.name}: new data has {after} of {before} published classifications; keeping the published data",
                file=sys.stderr,
            )
            shutil.rmtree(staged / published.name, ignore_errors=True)
            shutil.copytree(published, staged / published.name)


def keep_published_standings(staged: Path, target: Path, now: datetime | None = None) -> None:
    """Do not publish a standings table that is behind one published in the
    last 12 hours.

    Sources update at different speeds after a race (formula1.com within
    minutes, Jolpica hours later); a lagging source must not undo the
    standings a faster one already published. Older tables can go down
    (a post-race disqualification).
    """
    if not target.is_dir():
        return
    now = now or datetime.now(timezone.utc)
    for path in sorted(staged.glob("*/*/standings_*.json")):
        published = target / path.relative_to(staged)
        before, after = file_progress(published), file_progress(path)
        if before is None or after is None or after >= before:
            continue
        try:
            written = json.loads(published.read_text(encoding="utf-8"))["lastSuccessfulUpdate"]
            recent = now - datetime.fromisoformat(written.replace("Z", "+00:00")) < timedelta(hours=12)
        except (KeyError, ValueError, TypeError):
            recent = False
        if recent:
            shutil.copy2(published, path)
            print(f"Kept published {path.relative_to(staged)} ({before} ahead of {after})", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--series",
        help="Comma-separated series to refresh; others keep their published data",
    )
    args = parser.parse_args(argv)
    selected = set(SERIES)
    if args.series:
        selected = {item.strip() for item in args.series.split(",") if item.strip()}
        unknown = selected - set(SERIES)
        if unknown:
            print(f"Unknown series: {sorted(unknown)}", file=sys.stderr)
            return 2
    full_refresh = selected == set(SERIES)
    target = ROOT / "data"
    try:
        with tempfile.TemporaryDirectory(prefix="all-motorsport-data-", dir=ROOT) as temp_name:
            temp = Path(temp_name)
            staged = temp / "data"
            shutil.copytree(ROOT / "assets" / "data", staged)
            if (target / "sources").is_dir():
                shutil.copytree(target / "sources", staged / "sources", dirs_exist_ok=True)
            if target.is_dir():
                for series in SERIES:
                    published = target / series
                    if not published.is_dir():
                        continue
                    year = str(results_season(published, DEFAULT_SEASON))
                    try:
                        published_count = len(json.loads(
                            (published / year / "standings_drivers.json").read_text(encoding="utf-8")
                        )["data"])
                        bundled_path = staged / series / year / "standings_drivers.json"
                        bundled_count = (
                            len(json.loads(bundled_path.read_text(encoding="utf-8"))["data"])
                            if bundled_path.is_file()
                            else 0
                        )
                    except (FileNotFoundError, KeyError, json.JSONDecodeError):
                        continue
                    if published_count >= bundled_count:
                        shutil.rmtree(staged / series, ignore_errors=True)
                        shutil.copytree(published, staged / series)
            f1_output = temp / "f1-output"
            if "f1" in selected:
                shutil.copytree(staged / "f1", f1_output / "f1")
                f1_year = results_season(staged / "f1", DEFAULT_SEASON)
                try:
                    run("fetch_data.py", os.environ.copy(), "--year", str(f1_year), "--output", str(f1_output))
                except subprocess.CalledProcessError as error:
                    print(f"F1 refresh failed; retaining last verified F1 data: {error}", file=sys.stderr)
                else:
                    # fetch_data.py publishes a single season; keep the others
                    # (e.g. the announced next-season calendar).
                    for other in season_dirs(staged / "f1"):
                        if not (f1_output / "f1" / str(other)).exists():
                            shutil.copytree(staged / "f1" / str(other), f1_output / "f1" / str(other))
                    shutil.rmtree(staged / "f1")
                    shutil.copytree(f1_output / "f1", staged / "f1")

                # formula1.com is the primary and fastest official classification
                # source. Jolpica remains the schedule/fallback adapter only.
                f1_env = os.environ.copy()
                f1_env["MOTORSPORT_DATA_ROOT"] = str(staged)
                run("fetch_f1_official_results.py", f1_env)

            importers = [
                ("fetch_feeder_data.py", (), ("f2", "f3")),
                ("fetch_imsa_results.py", (), ("imsa",)),
                ("fetch_indycar_results.py", (), ("indycar",)),
                ("fetch_indynxt_results.py", (), ("indynxt",)),
                ("fetch_wec_results.py", (), ("wec",)),
                # One isolated run per GT3 championship: an outage of one SRO
                # site never blocks or discards the others.
                *(("fetch_gt3_results.py", ("--series", series), (series,)) for series in GT3_SERIES),
            ]
            for index, (script, script_args, affected) in enumerate(importers):
                if not selected.intersection(affected):
                    continue
                candidate = temp / f"candidate-{index}"
                shutil.copytree(staged, candidate)
                env = os.environ.copy()
                env["MOTORSPORT_DATA_ROOT"] = str(candidate)
                try:
                    run(script, env, *script_args)
                except subprocess.CalledProcessError as error:
                    print(f"{script} failed; retaining last verified data: {error}", file=sys.stderr)
                else:
                    for series in affected:
                        shutil.rmtree(staged / series, ignore_errors=True)
                        shutil.copytree(candidate / series, staged / series)

            env = os.environ.copy()
            env["MOTORSPORT_DATA_ROOT"] = str(staged)
            if full_refresh:
                try:
                    run("fetch_next_season.py", env)
                except subprocess.CalledProcessError as error:
                    print(f"Next-season calendars unavailable: {error}", file=sys.stderr)
            run("add_session_durations.py", env, str(staged))
            run("carry_lap_records.py", env, str(staged))
            # Portrait URLs are identity-bound metadata from official series
            # profile pages and can change with driver line-ups.
            portrait_env = os.environ.copy()
            portrait_env["PORTRAIT_SINGLE_ROOT"] = str(staged)
            run("enrich_driver_portraits.py", portrait_env)

            if full_refresh:
                # Targeted live refreshes must not hide that other series are
                # still waiting for their regular six-hour update.
                write_indexes(staged)
            keep_published_results(staged, target)
            keep_published_standings(staged, target)
            validate(staged)
            backup = ROOT / "data.previous"
            if backup.exists():
                shutil.rmtree(backup)
            if target.exists():
                target.replace(backup)
            try:
                staged.replace(target)
            except Exception:
                if backup.exists() and not target.exists():
                    backup.replace(target)
                raise
            if backup.exists():
                shutil.rmtree(backup)
    except Exception as error:
        print(f"All-series update failed; previous data was preserved: {error}", file=sys.stderr)
        return 1
    print("Published all supported series to data/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
