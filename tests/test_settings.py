from __future__ import annotations

from pathlib import Path

from shottrainer.app.preferences import Preferences
from shottrainer.app.settings import load_preferences, save_preferences


def test_returns_defaults_when_missing(tmp_path: Path):
    prefs = load_preferences(tmp_path / "nope.json")
    assert prefs == Preferences()


def test_roundtrip(tmp_path: Path):
    p = tmp_path / "settings.json"
    original = Preferences(
        camera_id=2,
        audio_device="USB Mic",
        shot_threshold=0.4,
        shot_refractory_ms=500,
        pre_shot_ms=2000,
        post_shot_ms=1000,
    )
    save_preferences(original, p)
    loaded = load_preferences(p)
    assert loaded == original


def test_ignores_unknown_keys(tmp_path: Path):
    p = tmp_path / "settings.json"
    p.write_text('{"camera_id": 1, "unknown_key": true}')
    loaded = load_preferences(p)
    assert loaded.camera_id == 1


def test_falls_back_on_garbage_file(tmp_path: Path):
    p = tmp_path / "settings.json"
    p.write_text("not json")
    assert load_preferences(p) == Preferences()
