from __future__ import annotations

from pathlib import Path

from shottrainer.app.camera_selection import (
    CameraSelection,
    load_camera_selection,
    resolve_camera_index,
    save_camera_selection,
)


def test_returns_default_when_missing(tmp_path: Path):
    sel = load_camera_selection(tmp_path / "nope.json")
    assert sel == CameraSelection()


def test_roundtrip(tmp_path: Path):
    p = tmp_path / "selection.json"
    save_camera_selection(CameraSelection(name="USB Cam", index=2), p)
    loaded = load_camera_selection(p)
    assert loaded == CameraSelection(name="USB Cam", index=2)


def test_resolve_prefers_name_match():
    sel = CameraSelection(name="USB Cam", index=99)
    available = [(0, "Built-in"), (3, "USB Cam")]
    assert resolve_camera_index(sel, available) == 3


def test_resolve_falls_back_to_index_when_name_missing():
    sel = CameraSelection(name="Unknown", index=2)
    available = [(0, "Built-in"), (2, "USB Cam")]
    assert resolve_camera_index(sel, available) == 2


def test_resolve_falls_back_to_first_when_neither_match():
    sel = CameraSelection(name="Unknown", index=99)
    available = [(0, "Built-in"), (2, "USB Cam")]
    assert resolve_camera_index(sel, available) == 0


def test_resolve_handles_empty_list():
    sel = CameraSelection(name="Anything", index=5)
    assert resolve_camera_index(sel, []) == 5


def test_resolve_handles_no_saved_name():
    sel = CameraSelection()
    available = [(1, "Built-in")]
    assert resolve_camera_index(sel, available) == 1
