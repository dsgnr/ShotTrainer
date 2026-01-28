"""Static UI assets bundled with the application."""

from __future__ import annotations

from pathlib import Path

ASSETS_DIR = Path(__file__).parent


def asset_path(name: str) -> Path:
    return ASSETS_DIR / name
