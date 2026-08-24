# MotorSport Calendar

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

GitHub Actions runs the same tests and refreshes data every six hours. The workflow can also be started manually with an optional season year.

The bundled 2026 WEC and IMSA calendars are curated from the official [FIA WEC](https://www.fiawec.com/) and [IMSA WeatherTech](https://www.imsa.com/weathertech/weathertech-2026-schedule/) schedules by `scripts/seed_endurance_data.py`.

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

F1, FIA WEC and IMSA marks remain trademarks of their respective owners. Their Wikimedia logo files are used only to identify the selected series. The iRacing logo is sourced from Wikimedia Commons under CC BY 4.0; the Le Mans Ultimate artwork is sourced from its official Steam media.
