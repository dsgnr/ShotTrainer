"""Light UI tests. Focus on signals and observable state, not pixel layout."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("PySide6")

from shottrainer.ui.camera_view import CameraView
from shottrainer.ui.replay_controls import ReplayControls
from shottrainer.ui.session_controls import SessionControls
from shottrainer.ui.shot_list import ShotList, ShotListEntry
from shottrainer.ui.target_view import ShotMarker, TargetView
from shottrainer.ui.zoom_controls import ZoomControls


def test_shot_list_emits_selection(qtbot):
    panel = ShotList()
    qtbot.addWidget(panel)
    panel.set_shots(
        [
            ShotListEntry(index=0, timestamp=0.0, x_mm=1.0, y_mm=2.0),
            ShotListEntry(index=1, timestamp=1.0, x_mm=-1.0, y_mm=-2.0, score="9.5"),
        ]
    )
    with qtbot.waitSignal(panel.shot_selected, timeout=500) as blocker:
        panel.select_index(1)
    assert blocker.args == [1]


def test_session_controls_emit_start_with_name(qtbot):
    bar = SessionControls()
    qtbot.addWidget(bar)
    bar._name.setText("standing 10m")
    with qtbot.waitSignal(bar.start_requested, timeout=500) as blocker:
        bar.primary_action().click()
    assert blocker.args == ["standing 10m"]


def test_session_controls_active_state_toggles_buttons(qtbot):
    bar = SessionControls()
    qtbot.addWidget(bar)
    bar.set_active(True)
    # While active, the primary becomes Stop and the destructive
    # secondary actions are disabled to avoid drift from the database.
    assert bar.primary_action().text().lower().startswith("stop")
    assert not bar._name.isEnabled()
    assert not bar.clear_button().isEnabled()
    bar.set_active(False)
    assert bar.primary_action().text().lower().startswith("start")
    assert bar._name.isEnabled()
    assert bar.clear_button().isEnabled()


def test_session_controls_primary_emits_stop_when_active(qtbot):
    bar = SessionControls()
    qtbot.addWidget(bar)
    bar.set_active(True)
    with qtbot.waitSignal(bar.stop_requested, timeout=500):
        bar.primary_action().click()


def test_replay_controls_progress_clamps(qtbot):
    rc = ReplayControls()
    qtbot.addWidget(rc)
    rc.set_progress(-1.0)
    assert rc._slider.value() == 0
    rc.set_progress(5.0)
    assert rc._slider.value() == 1000
    rc.set_progress(0.5)
    assert rc._slider.value() == 500


def test_camera_view_accepts_bgr_frame(qtbot):
    view = CameraView()
    qtbot.addWidget(view)
    frame = np.zeros((120, 160, 3), dtype=np.uint8)
    view.set_frame(frame)
    assert view._frame_size == (160, 120)


def test_target_view_accumulates_trace_then_clears(qtbot):
    tv = TargetView()
    qtbot.addWidget(tv)
    for i in range(5):
        tv.append_trace_point(float(i), float(-i))
    assert len(tv._trace) == 5
    tv.clear_trace()
    assert len(tv._trace) == 0


def test_target_view_records_shots(qtbot):
    tv = TargetView()
    qtbot.addWidget(tv)
    tv.set_shots([ShotMarker(1.0, 2.0, "1"), ShotMarker(-3.0, 4.0, "2")])
    assert len(tv._shots) == 2
    tv.set_selected_shot(1)
    assert tv._selected_shot == 1


def test_camera_view_status_changes_are_recorded(qtbot):
    view = CameraView()
    qtbot.addWidget(view)
    assert view._status is None
    view.set_status("tracking")
    assert view._status == "tracking"
    view.set_status("manual")
    assert view._status == "manual"


def test_camera_view_rejects_unknown_status(qtbot):
    view = CameraView()
    qtbot.addWidget(view)
    with pytest.raises(ValueError):
        view.set_status("nonsense")  # type: ignore[arg-type]


def test_zoom_controls_emit_extent(qtbot):
    z = ZoomControls(min_extent_mm=10.0, max_extent_mm=100.0)
    qtbot.addWidget(z)
    received: list[float] = []
    z.extent_changed.connect(received.append)
    # Halfway along log slider should be sqrt(10*100) = ~31.6.
    z._slider.setValue(500)
    assert received
    assert abs(received[-1] - 31.6) < 0.5


def test_zoom_controls_set_extent_clamps(qtbot):
    z = ZoomControls(min_extent_mm=10.0, max_extent_mm=100.0)
    qtbot.addWidget(z)
    z.set_extent(1.0)  # below minimum
    assert z._slider.value() == 0
    z.set_extent(1000.0)  # above maximum
    assert z._slider.value() == 1000


def test_main_window_close_skips_prompt_when_idle(qtbot):
    from shottrainer.ui.main_window import MainWindow

    window = MainWindow()
    qtbot.addWidget(window)
    window.set_recording_check(lambda: False)
    assert window.close()


def test_main_window_close_prompts_during_recording(qtbot, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from shottrainer.ui.main_window import MainWindow

    window = MainWindow()
    qtbot.addWidget(window)
    window.set_recording_check(lambda: True)

    # Pretend the user clicked "Keep recording" (the reject button).
    captured: dict[str, object] = {}

    def fake_exec(self) -> int:
        captured["box"] = self
        # The reject button is the last one added. Return its role.
        for btn in self.buttons():
            if self.buttonRole(btn) == QMessageBox.ButtonRole.RejectRole:
                self.setProperty("clicked_button_id", id(btn))
                self._fake_clicked = btn  # type: ignore[attr-defined]
                return 0
        return 0

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    monkeypatch.setattr(
        QMessageBox, "clickedButton", lambda self: getattr(self, "_fake_clicked", None)
    )

    assert not window.close()
    assert "box" in captured

    # Now choose Stop and quit.
    stop_signals: list[bool] = []
    window.session_controls.stop_requested.connect(lambda: stop_signals.append(True))

    def fake_exec_stop(self) -> int:
        for btn in self.buttons():
            if self.buttonRole(btn) == QMessageBox.ButtonRole.AcceptRole:
                self._fake_clicked = btn  # type: ignore[attr-defined]
                return 0
        return 0

    monkeypatch.setattr(QMessageBox, "exec", fake_exec_stop)
    assert window.close()
    assert stop_signals == [True]


def test_hero_stats_total_score_sums_scores(qtbot):
    from shottrainer.ui.hero_stats import HeroStats

    hero = HeroStats()
    qtbot.addWidget(hero)
    hero.set_scores(["10", "X", "9"])
    # 10 + 10 (X) + 9 = 29
    assert "29" in hero._total.value.text()


def test_hero_stats_total_score_handles_misses(qtbot):
    from shottrainer.ui.hero_stats import HeroStats

    hero = HeroStats()
    qtbot.addWidget(hero)
    hero.set_scores(["", ""])
    # No numeric scores parsed. The panel falls back to a shot-count message.
    assert "shots" in hero._total.value.text().lower()


def test_hero_stats_total_resets_when_empty(qtbot):
    from shottrainer.ui.hero_stats import HeroStats

    hero = HeroStats()
    qtbot.addWidget(hero)
    hero.set_scores(["10"])
    hero.set_scores([])
    assert hero._total.value.text() == "-"


def test_target_view_colour_for_score_maps_known_labels(qtbot):
    from shottrainer.ui.target_view import _MISS_COLOUR, colour_for_score

    assert colour_for_score("10") == colour_for_score("X")  # X tied with 10
    assert colour_for_score("9") != colour_for_score("10")
    assert colour_for_score("") == _MISS_COLOUR
    assert colour_for_score("nonsense") == _MISS_COLOUR
    # Decimal labels pick their integer-part colour.
    assert colour_for_score("9.5") == colour_for_score("9")


def test_target_view_records_shot_score(qtbot):
    from shottrainer.ui.target_view import ShotMarker, TargetView

    tv = TargetView()
    qtbot.addWidget(tv)
    tv.set_shots([ShotMarker(0.0, 0.0, "1", score="10")])
    assert tv._shots[0].score == "10"


def test_preferences_dialog_autofills_diameters_from_face(qtbot):
    """Picking a different face in the combo populates the calibre and
    tracking-circle spinboxes from the face's metadata. Only the
    user's explicit choice triggers this. The values present when the
    dialog opens are left alone so saved preferences aren't clobbered."""
    from shottrainer.app.preferences import Preferences
    from shottrainer.app.target_faces import TargetFace
    from shottrainer.ui.preferences_dialog import PreferencesDialog
    from shottrainer.ui.target_view import TargetRing

    rich = TargetFace(
        key="rich",
        label="Rich face",
        rings=(TargetRing(50.0, "1"),),
        shot_diameter_mm=5.6,
        face_diameter_mm=112.5,
    )
    bare = TargetFace(
        key="bare",
        label="Bare face",
        rings=(TargetRing(40.0, "1"),),
    )
    catalogue = {"rich": rich, "bare": bare}

    dialog = PreferencesDialog(
        Preferences(target_face="bare"),
        target_faces=[("bare", "Bare face"), ("rich", "Rich face")],
        rings_lookup=lambda key: catalogue[key].rings,
        face_lookup=catalogue.get,
    )
    qtbot.addWidget(dialog)

    # Opening the dialog must not have changed the saved diameters.
    assert dialog._shot_diameter.value() == Preferences().shot_diameter_mm
    assert dialog._circle_diameter.value() == Preferences().circle_diameter_mm

    # Simulate the user picking the rich face.
    rich_index = dialog._target_face.findData("rich")
    dialog._target_face.setCurrentIndex(rich_index)
    dialog._on_face_chosen(rich_index)

    assert dialog._shot_diameter.value() == 5.6
    assert dialog._circle_diameter.value() == 112.5

    # Switching back to the bare face must leave the spinboxes alone:
    # there's no metadata to copy from, and silently clearing them
    # would surprise the user.
    bare_index = dialog._target_face.findData("bare")
    dialog._target_face.setCurrentIndex(bare_index)
    dialog._on_face_chosen(bare_index)

    assert dialog._shot_diameter.value() == 5.6
    assert dialog._circle_diameter.value() == 112.5


