# Secar

Flutter application backed by small, versioned JSON files generated from upstream motorsport APIs.

## Motorsport data backend

The app never consumes Jolpica responses directly. `scripts/fetch_data.py` adapts the upstream API to schema version 1 and publishes files atomically under:

```text
data/
├── manifest.json
├── series.json
└── f1/<year>/
    ├── calendar.json
    ├── standings_drivers.json
    ├── standings_teams.json
    └── events/<round>-<event>.json
```

All timestamps are UTC. Every document includes `schemaVersion`, `lastSuccessfulUpdate`, and `source`. If downloading or validation fails, the previously published `data/` directory remains untouched.

Run locally:

```bash
python -m unittest discover -s tests -v
python scripts/fetch_data.py --year 2026
```

GitHub Actions runs the same tests and refreshes data every six hours. Because GitHub's cron is best effort (it fires only every few hours in practice), the workflows hand over to a fresh run before they end whenever a session is due within eight hours. During a session they wait for the expected finish and then poll the official timing sources every minute, refreshing only the series that is awaiting a classification, until the result is published. The workflow can also be started manually with an optional season year.

Portraits are uniform head-and-shoulders crops of official studio photos (F1/F2/F3, FIA WEC, ELMS, IMSA, INDYCAR, INDY NXT, GT World Challenge) built by `scripts/official_headshots.py --collect --build` into `assets/portraits/faces/<series>/`; `scripts/enrich_driver_portraits.py` links them by driver name and drivers without a verified face fall back to initials.

The bundled 2026 WEC and IMSA calendars are curated from the official [FIA WEC](https://www.fiawec.com/) and [IMSA WeatherTech](https://www.imsa.com/weathertech/weathertech-2026-schedule/) schedules by `scripts/seed_endurance_data.py`.

The 2026 INDYCAR and INDY NXT calendars and driver standings come from the official [INDYCAR](https://www.indycar.com/) and [INDY NXT](https://www.indynxt.com/) sites and are published by `scripts/seed_indy_data.py`.

The GT3 championships are shown as GT Europe (GT World Challenge Europe, Endurance and Sprint Cup rounds in one series with overall, Gold/Silver/Bronze and Endurance/Sprint Cup standings), GT America, GT Asia, GT Australia, GT International (Intercontinental GT Challenge) and British GT. They are imported by `scripts/fetch_gt3_results.py` from the official SRO websites on every refresh: calendar, timetable (local and GMT times), every session classification and class standings. Classifications come from the SRO HTML tables or the official timing PDFs (Natsoft in Australia and at Bathurst, the Suzuka timing service, the ADAC 24h Nürburgring result, of which only the GT3 class SP 9 is kept). Only GT3 cars are kept; GT4 sessions, rows and standings are skipped. Sessions missing from a published timetable are added from the official results index, and a classification whose entry list does not match the race grid (a support race filed under the wrong session) is rejected. `scripts/gt3_headshots.py` builds face crops for GT3 drivers into `assets/portraits/faces/gt3/` from official studio portraits (the driver's own SRO profile, their profile on another SRO championship, ELMS/Asian Le Mans/WEC, or a verified crop from another series) and, as a last resort, the lead image of the driver's Wikipedia article (exact name match, sharp single face, reviewed by eye); those Wikimedia Commons sources are listed in `data/sources/gt3_wikimedia_portraits.json`. Each GT3 championship can be switched on or off individually in Settings → GT3 championships.

Data is stored per season in `data/<series>/<season>/`. The importers produce the latest season that has started; `scripts/fetch_next_season.py` publishes the next season's calendar as soon as F1 or FIA WEC announce it (times not yet confirmed are marked TBC), and the GT3 importer follows the SRO sites when they switch to the next season. The manifest lists every season in `publishedSeasons`; the app shows all of them in the calendar and the current one in standings (`availableSeasons` keeps only the current season for older app versions). `python scripts/audit_results.py [--online]` checks every published classification (missing sessions, position gaps, duplicate cars, foreign entry lists, standings order, and F1 winners against the Jolpica archive).

Each event shows the fastest race lap of the series' latest meeting at the circuit ("1:46.396 • crew (2026)"), written by the importers from the official timing (F1: all-time race lap record; GT Asia and British GT best laps come from the TSL Timing race PDFs, as the SRO tables only give race times). Rounds still to come get the fastest lap the same series set at that circuit in an earlier meeting (`scripts/carry_lap_records.py`); for circuits not raced in the published seasons, earlier official records with their sources are kept in `data/sources/earlier_lap_records.json`.

Because these curated calendars (F2/F3, WEC, IMSA, INDYCAR, INDY NXT) are not rebuilt from a live API like F1, the `Check official schedules` workflow runs `scripts/check_schedules.py` once per day. It compares the upcoming events of every unfinished season in `data/` with the official FIA WEC, F2, F3 and IMSA schedule pages, reports when a next-season calendar is announced that is not imported automatically, and opens (or updates) a single `Official schedule changed` issue when an event was cancelled, added or moved, or when a source could not be checked; the issue is closed automatically once everything matches again. Run it locally with `PYTHONPATH=scripts python scripts/check_schedules.py`. Result importers match official classifications to calendar events by venue and race day, never by position, so a changed calendar cannot shift results onto the wrong round.

## Flutter application

The application uses a feature-first structure with Riverpod, a shared light/dark design system, responsive phone/desktop navigation, and a complete offline season snapshot. It includes:

- the complete season calendar with an option to show or hide past events;
- session results for completed rounds and driver/constructor standings;
- Polish and English interfaces;
- event times displayed either in the user's local time or the circuit's local time.

It tries the versioned GitHub data first and falls back to the bundled files when the network is unavailable.

```bash
flutter pub get
flutter analyze
flutter test
flutter run
```

On Windows, `run_app.bat` starts the web version using the bundled Flutter SDK. The debug Android package is created at `build/app/outputs/flutter-apk/app-debug.apk`.

CI verifies formatting, static analysis, widget and visual-regression tests, and both web and Android builds.

## Circuit assets

The bundled circuit layout SVGs come from the open-source [F1DB](https://github.com/f1db/f1db) project and are used under CC BY 4.0. A copy of the license is included at `assets/circuits/F1DB-LICENSE.txt`.

Additional endurance layouts are adapted from the open [Pixelsonly Racing Circuits](https://github.com/pixelsonly/pixelsonly-racing-circuits) collection; per-file Wikimedia licensing and attribution is included at `assets/circuits/PIXELSONLY-ASSET-LICENSES.md`. Selected IndyCar layouts come from the public iRacing track-map CDN and are used for circuit identification only.

The GT3 circuit layouts are F1DB maps (CC BY 4.0), the Pixelsonly Sonoma map (CC BY-SA 4.0) and outlines traced from OpenStreetMap raceway geometry (© OpenStreetMap contributors, ODbL 1.0); sources, licences and OSM way/relation ids are listed in `assets/circuits/GT-CIRCUIT-SOURCES.md`.

F1, FIA WEC and IMSA marks remain trademarks of their respective owners. Their Wikimedia logo files are used only to identify the selected series. The iRacing logo is sourced from Wikimedia Commons under CC BY 4.0; the Le Mans Ultimate artwork is sourced from its official Steam media.
