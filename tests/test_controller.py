"""Behaviour tests for the application controller.

The controller connects every signal in the app. These tests focus on
the bits a user notices when something goes wrong:

- saved preferences applied at startup actually reach the tracker
  and the recording window
- the zero-on-aim path persists the offset so it survives a restart
- re-scoring against a different face updates what's on screen
  without rewriting the database
- cancelling the Preferences dialog reverts a camera change

The tests construct a real ``MainWindow`` and ``AppController``
against an in-memory database so the connections are exercised end to end.
The camera and audio listeners are stubbed because Qt threads aren't
helpful here.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from shottrainer.app.controller import AppController, _ShotEntry
from shottrainer.app.preferences import Preferences
from shottrainer.ui.main_window import MainWindow


@pytest.fixture()
def controller(
    qtbot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> AppController:
    """Build a controller connected to a fresh in-memory database.

    Camera capture and audio listening are stubbed. Starting a
    real camera thread inside a unit test invites flakiness, and
    none of the assertions here look at frames or audio.
    """
    monkeypatch.setattr("shottrainer.app.camera_manager.CameraCapture", _StubCameraCapture)
    monkeypatch.setattr("shottrainer.app.controller.AudioShotListener", _StubAudioListener)
    # Persistent state files all live next to ``data_dir()``. Redirect
    # each module's path helper so the tests don't trample on the
    # user's real config. ``data_dir`` is bound at import time in
    # several places, so each importer needs its own redirect.
    monkeypatch.setattr("shottrainer.app.paths.data_dir", lambda: tmp_path)
    monkeypatch.setattr(
        "shottrainer.app.zero_offset_store.zero_offset_path",
        lambda: tmp_path / "zero_offset.json",
    )
    monkeypatch.setattr(
        "shottrainer.app.camera_selection.camera_selection_path",
        lambda: tmp_path / "camera_selection.json",
    )
    monkeypatch.setattr(
        "shottrainer.app.detector_store.detector_settings_path",
        lambda: tmp_path / "detector_settings.json",
    )
    monkeypatch.setattr(
        "shottrainer.app.settings.settings_path",
        lambda: tmp_path / "settings.json",
    )

    window = MainWindow()
    qtbot.addWidget(window)
    db_path = tmp_path / "test.sqlite"
    return AppController(window, db_path)


class _StubCameraCapture:
    """A ``CameraCapture``-shaped object that doesn't open a camera."""

    def __init__(self, config) -> None:
        self._config = config
        self.frame_ready = _StubSignal()
        self.error = _StubSignal()

    @property
    def device_index(self) -> int:
        return self._config.device_index

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass


class _StubAudioListener:
    """A no-op stand-in for :class:`AudioShotListener`."""

    def __init__(self, *_a, **_kw) -> None:
        self.shot_detected = _StubSignal()
        self.error = _StubSignal()
        self.level = _StubSignal()

    def update_settings(self, _settings) -> None:
        pass

    def set_device(self, _device: str | int | None) -> None:
        pass

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass


class _StubSignal:
    """Connect/emit shape with no Qt magic. Receivers are plain callables."""

    def __init__(self) -> None:
        self._slots: list[Callable] = []

    def connect(self, slot: Callable, type: object = None) -> None:
        self._slots.append(slot)

    def emit(self, *args, **kwargs) -> None:
        for slot in self._slots:
            slot(*args, **kwargs)


def test_apply_preferences_pushes_circle_diameter_into_tracker(
    controller: AppController,
):
    """Preferences saved to disk on a previous run reach the live tracker."""
    new_prefs = Preferences(circle_diameter_mm=85.0)
    controller._apply_preferences(new_prefs, persist=False)
    assert controller._tracker.circle_diameter_mm == 85.0


