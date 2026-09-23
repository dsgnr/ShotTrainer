"""Regression tests for documentation media validation."""

import tempfile
import unittest
from pathlib import Path

from check_docs_seo import PageMetadata, validate_local_media

BASE = "https://example.com/ShotTrainer/"


class MediaValidationTests(unittest.TestCase):
    def test_media_urls_resolve_relative_to_the_built_page(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            assets = root / "assets"
            assets.mkdir()
            (assets / "aim trace.mp4").touch()
            (assets / "target.png").touch()
            page = PageMetadata(
                '<video src="../assets/aim%20trace.mp4" poster="../assets/target.png"></video>'
                '<img src="../assets/target.png?version=2">'
            )
            validate_local_media(page, BASE + "replay/", BASE, root)

    def test_missing_local_media_fails_validation(self):
        cases = [
            '<video src="assets/missing.mp4"></video>',
            '<video poster="../assets/missing.png"></video>',
            '<video><source src="../assets/missing.mp4"></video>',
            '<img src="/assets/missing.png">',
        ]
        with tempfile.TemporaryDirectory() as directory:
            for html in cases:
                with self.subTest(html=html), self.assertRaisesRegex(AssertionError, "media"):
                    validate_local_media(PageMetadata(html), BASE + "replay/", BASE, Path(directory))

    def test_external_and_embedded_images_do_not_require_local_files(self):
        page = PageMetadata(
            '<img src="https://cdn.example.com/image.png"><img src="data:image/png;base64,abc">'
        )
        with tempfile.TemporaryDirectory() as directory:
            validate_local_media(page, BASE + "replay/", BASE, Path(directory))


if __name__ == "__main__":
    unittest.main()
