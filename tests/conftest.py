"""Test setup. Runs Qt offscreen so UI tests don't need a display."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(autouse=True)
def _reset_target_faces_cache():
    # ``target_faces`` caches the custom-faces JSON across calls. Reset
    # between tests so ordering doesn't change behaviour.
    try:
        from shottrainer.ui.target_faces import reload_custom_faces
    except Exception:
        return
    reload_custom_faces()
    yield
    reload_custom_faces()
