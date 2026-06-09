"""Tests for the CameraManager extracted module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from shottrainer.app.camera_manager import CameraManager
from shottrainer.app.camera_selection import CameraSelection, save_camera_selection


@pytest.fixture()
def camera_mgr(monkeypatch: pytest.MonkeyPatch) -> CameraManager:
    """A CameraManager with stubbed window and slots."""
    window = MagicMock()
    window.camera_view.set_status = MagicMock()
    on_frame = MagicMock()
    on_error = MagicMock()
    return CameraManager(window=window, on_frame_slot=on_frame, on_camera_error_slot=on_error)


def test_effective_camera_index_no_camera(
    camera_mgr: CameraManager,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """Returns None when the saved selection is explicitly 'no camera'."""
    p = tmp_path / "camera_selection.json"
    save_camera_selection(CameraSelection(name="", index=None), p)
    monkeypatch.setattr(
        "shottrainer.app.camera_manager.load_camera_selection",
        lambda: CameraSelection(name="", index=None),
    )
    assert camera_mgr.effective_camera_index() is None


def test_effective_camera_index_resolves_by_name(
    camera_mgr: CameraManager,
    monkeypatch: pytest.MonkeyPatch,
):
    """Prefers name match when available devices are listed."""
    monkeypatch.setattr(
        "shottrainer.app.camera_manager.load_camera_selection",
        lambda: CameraSelection(name="USB Cam", index=0),
    )
    monkeypatch.setattr(
        "shottrainer.app.camera_manager.list_available_cameras",
        lambda: [(0, "Built-in"), (2, "USB Cam")],
    )
    assert camera_mgr.effective_camera_index() == 2


def test_persist_camera_selection_none(
    camera_mgr: CameraManager,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """Persisting None saves an empty-name, None-index selection."""
    saved = {}

    def fake_save(selection):
        saved["sel"] = selection

    monkeypatch.setattr("shottrainer.app.camera_manager.save_camera_selection", fake_save)
    camera_mgr.persist_camera_selection(None)
    assert saved["sel"].name == ""
    assert saved["sel"].index is None


def test_persist_camera_selection_uses_cache(
    camera_mgr: CameraManager,
    monkeypatch: pytest.MonkeyPatch,
):
    """Uses cached options to look up the name by index."""
    saved = {}

    def fake_save(selection):
        saved["sel"] = selection

    monkeypatch.setattr("shottrainer.app.camera_manager.save_camera_selection", fake_save)
    camera_mgr._cached_camera_options = [(0, "Built-in"), (2, "USB Cam")]
    camera_mgr.persist_camera_selection(2)
    assert saved["sel"].name == "USB Cam"
    assert saved["sel"].index == 2


def test_device_index_returns_none_when_no_camera(camera_mgr: CameraManager):
    """Returns None when no camera is running."""
    assert camera_mgr.device_index() is None


def test_stop_camera_resets_status(camera_mgr: CameraManager):
    """Stopping sets the camera view status to idle."""
    stub_cam = MagicMock()
    camera_mgr._camera = stub_cam
    camera_mgr.stop_camera()
    assert camera_mgr._camera is None
    stub_cam.stop.assert_called_once()
    camera_mgr._window.camera_view.set_status.assert_called_with("idle")


def test_register_frame_mirror(camera_mgr: CameraManager):
    """Registering a mirror adds it to the list."""
    dialog = MagicMock()
    camera_mgr.register_frame_mirror(dialog)
    assert dialog in camera_mgr.frame_mirrors
