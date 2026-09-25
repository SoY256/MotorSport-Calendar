"""Atomically refresh and publish every supported motorsport series."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERIES = ("f1", "f2", "f3", "imsa", "indycar", "indynxt", "wec")


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
        "availableSeries": [{"id": series, "availableSeasons": [2026]} for series in SERIES],
    }
    descriptions = {
        "f1": ("Formula 1", "F1", "#E10600"),
        "f2": ("Formula 2", "F2", "#1565C0"),
        "f3": ("Formula 3", "F3", "#7B1FA2"),
        "imsa": ("IMSA WeatherTech", "IMSA", "#EF6C00"),
        "indycar": ("NTT INDYCAR SERIES", "INDYCAR", "#D71920"),
        "indynxt": ("INDY NXT by Firestone", "INDY NXT", "#E31837"),
        "wec": ("FIA World Endurance Championship", "WEC", "#00695C"),
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
    for series in SERIES:
        season = data_root / series / "2026"
        for name in ("calendar.json", "standings_drivers.json", "standings_teams.json"):
            document = json.loads((season / name).read_text(encoding="utf-8"))
            if document.get("schemaVersion") != 1 or not isinstance(document.get("data"), list):
                raise RuntimeError(f"Invalid {series}/{name}")
            if name.startswith("standings_") and not document["data"]:
                raise RuntimeError(f"Empty {series}/{name}")
        calendar = json.loads((season / "calendar.json").read_text(encoding="utf-8"))["data"]
        if not calendar:
            raise RuntimeError(f"Empty {series} calendar")
        for event in calendar:
            if any(int(session.get("durationMinutes", 0)) <= 0 for session in event.get("sessions", [])):
                raise RuntimeError(f"Missing session duration: {series}/{event['id']}")
            result = season / event["resultsPath"]
            if not result.is_file():
                raise RuntimeError(f"Missing result document: {result}")


def main() -> int:
    target = ROOT / "data"
    try:
        with tempfile.TemporaryDirectory(prefix="all-motorsport-data-", dir=ROOT) as temp_name:
            temp = Path(temp_name)
            staged = temp / "data"
            shutil.copytree(ROOT / "assets" / "data", staged)
            if target.is_dir():
                for series in SERIES:
                    published = target / series
                    if not published.is_dir():
                        continue
                    try:
                        published_count = len(json.loads(
                            (published / "2026" / "standings_drivers.json").read_text(encoding="utf-8")
                        )["data"])
                        bundled_count = len(json.loads(
                            (staged / series / "2026" / "standings_drivers.json").read_text(encoding="utf-8")
                        )["data"])
                    except (FileNotFoundError, KeyError, json.JSONDecodeError):
                        continue
                    if published_count >= bundled_count:
                        shutil.rmtree(staged / series)
                        shutil.copytree(published, staged / series)
            f1_output = temp / "f1-output"
            shutil.copytree(staged / "f1", f1_output / "f1")
            try:
                run("fetch_data.py", os.environ.copy(), "--year", "2026", "--output", str(f1_output))
            except subprocess.CalledProcessError as error:
                print(f"F1 refresh failed; retaining last verified F1 data: {error}", file=sys.stderr)
            else:
                shutil.rmtree(staged / "f1")
                shutil.copytree(f1_output / "f1", staged / "f1")

            importers = {
                "fetch_feeder_data.py": ("f2", "f3"),
                "fetch_imsa_results.py": ("imsa",),
                "fetch_indycar_results.py": ("indycar",),
                "fetch_indynxt_results.py": ("indynxt",),
                "fetch_wec_results.py": ("wec",),
            }
            for index, (script, affected) in enumerate(importers.items()):
                candidate = temp / f"candidate-{index}"
                shutil.copytree(staged, candidate)
                env = os.environ.copy()
                env["MOTORSPORT_DATA_ROOT"] = str(candidate)
                try:
                    run(script, env)
                except subprocess.CalledProcessError as error:
                    print(f"{script} failed; retaining last verified data: {error}", file=sys.stderr)
                else:
                    for series in affected:
                        shutil.rmtree(staged / series)
                        shutil.copytree(candidate / series, staged / series)

            env = os.environ.copy()
            env["MOTORSPORT_DATA_ROOT"] = str(staged)
            run("add_session_durations.py", env, str(staged))
            # Portrait URLs are identity-bound metadata from official series
            # profile pages and can change with driver line-ups.
            portrait_env = os.environ.copy()
            portrait_env["PORTRAIT_SINGLE_ROOT"] = str(staged)
            run("enrich_driver_portraits.py", portrait_env)

            write_indexes(staged)
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
