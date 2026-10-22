import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import carry_lap_records  # noqa: E402


def event(circuit, start, record=None):
    data = {"circuit": {"id": circuit, "name": circuit}, "sessions": [{"startTimeUtc": start}]}
    if record:
        data["circuit"]["lapRecord"] = record
    return data


class CarryLapRecordTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, series, season, events):
        path = self.root / series / str(season) / "calendar.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"data": events}), encoding="utf-8")

    def read(self, series, season):
        return json.loads((self.root / series / str(season) / "calendar.json").read_text(encoding="utf-8"))["data"]

    def test_upcoming_rounds_get_the_fastest_earlier_lap_of_the_series(self):
        self.write("wec", 2026, [
            event("imola", "2026-04-18T10:00:00Z", "1:32.066 • A (2026)"),
            event("spa", "2026-05-08T10:00:00Z", "2:04.177 • B (2026)"),
        ])
        self.write("wec", 2027, [
            event("imola", "2027-04-18T10:00:00Z"),
            event("monza", "2027-07-10T10:00:00Z"),
        ])
        self.write("imsa", 2026, [event("imola", "2025-01-01T00:00:00Z", "1:20.000 • Other series (2026)")])
        carry_lap_records.carry(self.root, now="2026-10-22T00:00:00Z")
        upcoming = self.read("wec", 2027)
        self.assertEqual(upcoming[0]["circuit"]["lapRecord"], "1:32.066 • A (2026)")
        self.assertNotIn("lapRecord", upcoming[1]["circuit"])

    def test_a_meeting_that_has_started_keeps_its_own_record(self):
        self.write("gt", 2026, [
            event("spa", "2026-06-01T10:00:00Z", "2:17.340 • Fast (2026)"),
            event("spa", "2026-09-01T10:00:00Z", "2:19.000 • Slower (2026)"),
            event("spa", "2026-12-01T10:00:00Z", "2:19.000 • Stale carried value (2026)"),
        ])
        carry_lap_records.carry(self.root, now="2026-10-22T00:00:00Z")
        records = [item["circuit"]["lapRecord"] for item in self.read("gt", 2026)]
        self.assertEqual(records, ["2:17.340 • Fast (2026)", "2:19.000 • Slower (2026)", "2:17.340 • Fast (2026)"])

    def test_seeded_earlier_season_records(self):
        sources = self.root / "sources"
        sources.mkdir()
        (sources / "earlier_lap_records.json").write_text(json.dumps({"records": {"wec": {
            "lusail": {"lapRecord": "1:41.259 • Seed (2025)", "source": "https://example.invalid"},
        }}}), encoding="utf-8")
        self.write("wec", 2027, [event("lusail", "2027-02-27T10:00:00Z")])
        carry_lap_records.carry(self.root, now="2026-10-22T00:00:00Z")
        self.assertEqual(self.read("wec", 2027)[0]["circuit"]["lapRecord"], "1:41.259 • Seed (2025)")

    def test_lap_seconds(self):
        self.assertAlmostEqual(carry_lap_records.lap_seconds("8:08.758 • X (2026)"), 488.758)
        self.assertAlmostEqual(carry_lap_records.lap_seconds("0:21.8686 • Y (2026)"), 21.8686)
        self.assertIsNone(carry_lap_records.lap_seconds("–"))


if __name__ == "__main__":
    unittest.main()
