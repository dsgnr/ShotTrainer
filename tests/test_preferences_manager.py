"""Tests for the PreferencesManager extracted module."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from shottrainer.app.capture_pipeline import FrameTransformOptions
from shottrainer.app.preferences import Preferences
from shottrainer.app.preferences_manager import PreferencesManager


@pytest.fixture()
def prefs_mgr() -> PreferencesManager:
    """A PreferencesManager with stubbed dependencies."""
    window = MagicMock()
    tracker = MagicMock()
    tracker.detector = MagicMock()
    tracker.detector.settings = MagicMock()
    camera_mgr = MagicMock()

    current_prefs = Preferences()
    transforms = []

    def get_prefs():
        return current_prefs

    def set_prefs(p):
        nonlocal current_prefs
        current_prefs = p

    def set_transform(t):
        transforms.append(t)

    def build_transform(p):
        return FrameTransformOptions(
            rotation_degrees=p.camera_rotation,
            flip_horizontal=p.camera_flip_h,
            flip_vertical=p.camera_flip_v,
            brightness=p.camera_brightness,
            contrast=p.camera_contrast,
        )

    mgr = PreferencesManager(
        window=window,
        tracker=tracker,
        camera_mgr=camera_mgr,
        get_preferences=get_prefs,
        set_preferences=set_prefs,
        set_frame_transform=set_transform,
        build_transform=build_transform,
    )
    mgr._get_prefs_ref = get_prefs
    mgr._transforms = transforms
    return mgr


def test_camera_property_changed_brightness(prefs_mgr: PreferencesManager):
    """Brightness slider change updates preferences."""
    prefs_mgr._on_camera_property_changed("brightness", 50.0)
    assert prefs_mgr._get_preferences().camera_brightness == 50.0
    assert len(prefs_mgr._transforms) == 1


def test_camera_property_changed_contrast(prefs_mgr: PreferencesManager):
    """Contrast slider change updates preferences."""
    prefs_mgr._on_camera_property_changed("contrast", 1.5)
    assert prefs_mgr._get_preferences().camera_contrast == 1.5


def test_camera_property_changed_ignores_unknown(prefs_mgr: PreferencesManager):
    """Unknown property names are silently ignored."""
    prefs_mgr._on_camera_property_changed("saturation", 1.0)
    # No transform update
    assert len(prefs_mgr._transforms) == 0


def test_camera_property_changed_ignores_none(prefs_mgr: PreferencesManager):
    """None values are ignored."""
    prefs_mgr._on_camera_property_changed("brightness", None)
    assert prefs_mgr._get_preferences().camera_brightness == 0.0


def test_camera_transform_changed(prefs_mgr: PreferencesManager):
    """Rotation and flip changes update preferences."""
    prefs_mgr._on_camera_transform_changed(90, True, False)
    prefs = prefs_mgr._get_preferences()
    assert prefs.camera_rotation == 90
    assert prefs.camera_flip_h is True
    assert prefs.camera_flip_v is False


def test_revert_transform_on_cancel(prefs_mgr: PreferencesManager):
    """Cancelling reverts to the original preferences."""
    original = Preferences(camera_brightness=0.0, camera_contrast=1.0)
    prefs_mgr._on_camera_property_changed("brightness", 80.0)
    prefs_mgr._revert_transform_after_dialog(original, committed=False)
    assert prefs_mgr._get_preferences().camera_brightness == 0.0


def test_revert_transform_no_op_on_commit(prefs_mgr: PreferencesManager):
    """Committed changes are not reverted."""
    original = Preferences(camera_brightness=0.0)
    prefs_mgr._on_camera_property_changed("brightness", 80.0)
    prefs_mgr._revert_transform_after_dialog(original, committed=True)
    # Should still be 80 because committed=True means no revert
    assert prefs_mgr._get_preferences().camera_brightness == 80.0


def test_revert_camera_on_cancel(prefs_mgr: PreferencesManager):
    """Camera reverts to original index on cancel."""
    prefs_mgr._camera_mgr.device_index.return_value = 2
    prefs_mgr._revert_camera_after_dialog(original_index=0, committed=False)
    prefs_mgr._camera_mgr.start_camera.assert_called_once_with(0)


def test_revert_camera_no_op_on_commit(prefs_mgr: PreferencesManager):
    """No revert when user saved."""
    prefs_mgr._revert_camera_after_dialog(original_index=0, committed=True)
    prefs_mgr._camera_mgr.start_camera.assert_not_called()
    prefs_mgr._camera_mgr.stop_camera.assert_not_called()


def test_reset_detector_clears_file(prefs_mgr: PreferencesManager, monkeypatch):
    """Reset sets default settings and clears the saved file."""
    cleared = []
    monkeypatch.setattr(
        "shottrainer.app.preferences_manager.clear_detector_settings",
        lambda: cleared.append(True),
    )
    prefs_mgr._on_reset_detector_requested()
    assert cleared == [True]
