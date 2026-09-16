from __future__ import annotations

import pytest
from scripts.check_docs_seo import PageMetadata, validate_local_media

BASE = "https://example.com/ShotTrainer/"


def test_media_urls_resolve_relative_to_the_built_page(tmp_path):
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "aim trace.mp4").touch()
    (assets / "target.png").touch()
    page = PageMetadata(
        '<video src="../assets/aim%20trace.mp4" poster="../assets/target.png"></video>'
        '<img src="../assets/target.png?version=2">'
    )
    validate_local_media(page, BASE + "replay/", BASE, tmp_path)


@pytest.mark.parametrize(
    "html",
    [
        '<video src="assets/missing.mp4"></video>',
        '<video poster="../assets/missing.png"></video>',
        '<video><source src="../assets/missing.mp4"></video>',
        '<img src="/assets/missing.png">',
    ],
)
def test_missing_local_media_fails_validation(tmp_path, html):
    with pytest.raises(AssertionError, match="media"):
        validate_local_media(PageMetadata(html), BASE + "replay/", BASE, tmp_path)


def test_external_and_embedded_images_do_not_require_local_files(tmp_path):
    page = PageMetadata(
        '<img src="https://cdn.example.com/image.png"><img src="data:image/png;base64,abc">'
    )
    validate_local_media(page, BASE + "replay/", BASE, tmp_path)
