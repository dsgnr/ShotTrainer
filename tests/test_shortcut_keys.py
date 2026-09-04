"""Regression tests for the main window's keyboard shortcuts.

The tests look up each shortcut by its key sequence and check that
triggering it does the right thing (a signal goes out, the shot
selection moves, the zoom changes). Together they make sure each
shortcut is still hooked up to the right action, so a renamed slot
or a wrong key sequence shows up as a test failure.

Qt's offscreen platform doesn't activate windows the way a real
display does, so ``qtbot.keyClick`` can't trigger a window-level
shortcut. Asking the matching ``QShortcut`` or ``QAction`` to run
itself is the standard workaround and still catches the
regressions we care about.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence, QShortcut

from shottrainer.app.target_faces import rings_for_face
from shottrainer.ui.main_window import MainWindow
from shottrainer.ui.shot_list import ShotListEntry


def _make_window(qtbot) -> MainWindow:
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    return window


def _three_shots() -> list[ShotListEntry]:
    return [
        ShotListEntry(index=0, timestamp=0.0, x_mm=0.0, y_mm=0.0, score="10"),
        ShotListEntry(index=1, timestamp=1.0, x_mm=1.0, y_mm=1.0, score="9"),
        ShotListEntry(index=2, timestamp=2.0, x_mm=2.0, y_mm=2.0, score="8"),
    ]


def _trigger_shortcut(window: MainWindow, sequence: str) -> None:
    """Find the shortcut or action for ``sequence`` and run it.

    Looks at every ``QShortcut`` and ``QAction`` that belongs to the
    window. There should be exactly one match, so a missing or
    duplicate binding shows up as a test failure.
    """
    target = QKeySequence(sequence)
    matches: list[QShortcut | QAction] = []
    for shortcut in window.findChildren(QShortcut):
        if shortcut.key() == target:
            matches.append(shortcut)
    for action in window.findChildren(QAction):
        for seq in action.shortcuts():
            if seq == target:
                matches.append(action)
                break
    assert matches, f"No shortcut bound to {sequence!r}"
    assert len(matches) == 1, f"More than one binding for {sequence!r}: {matches}"
    binding = matches[0]
    if isinstance(binding, QAction):
        binding.trigger()
    else:
        binding.activated.emit()


def test_ctrl_s_clicks_the_primary_session_button(qtbot):
    window = _make_window(qtbot)
    with qtbot.waitSignal(window.session_controls.start_requested, timeout=1000):
        _trigger_shortcut(window, "Ctrl+S")


def test_ctrl_r_emits_clear_shots_when_the_button_is_enabled(qtbot):
    window = _make_window(qtbot)
    window.session_controls.clear_button().setEnabled(True)
    with qtbot.waitSignal(window.session_controls.clear_shots_requested, timeout=1000):
        _trigger_shortcut(window, "Ctrl+R")


def test_ctrl_r_does_nothing_when_the_clear_button_is_disabled(qtbot):
    window = _make_window(qtbot)
    window.session_controls.clear_button().setEnabled(False)
    with qtbot.assertNotEmitted(window.session_controls.clear_shots_requested, wait=200):
        _trigger_shortcut(window, "Ctrl+R")


def test_space_toggles_replay_when_the_controls_are_enabled(qtbot):
    window = _make_window(qtbot)
    window.replay_controls.setEnabled(True)
    with qtbot.waitSignal(window.replay_controls.play_clicked, timeout=1000):
        _trigger_shortcut(window, "Space")


def test_space_does_nothing_while_replay_controls_are_disabled(qtbot):
    window = _make_window(qtbot)
    window.replay_controls.setEnabled(False)
    with qtbot.assertNotEmitted(window.replay_controls.play_clicked, wait=200):
        _trigger_shortcut(window, "Space")


def test_arrow_keys_move_through_the_shot_list(qtbot):
    window = _make_window(qtbot)
    window.shot_list.set_shots(_three_shots())

    _trigger_shortcut(window, "Down")
    assert window.shot_list._list.currentRow() == 0

    _trigger_shortcut(window, "Down")
    assert window.shot_list._list.currentRow() == 1

    _trigger_shortcut(window, "Up")
    assert window.shot_list._list.currentRow() == 0


def test_ctrl_o_emits_the_session_browser_request(qtbot):
    window = _make_window(qtbot)
    with qtbot.waitSignal(window.session_browser_requested, timeout=1000):
        _trigger_shortcut(window, "Ctrl+O")


def test_ctrl_plus_zooms_in(qtbot):
    window = _make_window(qtbot)
    window.target_view.set_rings(rings_for_face("default"))
    initial = window.target_view.extent_mm

    _trigger_shortcut(window, "Ctrl++")
    assert window.target_view.extent_mm < initial


def test_ctrl_minus_zooms_out(qtbot):
    window = _make_window(qtbot)
    window.target_view.set_rings(rings_for_face("default"))
    initial = window.target_view.extent_mm

    _trigger_shortcut(window, "Ctrl+-")
    assert window.target_view.extent_mm > initial


def test_ctrl_zero_resets_the_zoom(qtbot):
    window = _make_window(qtbot)
    window.target_view.set_rings(rings_for_face("default"))
    initial = window.target_view.extent_mm

    # Move the view away from the default extent first so the reset
    # has something to put back.
    window.zoom_controls.zoom_in()
    window.zoom_controls.zoom_in()
    assert window.target_view.extent_mm != pytest.approx(initial, rel=1e-6)

    _trigger_shortcut(window, "Ctrl+0")
    assert window.target_view.extent_mm == pytest.approx(initial, rel=1e-6)


def test_delete_in_the_shot_list_emits_a_deletion_request(qtbot):
    window = _make_window(qtbot)
    window.shot_list.set_shots(_three_shots())
    window.shot_list._list.setCurrentRow(1)
    window.shot_list._list.setFocus()

    with qtbot.waitSignal(window.shot_list.shot_deletion_requested, timeout=1000) as blocker:
        qtbot.keyClick(window.shot_list._list, Qt.Key.Key_Delete)
    assert blocker.args == [1]


def test_backspace_in_the_shot_list_also_emits_a_deletion_request(qtbot):
    window = _make_window(qtbot)
    window.shot_list.set_shots(_three_shots())
    window.shot_list._list.setCurrentRow(2)
    window.shot_list._list.setFocus()

    with qtbot.waitSignal(window.shot_list.shot_deletion_requested, timeout=1000) as blocker:
        qtbot.keyClick(window.shot_list._list, Qt.Key.Key_Backspace)
    assert blocker.args == [2]


def test_ctrl_comma_opens_the_preferences_dialog(qtbot):
    window = _make_window(qtbot)

    # The signal goes out before ``dialog.exec`` takes over the
    # event loop. Schedule ``reject`` for a moment later so it runs
    # once exec is in charge, which lets the dialog close itself.
    def _close_dialog(dialog) -> None:
        QTimer.singleShot(0, dialog.reject)

    window.preferences_dialog_opened.connect(_close_dialog)
    with qtbot.waitSignal(window.preferences_dialog_opened, timeout=2000):
        _trigger_shortcut(window, "Ctrl+,")