def test_preferences_dialog_inserts_no_camera_when_saved_is_missing(qtbot):
    """If the saved camera isn't in the enumerated list, the combo
    prepends a "No camera" entry and selects it. Saving from this
    state propagates ``camera_id=None`` so the controller stops
    capture rather than silently picking some other device."""
    from shottrainer.app.preferences import Preferences
    from shottrainer.ui.preferences_dialog import PreferencesDialog

    dialog = PreferencesDialog(
        Preferences(camera_id=2),  # saved cam, but not in the list below
        camera_options=[(0, "Camera 0"), (1, "Camera 1")],
    )
    qtbot.addWidget(dialog)

    assert dialog._camera.currentText() == "No camera"
    assert dialog._camera.currentData() is None


def test_preferences_dialog_emits_camera_changed_on_user_pick(qtbot):
    """Selecting a different camera fires ``camera_changed`` with the
    new index so the controller can swap the live preview without
    waiting for Save."""
    from shottrainer.app.preferences import Preferences
    from shottrainer.ui.preferences_dialog import PreferencesDialog

    dialog = PreferencesDialog(
        Preferences(camera_id=0),
        camera_options=[(0, "Camera 0"), (1, "Camera 1")],
    )
    qtbot.addWidget(dialog)

    received: list[object] = []
    dialog.camera_changed.connect(received.append)

    target = dialog._camera.findData(1)
    dialog._camera.setCurrentIndex(target)
    dialog._on_camera_chosen(target)  # simulate the activated signal

    assert received == [1]


