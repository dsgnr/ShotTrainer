"""Test setup. Runs Qt offscreen so UI tests don't need a display."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Windows' offscreen plugin uses FreeType rather than the native font
# database. Without a font directory it measures missing-glyph boxes.
if sys.platform == "win32":
    os.environ.setdefault("QT_QPA_FONTDIR", str(Path(os.environ["WINDIR"]) / "Fonts"))

import pytest


@pytest.fixture(autouse=True)
def _reset_target_faces_cache():
    # ``target_faces`` caches the custom-faces JSON across calls. Reset
    # between tests so ordering doesn't change behaviour.
    try:
        from shottrainer.app.target_faces import reload_custom_faces
    except Exception:
        return
    reload_custom_faces()
    yield
    reload_custom_faces()
