"""Smoke tests for the UI.

These tests construct top-level windows and dialogs and make sure
they build without crashing. They don't assert anything specific
about layout or behaviour, but exist to catch import errors,
missing methods, and broken signal connections.

The kind of bug they would catch: a `paintEvent` calling a method
that no longer exists, an import that breaks at module load,
a dialog that fails to instantiate because a constructor argument
changed.
"""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt

from shottrainer.app.preferences import Preferences
from shottrainer.ui.app_header import AppHeader
from shottrainer.ui.camera_popout import CameraPopout
from shottrainer.ui.camera_view import CameraView, RawCameraView
from shottrainer.ui.main_window import MainWindow
from shottrainer.ui.preferences_dialog import PreferencesDialog


def test_main_window_constructs(qtbot):
    """MainWindow builds all three columns without crashing."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    assert window.camera_view is not None
    assert window.target_view is not None
    assert window.shot_list is not None


def test_main_window_paints_with_no_camera(qtbot):
    """MainWindow repaints cleanly when no camera frame has arrived."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    window.repaint()


def test_main_window_handles_a_frame(qtbot):
    """Push a frame through and trigger a paint."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    frame = np.full((240, 320), 128, dtype=np.uint8)
    window.camera_view.set_frame(frame)
    window.camera_view.set_aim_point(160.0, 120.0, radius_px=40.0)
    window.camera_view.set_status("tracking")
    window.camera_view.repaint()


def test_preferences_dialog_constructs(qtbot):
    """PreferencesDialog builds every tab without crashing."""
    prefs = Preferences()
    dialog = PreferencesDialog(
        prefs,
        camera_options=[(0, "Camera 0"), (1, "Camera 1")],
        audio_options=["default", "Built-in"],
        target_faces=[("default", "Default rings")],
    )
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)


def test_preferences_dialog_push_frame(qtbot):
    """Pushing a frame to the dialog updates the embedded preview."""
    prefs = Preferences()
    dialog = PreferencesDialog(prefs)
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)
    frame = np.full((240, 320), 128, dtype=np.uint8)
    dialog.push_frame(frame)


def test_camera_popout_constructs(qtbot):
    """CameraPopout builds and shows without crashing."""
    popout = CameraPopout()
    qtbot.addWidget(popout)
    popout.show()
    qtbot.waitExposed(popout)


def test_camera_popout_displays_frame(qtbot):
    """Popout shows a frame and resolution label."""
    popout = CameraPopout()
    qtbot.addWidget(popout)
    popout.show()
    qtbot.waitExposed(popout)
    frame = np.full((480, 640), 200, dtype=np.uint8)
    popout.view.set_frame(frame)
    popout.set_resolution(640, 480, fps=120.0)
    popout.repaint()


def test_camera_popout_escape_closes(qtbot):
    """Escape key closes the popout."""
    popout = CameraPopout()
    qtbot.addWidget(popout)
    popout.show()
    qtbot.waitExposed(popout)
    qtbot.keyPress(popout, Qt.Key.Key_Escape)
    qtbot.waitUntil(lambda: not popout.isVisible(), timeout=1000)


def test_app_header_state_transitions(qtbot):
    """Header pill cycles through every defined state without erroring."""
    header = AppHeader()
    qtbot.addWidget(header)
    header.show()
    qtbot.waitExposed(header)
    for state in ("idle", "recording", "replay", "idle"):
        header.set_state(state)
        header.repaint()


def test_main_window_close_when_not_recording(qtbot):
    """Closing the window goes through the closeEvent path cleanly."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.set_recording_check(lambda: False)
    window.show()
    qtbot.waitExposed(window)
    window.close()


def test_camera_view_full_lifecycle(qtbot):
    """Push frames, set overlays, clear, and repaint."""
    view = CameraView()
    qtbot.addWidget(view)
    view.resize(320, 240)
    frame = np.full((120, 160), 100, dtype=np.uint8)
    view.set_frame(frame)
    view.set_aim_point(80.0, 60.0, radius_px=20.0)
    view.set_rejected_point(20.0, 20.0, radius_px=10.0)
    view.set_region_fraction(0.7)
    view.set_status("tracking")
    view.repaint()
    view.clear()
    view.repaint()


def test_raw_camera_view_full_lifecycle(qtbot):
    """RawCameraView accepts both BGR and greyscale frames."""
    view = RawCameraView()
    qtbot.addWidget(view)
    view.resize(320, 240)
    grey = np.full((120, 160), 50, dtype=np.uint8)
    view.set_frame(grey)
    view.repaint()
    bgr = np.full((120, 160, 3), 200, dtype=np.uint8)
    view.set_frame(bgr)
    view.repaint()
    view.clear()
    view.repaint()


def test_arrow_keys_step_shot_selection(qtbot):
    """Up and Down step through the shot list when there are shots."""
    from shottrainer.ui.shot_list import ShotListEntry

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    window.activateWindow()
    qtbot.waitActive(window)

    window.shot_list.set_shots(
        [
            ShotListEntry(index=0, timestamp=0.0, x_mm=0.0, y_mm=0.0, score="10"),
            ShotListEntry(index=1, timestamp=1.0, x_mm=1.0, y_mm=1.0, score="9"),
            ShotListEntry(index=2, timestamp=2.0, x_mm=2.0, y_mm=2.0, score="8"),
        ]
    )

    # The arrow keys go through the main window's helper, so exercise
    # them through that entry point. The QShortcut binds the same
    # callable.
    window._step_next_shot()
    assert window.shot_list._list.currentRow() == 0

    window._step_next_shot()
    assert window.shot_list._list.currentRow() == 1

    window._step_prev_shot()
    assert window.shot_list._list.currentRow() == 0

    # Up at the top stays put.
    window._step_prev_shot()
    assert window.shot_list._list.currentRow() == 0


def test_zoom_shortcuts_change_extent(qtbot):
    """The zoom helpers behind Ctrl++/-/0 change the target extent."""
    from shottrainer.app.target_faces import rings_for_face

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)

    # Apply the default face's rings the way the controller does on
    # startup so the "fit to rings" reset has the right baseline.
    window.target_view.set_rings(rings_for_face("default"))
    initial = window.target_view.extent_mm

    window.zoom_controls.zoom_in()
    assert window.target_view.extent_mm < initial

    window.zoom_controls.zoom_out()
    window.zoom_controls.zoom_out()
    assert window.target_view.extent_mm > initial

    # Reset returns the view to the rings-based default extent.
    window.target_view.reset_extent_to_rings()
    assert window.target_view.extent_mm == pytest.approx(initial, rel=1e-6)
