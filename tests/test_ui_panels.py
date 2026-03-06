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
    panel.set_shots([
        ShotListEntry(index=0, timestamp=0.0, x_mm=1.0, y_mm=2.0),
        ShotListEntry(index=1, timestamp=1.0, x_mm=-1.0, y_mm=-2.0, score="9.5"),
    ])
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
    assert view._status == "idle"
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