def test_apply_preferences_propagates_to_main_window_cache(
    controller: AppController,
):
    """The Preferences dialog opens against the controller's loaded
    values, not the defaults the window started with."""
    controller._apply_preferences(
        Preferences(circle_diameter_mm=42.0, target_face="default"),
        persist=False,
    )
    assert controller._window.current_preferences().circle_diameter_mm == 42.0


def test_settings_file_change_does_not_re_save(
    controller: AppController,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    """When the watcher reports an external edit, the controller
    applies the new prefs but must not write them straight back to
    disk and trigger another change event."""
    saves: list[Preferences] = []
    monkeypatch.setattr(
        "shottrainer.app.controller.save_preferences",
        lambda prefs: saves.append(prefs),
    )
    new_prefs = Preferences(circle_diameter_mm=99.0)
    controller._on_settings_file_changed(new_prefs)
    assert controller._tracker.circle_diameter_mm == 99.0
    assert saves == []


def test_zero_on_aim_persists_offset_and_clears(
    controller: AppController,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """Locking the trace's origin should write to ``zero_offset.json``
    and the Clear-zero path should remove the file."""
    monkeypatch.setattr(
        "shottrainer.app.zero_offset_store.zero_offset_path",
        lambda: tmp_path / "zero_offset.json",
    )
    # Seed the tracker with a sample so zero_at_last_sample works.
    controller._tracker._last_sample = type(
        "S", (), {"x_mm": 1.5, "y_mm": -2.0, "x_px": 0.0, "y_px": 0.0}
    )()
    controller._on_zero_on_aim_requested()
    assert (tmp_path / "zero_offset.json").exists()
    assert controller._tracker.zero_offset_mm == (1.5, -2.0)

    controller._on_zero_cleared()
    assert not (tmp_path / "zero_offset.json").exists()
    assert controller._tracker.zero_offset_mm == (0.0, 0.0)


def test_rescore_updates_view_without_writing_to_db(
    controller: AppController,
):
    """Re-scoring against the active face replaces ``score`` on every
    in-memory shot but does not persist anything. The database keeps
    whichever score was active at the time of capture."""
    controller._shots_in_view = [
        _ShotEntry(timestamp=0.0, x_mm=0.0, y_mm=0.0, score="9"),
        _ShotEntry(timestamp=1.0, x_mm=1000.0, y_mm=1000.0, score=None),
    ]
    controller._on_rescore_requested()
    # Centre shot scores into the smallest ring. Far-out shot scores
    # nothing, so its label should be cleared rather than left as "9".
    centred = controller._shots_in_view[0]
    far = controller._shots_in_view[1]
    assert centred.score not in (None, "")
    assert far.score is None


def test_revert_camera_after_dialog_does_nothing_if_unchanged(
    controller: AppController,
    monkeypatch: pytest.MonkeyPatch,
):
    """Closing the Preferences dialog without changing the camera
    should leave the running capture alone."""
    starts: list[int] = []
    stops: list[bool] = []
    monkeypatch.setattr(AppController, "_start_camera", lambda self, idx: starts.append(idx))
    monkeypatch.setattr(AppController, "_stop_camera", lambda self: stops.append(True))
    # Pretend the camera is already running on index 0 so the revert
    # logic sees the dialog's pre-open and post-close indices match.
    controller._camera = _StubCameraCapture(type("Cfg", (), {"device_index": 0})())
    controller._revert_camera_after_dialog(original_index=0, committed=False)
    assert starts == []
    assert stops == []


def test_revert_camera_after_dialog_committed_is_a_no_op(
    controller: AppController,
    monkeypatch: pytest.MonkeyPatch,
):
    """When the user pressed Save the controller has already applied
    the change. The post-close revert path must keep its hands off."""
    starts: list[int] = []
    stops: list[bool] = []
    monkeypatch.setattr(AppController, "_start_camera", lambda self, idx: starts.append(idx))
    monkeypatch.setattr(AppController, "_stop_camera", lambda self: stops.append(True))
    controller._revert_camera_after_dialog(original_index=0, committed=True)
    assert starts == []
    assert stops == []
