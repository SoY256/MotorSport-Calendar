import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from validate_data import missing_bundled_results, timestamp


class BundledResultsTests(unittest.TestCase):
    snapshot_at = timestamp("2026-11-23T08:00:00Z")
    bundled = {"data": {"sessions": [{"type": "R", "results": [{"position": 1}]}]}}

    def test_live_results_after_snapshot_are_not_required_in_the_offline_bundle(self):
        published = {
            "lastSuccessfulUpdate": "2026-11-27T16:02:06Z",
            "data": {"sessions": [{"type": "FP1", "results": [{"position": 1}]}]},
        }
        self.assertEqual(missing_bundled_results(self.bundled, published, self.snapshot_at), set())

    def test_results_published_before_or_at_capture_must_already_be_present(self):
        for updated in ("2026-11-22T16:50:07Z", "2026-11-23T08:00:00Z"):
            with self.subTest(updated=updated):
                published = {
                    "lastSuccessfulUpdate": updated,
                    "data": {"sessions": [
                        {"type": "FP1", "results": []},
                        {"type": "Q", "results": [{"position": 1}]},
                        {"type": "R", "results": [{"position": 1}]},
                    ]},
                }
                self.assertEqual(missing_bundled_results(self.bundled, published, self.snapshot_at), {"Q"})
