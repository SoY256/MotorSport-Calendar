# MotorSport Calendar

Flutter application backed by small, versioned JSON files generated from upstream motorsport APIs.

## F1 data backend

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
