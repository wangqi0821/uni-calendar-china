"""Integrity checks for the complete frozen calendar (no network access).

    python tools/test_archive.py --media-root /path/to/original/repository
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from urllib.parse import unquote, urlsplit

from PIL import Image

import build_archive


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MEDIA_ROOT = PROJECT_ROOT


class FrozenArchiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = json.loads((PROJECT_ROOT / "Uni.json").read_text(encoding="utf-8"))
        cls.index = json.loads((PROJECT_ROOT / "data/index.json").read_text(encoding="utf-8"))
        cls.days = {}
        for month, relative in cls.index["months"].items():
            payload = json.loads((PROJECT_ROOT / relative).read_text(encoding="utf-8"))
            for day, posts in payload["days"].items():
                if day in cls.days:
                    raise AssertionError(f"Date duplicated across monthly files: {day}")
                if not day.startswith(month + "-"):
                    raise AssertionError(f"Date in the wrong month: {day}")
                cls.days[day] = posts

    def test_complete_frozen_archive_and_all_dates(self):
        self.assertEqual(len(self.source), 2089)
        expected_dates = sorted({record["日期"] for record in self.source})
        self.assertEqual(len(expected_dates), 1745)
        self.assertEqual(self.index["version"], 1)
        self.assertEqual(self.index["dates"], expected_dates)
        self.assertEqual(sorted(self.days), expected_dates)
        self.assertEqual(self.index["firstDate"], "2020-06-10")
        self.assertEqual(self.index["lastDate"], "2026-04-01")
        self.assertEqual(self.index["postCount"], 2089)
        self.assertEqual(self.index["mediaCount"], 3260)
        self.assertEqual(sum(map(len, self.days.values())), 2089)
        self.assertEqual(sum(len(post["media"]) for posts in self.days.values() for post in posts), 3260)

    def test_text_source_and_all_media_references_preserved_in_order(self):
        expected = defaultdict(list)
        for record in self.source:
            expected[record["日期"]].append(record)
        multi_post_days = 0
        for day, originals in expected.items():
            with self.subTest(day=day):
                actual = self.days[day]
                self.assertEqual(len(actual), len(originals))
                multi_post_days += len(originals) > 1
                for original, post in zip(originals, actual, strict=True):
                    self.assertEqual(post["description"], original["描述"])
                    self.assertEqual(post["source"], original["原链接"])
                    # Derive expected paths independently of the production parser.
                    expected_media = [
                        unquote(urlsplit(url).path.split("@main/", 1)[1])
                        for url in original["Uni"]
                    ]
                    self.assertEqual([media["src"] for media in post["media"]], expected_media)
        self.assertEqual(multi_post_days, 329)

    def test_media_files_exist_and_image_dimensions_are_real(self):
        seen = set()
        media_root = MEDIA_ROOT.resolve()
        for posts in self.days.values():
            for post in posts:
                for media in post["media"]:
                    relative = media["src"]
                    if relative in seen:
                        continue
                    seen.add(relative)
                    with self.subTest(path=relative):
                        self.assertRegex(relative, r"^(media|media\.plus)/[^/]+$")
                        self.assertNotIn("..", relative.split("/"))
                        self.assertFalse(any(character in relative for character in "\\:?#%"))
                        actual = (media_root / relative).resolve()
                        self.assertTrue(actual.is_relative_to(media_root))
                        self.assertTrue(actual.is_file())
                        self.assertGreater(actual.stat().st_size, 0)
                        if actual.suffix.lower() == ".jpg":
                            self.assertEqual(media["type"], "image")
                            with Image.open(actual) as picture:
                                expected = picture.size
                                if picture.getexif().get(274, 1) in {5, 6, 7, 8}:
                                    expected = expected[::-1]
                            self.assertEqual((media["width"], media["height"]), expected)
                        else:
                            self.assertEqual(actual.suffix.lower(), ".mp4")
                            self.assertEqual(media["type"], "video")
                        self.assertNotIn("poster", media)
        self.assertEqual(len(seen), 3222)

    def test_every_month_has_a_content_hash_and_exact_month_set(self):
        self.assertEqual(set(self.index["months"]), {day[:7] for day in self.index["dates"]})
        for month, relative in self.index["months"].items():
            with self.subTest(month=month):
                match = re.fullmatch(r"data/(\d{4}-\d{2})\.([0-9a-f]{12})\.json", relative)
                self.assertIsNotNone(match)
                self.assertEqual(match[1], month)
                contents = (PROJECT_ROOT / relative).read_bytes()
                self.assertEqual(hashlib.sha256(contents).hexdigest()[:12], match[2])
                self.assertEqual(set(json.loads(contents)), {"days"})

    def test_regeneration_is_byte_identical_and_preserves_sources(self):
        source = PROJECT_ROOT / "Uni.json"
        before = hashlib.sha256(source.read_bytes()).hexdigest()
        # Keep scratch output in this project's writable data directory; some
        # managed Windows sessions cannot write below the system temp folder.
        with tempfile.TemporaryDirectory(prefix=".integrity-", dir=PROJECT_ROOT / "data") as temporary:
            output = Path(temporary).resolve()
            self.assertTrue(output.is_relative_to((PROJECT_ROOT / "data").resolve()))
            build_archive.build_archive(source, output, MEDIA_ROOT)
            relatives = ["data/index.json", *self.index["months"].values()]
            for relative in relatives:
                self.assertEqual((output / relative).read_bytes(), (PROJECT_ROOT / relative).read_bytes())
            # Reusing the same output folder is also safe and deterministic.
            build_archive.build_archive(source, output, MEDIA_ROOT)
            for relative in relatives:
                self.assertEqual((output / relative).read_bytes(), (PROJECT_ROOT / relative).read_bytes())
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), before)

    def test_rejects_unsafe_or_unknown_sources_and_missing_media(self):
        prefix = "https://cdn.jsdelivr.net/gh/wangqi0821/uni-calendar-china@main/"
        for url in [
            prefix + "media/../Uni.json",
            prefix + "media/%2e%2e/Uni.json",
            prefix + "media/%2fsecret.jpg",
            prefix + "media/photo.jpg?download=1",
            prefix + "media/photo.jpg#fragment",
            prefix + "media/photo%3f.jpg",
            prefix + "media/..%5csecret.jpg",
            prefix + "other/photo.jpg",
            "https://example.com/media/photo.jpg",
            "file:///media/photo.jpg",
        ]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                build_archive.relative_media_path(url)
        with self.assertRaises(ValueError):
            build_archive.media_metadata("media/does-not-exist.jpg", MEDIA_ROOT.resolve())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--media-root", type=Path, default=PROJECT_ROOT)
    arguments, remaining = parser.parse_known_args()
    MEDIA_ROOT = arguments.media_root
    unittest.main(argv=[sys.argv[0], *remaining])
