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

Portraits are always local face crops from `assets/portraits/faces/<series>/`; `scripts/enrich_driver_portraits.py` links them by driver name and drivers without a verified face fall back to initials.

The bundled 2026 WEC and IMSA calendars are curated from the official [FIA WEC](https://www.fiawec.com/) and [IMSA WeatherTech](https://www.imsa.com/weathertech/weathertech-2026-schedule/) schedules by `scripts/seed_endurance_data.py`.

The 2026 INDYCAR and INDY NXT calendars and driver standings come from the official [INDYCAR](https://www.indycar.com/) and [INDY NXT](https://www.indynxt.com/) sites and are published by `scripts/seed_indy_data.py`.

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

F1, FIA WEC and IMSA marks remain trademarks of their respective owners. Their Wikimedia logo files are used only to identify the selected series. The iRacing logo is sourced from Wikimedia Commons under CC BY 4.0; the Le Mans Ultimate artwork is sourced from its official Steam media.