def test_preferences_dialog_emits_none_when_no_camera_chosen(qtbot):
    """Picking the "No camera" entry emits ``None`` so the controller
    can stop the running capture."""
    from shottrainer.app.preferences import Preferences
    from shottrainer.ui.preferences_dialog import PreferencesDialog

    dialog = PreferencesDialog(
        Preferences(camera_id=2),  # forces "No camera" insertion
        camera_options=[(0, "Camera 0")],
    )
    qtbot.addWidget(dialog)

    received: list[object] = []
    dialog.camera_changed.connect(received.append)

    # Already on "No camera". Pick Camera 0 then back to "No camera".
    dialog._camera.setCurrentIndex(dialog._camera.findData(0))
    dialog._on_camera_chosen(dialog._camera.findData(0))
    dialog._camera.setCurrentIndex(0)  # "No camera" item
    dialog._on_camera_chosen(0)

    assert received == [0, None]


def test_preferences_dialog_emits_refresh_devices_request(qtbot):
    """Clicking Refresh asks the controller to re-enumerate devices."""
    from shottrainer.app.preferences import Preferences
    from shottrainer.ui.preferences_dialog import PreferencesDialog

    dialog = PreferencesDialog(
        Preferences(camera_id=0),
        camera_options=[(0, "FaceTime HD")],
    )
    qtbot.addWidget(dialog)

    received: list[bool] = []
    dialog.refresh_devices_requested.connect(lambda: received.append(True))

    # Find the refresh button by its text and click it.
    from PySide6.QtWidgets import QPushButton

    refresh = next(b for b in dialog.findChildren(QPushButton) if b.text() == "Refresh")
    refresh.click()
    assert received == [True]


