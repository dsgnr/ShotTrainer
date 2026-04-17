from __future__ import annotations

from pathlib import Path

from shottrainer.app.detector_store import load_detector_settings, save_detector_settings
from shottrainer.tracking.detector import DetectorSettings


def test_returns_none_when_missing(tmp_path: Path):
    assert load_detector_settings(tmp_path / "nope.json") is None


def test_roundtrip(tmp_path: Path):
    p = tmp_path / "detector.json"
    original = DetectorSettings(
        min_radius_px=8,
        max_radius_px=300,
        blur_kernel=7,
        adaptive_block_size=41,
        adaptive_offset=8,
        region_fraction=0.5,
    )
    save_detector_settings(original, p)
    loaded = load_detector_settings(p)
    assert loaded == original


def test_garbage_file_returns_none(tmp_path: Path):
    p = tmp_path / "detector.json"
    p.write_text("not json")
    assert load_detector_settings(p) is None


def test_unknown_keys_are_ignored(tmp_path: Path):
    p = tmp_path / "detector.json"
    p.write_text('{"min_radius_px": 12, "totally_unknown": 99}')
    loaded = load_detector_settings(p)
    assert loaded is not None
    assert loaded.min_radius_px == 12
