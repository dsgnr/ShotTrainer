from __future__ import annotations

import json
from pathlib import Path

import pytest

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


@pytest.mark.parametrize("payload", [b"null", b"[]", b"42", b"true", b'"text"', b"\xff\xfe"])
def test_invalid_settings_document_uses_defaults(tmp_path, payload):
    p = tmp_path / "settings.json"
    p.write_bytes(payload)
    assert load_preferences(p) == Preferences()


@pytest.mark.parametrize(
    "key,value",
    [
        ("pre_shot_ms", "1500"),
        ("post_shot_ms", -1),
        ("release_window_ms", 10**20),
        ("camera_id", True),
        ("camera_rotation", 45),
        ("camera_flip_h", "false"),
        ("show_hold_zone", None),
        ("audio_device", []),
        ("target_face", {}),
        ("shot_threshold", float("nan")),
        ("audio_gain", float("inf")),
        ("circle_diameter_mm", 0),
        ("camera_contrast", -1),
        ("tracking_region_fraction", 2.0),
    ],
)
def test_invalid_preference_value_falls_back_without_discarding_valid_fields(tmp_path, key, value):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({key: value, "shot_diameter_mm": 5.6}))
    loaded = load_preferences(p)
    assert getattr(loaded, key) == getattr(Preferences(), key)
    assert loaded.shot_diameter_mm == 5.6


def test_legacy_null_image_settings_and_unselected_camera_are_supported(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text(
        '{"camera_id": null, "camera_brightness": null, "camera_contrast": null, "audio_gain": 2}'
    )
    loaded = load_preferences(p)
    assert loaded.camera_id is None
    assert loaded.camera_brightness == Preferences().camera_brightness
    assert loaded.camera_contrast == Preferences().camera_contrast
    assert loaded.audio_gain == 2.0
