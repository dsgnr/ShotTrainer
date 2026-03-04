"""Tests for the settings watcher.

The watcher uses a QTimer. The suite drives it via ``force_check`` so
tests don't sleep.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from shottrainer.app.settings import save_preferences
from shottrainer.app.settings_watcher import SettingsWatcher
from shottrainer.ui.preferences_dialog import Preferences


def test_no_change_when_file_missing(qtbot, tmp_path):
    watcher = SettingsWatcher(path=tmp_path / "absent.json")
    received = []
    watcher.changed.connect(received.append)
    watcher.start()
    watcher.force_check()
    assert received == []


def test_emits_when_file_appears(qtbot, tmp_path):
    p = tmp_path / "settings.json"
    watcher = SettingsWatcher(path=p)
    received = []
    watcher.changed.connect(received.append)
    watcher.start()
    save_preferences(Preferences(camera_id=2), p)
    watcher.force_check()
    assert len(received) == 1
    assert received[0].camera_id == 2


def test_no_emit_after_mark_seen(qtbot, tmp_path):
    p = tmp_path / "settings.json"
    save_preferences(Preferences(), p)
    watcher = SettingsWatcher(path=p)
    received = []
    watcher.changed.connect(received.append)
    watcher.start()
    watcher.mark_seen()
    watcher.force_check()
    assert received == []


def test_emits_defaults_when_file_removed(qtbot, tmp_path):
    p = tmp_path / "settings.json"
    save_preferences(Preferences(camera_id=3), p)
    watcher = SettingsWatcher(path=p)
    received = []
    watcher.changed.connect(received.append)
    watcher.start()
    p.unlink()
    watcher.force_check()
    assert len(received) == 1
    # Removed file means "back to defaults".
    assert received[0] == Preferences()
