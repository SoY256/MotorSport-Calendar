import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import publish_store_listing as store


class StoreCopyTests(unittest.TestCase):
    def test_both_real_listings_fit_google_limits_and_describe_shipped_features(self):
        for language in store.LOCALES:
            with self.subTest(language=language):
                listing = store.read_listing(ROOT / "play_store" / f"listing-{language}.txt", language)
                self.assertEqual(listing["language"], language)
                self.assertIn("Secar", listing["title"])
                self.assertIn("WEC", listing["shortDescription"])
                self.assertNotIn("e-sport", listing["fullDescription"].lower())
                self.assertNotIn("instant", listing["fullDescription"].lower())

    def test_missing_sections_and_overlong_copy_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "listing-en-US.txt"
            for text in (
                "APP NAME\nSecar\nSHORT DESCRIPTION\nRacing",
                f"APP NAME\n{'x' * 31}\nSHORT DESCRIPTION\nRacing\nFULL DESCRIPTION\nCalendar",
                f"APP NAME\nSecar\nSHORT DESCRIPTION\n{'x' * 81}\nFULL DESCRIPTION\nCalendar",
                f"APP NAME\nSecar\nSHORT DESCRIPTION\nRacing\nFULL DESCRIPTION\n{'x' * 4001}",
                "APP NAME\nSecar\nSHORT DESCRIPTION\nRace\ncalendar\nFULL DESCRIPTION\nCalendar",
            ):
                with self.subTest(text=text[:60]):
                    path.write_text(text, encoding="utf-8")
                    with self.assertRaises(ValueError):
                        store.read_listing(path, "en-US")

    def test_both_supported_youtube_url_forms_are_accepted(self):
        for url in ("https://www.youtube.com/watch?v=abcdefghijk", "https://youtu.be/abcdefghijk"):
            self.assertEqual(store.video_url(url), url)

    def test_localized_previews_have_distinct_valid_video_urls(self):
        links = {
            store.video_url((ROOT / "play_store" / language / "video-url.txt").read_text(encoding="utf-8"))
            for language in store.LOCALES
        }
        self.assertEqual(len(links), 2)

    def test_later_ad_variants_fit_their_text_limits(self):
        sections = {
            "en-US": ("HEADLINE VARIANTS FOR A LATER AD TEST", "DESCRIPTION VARIANTS", "ASSETS"),
            "pl-PL": ("WARIANTY NAGŁÓWKÓW DO PÓŹNIEJSZEGO TESTU REKLAMOWEGO",
                      "WARIANTY OPISÓW REKLAMOWYCH", "MATERIAŁY"),
        }
        for language, (start, middle, end) in sections.items():
            text = (ROOT / "play_store" / f"promotion-{language}.txt").read_text(encoding="utf-8")
            for block, limit in ((text.split(start)[1].split(middle)[0], 30),
                                 (text.split(middle)[1].split(end)[0], 90)):
                lines = [line for line in block.splitlines() if line.strip()]
                with self.subTest(language=language, limit=limit):
                    self.assertEqual(len(lines), 5)
                    self.assertTrue(all(0 < len(line) <= limit for line in lines), lines)

    def test_video_rejects_channels_playlists_tracking_and_insecure_links(self):
        for url in (
            "http://www.youtube.com/watch?v=abcdefghijk",
            "https://www.youtube.com/channel/abcdefghijk",
            "https://www.youtube.com/watch?v=abcdefghijk&list=playlist",
            "https://youtu.be/abcdefghijk?t=20",
            "https://youtu.be/short",
            "https://example.com/watch?v=abcdefghijk",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                store.video_url(url)

    def test_concurrent_edit_guard_ignores_only_preview_url_changes(self):
        base = {
            "listings": [{"language": "en-US", "title": "Secar"}],
            "images": {"en-US": {"phoneScreenshots": [{"id": "1", "sha256": "abc", "url": "old"}]}},
        }
        changed = json.loads(json.dumps(base))
        changed["images"]["en-US"]["phoneScreenshots"][0]["url"] = "new"
        self.assertEqual(store.fingerprint(base), store.fingerprint(changed))
        changed["listings"][0]["title"] = "Someone else's edit"
        self.assertNotEqual(store.fingerprint(base), store.fingerprint(changed))


if __name__ == "__main__":
    unittest.main()