def test_preferences_dialog_set_camera_options_replaces_combo(qtbot):
    """``set_camera_options`` rebuilds the combo and keeps the user's
    previously selected camera if it's still in the new list."""
    from shottrainer.app.preferences import Preferences
    from shottrainer.ui.preferences_dialog import PreferencesDialog

    dialog = PreferencesDialog(
        Preferences(camera_id=0),
        camera_options=[(0, "FaceTime HD")],
    )
    qtbot.addWidget(dialog)

    dialog.set_camera_options([(0, "FaceTime HD"), (1, "Logitech BRIO")])
    assert dialog._camera.count() == 2
    assert dialog._camera.currentData() == 0  # preserved


def test_preferences_dialog_set_camera_options_falls_back_to_no_camera(qtbot):
    """If the previously selected camera vanishes from the refreshed
    list, the combo falls back to "No camera"."""
    from shottrainer.app.preferences import Preferences
    from shottrainer.ui.preferences_dialog import PreferencesDialog

    dialog = PreferencesDialog(
        Preferences(camera_id=0),
        camera_options=[(0, "FaceTime HD")],
    )
    qtbot.addWidget(dialog)

    dialog.set_camera_options([(2, "USB camera")])
    assert dialog._camera.currentData() is None
    assert dialog._camera.itemText(0) == "No camera"


def test_preferences_dialog_picks_saved_camera_by_name(qtbot):
    """When the saved camera's index has shifted (a new device landed
    at a lower index), the dialog still selects the right camera by
    matching its name. The saved index alone would point at the
    wrong device after the shift."""
    from shottrainer.app.preferences import Preferences
    from shottrainer.ui.preferences_dialog import PreferencesDialog

    # The user previously saved index=0 / name="FaceTime HD". A new
    # USB camera was plugged in. QMediaDevices now returns it at
    # index 0, pushing FaceTime HD to index 1.
    dialog = PreferencesDialog(
        Preferences(camera_id=0),
        camera_options=[(0, "USB Webcam"), (1, "FaceTime HD")],
        saved_camera_name="FaceTime HD",
    )
    qtbot.addWidget(dialog)

    assert dialog._camera.currentText() == "FaceTime HD"
    assert dialog._camera.currentData() == 1


def test_preferences_dialog_set_camera_options_keeps_selection_by_name(qtbot):
    """Refreshing while a camera is selected must keep the same
    *physical* camera selected, even if its index changes because a
    new device was plugged in at a lower index."""
    from shottrainer.app.preferences import Preferences
    from shottrainer.ui.preferences_dialog import PreferencesDialog

    dialog = PreferencesDialog(
        Preferences(camera_id=0),
        camera_options=[(0, "FaceTime HD")],
    )
    qtbot.addWidget(dialog)
    assert dialog._camera.currentText() == "FaceTime HD"

    # Plug in a USB camera that lands at index 0.
    dialog.set_camera_options([(0, "USB Webcam"), (1, "FaceTime HD")])

    # Selection follows the name, not the integer index.
    assert dialog._camera.currentText() == "FaceTime HD"
    assert dialog._camera.currentData() == 1


def test_set_camera_options_emits_camera_changed_when_index_shifts(qtbot):
    """When a refresh assigns the same camera a different index, the
    dialog must emit ``camera_changed`` so the controller restarts
    the live preview on the new index. Without this the preview
    would keep streaming from whatever device now sits at the old
    integer index."""
    from shottrainer.app.preferences import Preferences
    from shottrainer.ui.preferences_dialog import PreferencesDialog

    dialog = PreferencesDialog(
        Preferences(camera_id=0),
        camera_options=[(0, "FaceTime HD")],
    )
    qtbot.addWidget(dialog)

    received: list[object] = []
    dialog.camera_changed.connect(received.append)

    # New USB camera lands at index 0. FaceTime HD shifts to index 1.
    dialog.set_camera_options([(0, "USB Webcam"), (1, "FaceTime HD")])

    assert received == [1]


def test_set_camera_options_no_emit_when_selection_index_unchanged(qtbot):
    """A refresh that returns the same list shouldn't restart the
    live capture."""
    from shottrainer.app.preferences import Preferences
    from shottrainer.ui.preferences_dialog import PreferencesDialog

    dialog = PreferencesDialog(
        Preferences(camera_id=0),
        camera_options=[(0, "FaceTime HD")],
    )
    qtbot.addWidget(dialog)

    received: list[object] = []
    dialog.camera_changed.connect(received.append)

    dialog.set_camera_options([(0, "FaceTime HD")])
    assert received == []
