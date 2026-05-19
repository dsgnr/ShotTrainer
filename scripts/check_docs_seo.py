"""Validate search and sharing metadata after building the documentation."""

from __future__ import annotations

import json
import tomllib
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


class PageMetadata(HTMLParser):
    def __init__(self, html: str) -> None:
        super().__init__()
        self.titles: list[str] = []
        self.canonicals: list[str] = []
        self.meta: dict[str, list[str]] = {}
        self.schemas: list[str] = []
        self._title = False
        self._schema = False
        self.feed(html)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "title":
            self.titles.append("")
            self._title = True
        elif tag == "meta":
            key = attributes.get("name") or attributes.get("property")
            if key:
                self.meta.setdefault(key, []).append(attributes.get("content") or "")
        elif tag == "link" and attributes.get("rel") == "canonical":
            self.canonicals.append(attributes.get("href") or "")
        elif tag == "script" and attributes.get("type") == "application/ld+json":
            self.schemas.append("")
            self._schema = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._title = False
        elif tag == "script":
            self._schema = False

    def handle_data(self, data: str) -> None:
        if self._title:
            self.titles[-1] += data
        if self._schema:
            self.schemas[-1] += data


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    config = tomllib.loads((root / "zensical.toml").read_text())["project"]
    base = config["site_url"]
    site = root / "site"
    urls = [node.text for node in ET.parse(site / "sitemap.xml").iterfind(".//{*}loc")]
    assert urls and len(urls) == len(set(urls)), "Empty or duplicate sitemap entries"
    titles: set[str] = set()
    descriptions: set[str] = set()
    for url in urls:
        assert url and url.startswith(base), f"Unexpected sitemap URL: {url}"
        relative = unquote(url.removeprefix(base))
        html = (
            site / relative / "index.html"
            if not relative or relative.endswith("/")
            else site / relative
        )
        page = PageMetadata(html.read_text())
        assert page.canonicals == [url], f"Canonical mismatch: {url}"
        assert len(page.titles) == 1 and page.titles[0].strip(), f"Missing title: {url}"
        title = page.titles[0].strip()
        assert title not in titles, f"Duplicate title: {title}"
        titles.add(title)
        for key in (
            "description",
            "og:title",
            "og:description",
            "og:url",
            "og:image",
            "og:image:alt",
            "twitter:card",
            "twitter:title",
            "twitter:description",
            "twitter:image",
            "twitter:image:alt",
        ):
            assert len(page.meta.get(key, [])) == 1 and page.meta[key][0], (
                f"Missing or duplicate {key}: {url}"
            )
        description = page.meta["description"][0]
        assert description not in descriptions, f"Duplicate description: {url}"
        descriptions.add(description)
        assert page.meta["og:url"] == [url], f"Sharing URL mismatch: {url}"
        for prefix in ("og", "twitter"):
            assert page.meta[f"{prefix}:title"] == [title], f"Sharing title mismatch: {url}"
            assert page.meta[f"{prefix}:description"] == [description], (
                f"Sharing description mismatch: {url}"
            )
            image = page.meta[f"{prefix}:image"][0]
            assert image.startswith(base) and urlsplit(image).scheme == "https", image
            assert (site / image.removeprefix(base)).is_file(), f"Missing preview image: {image}"
        for schema in page.schemas:
            assert json.loads(schema)["@context"] == "https://schema.org", url
        if url == base:
            assert any(
                json.loads(schema)["@type"] == "SoftwareApplication" for schema in page.schemas
            )
    print(f"SEO metadata verified for {len(urls)} pages.")


if __name__ == "__main__":
    main()
