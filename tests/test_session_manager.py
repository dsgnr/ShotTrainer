"""Tests for the SessionManager extracted module."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from shottrainer.app.preferences import Preferences
from shottrainer.app.session_manager import SessionManager, ShotEntry


@pytest.fixture()
def session_mgr() -> SessionManager:
    """A SessionManager with stubbed dependencies."""
    window = MagicMock()
    repo = MagicMock()
    recorder = MagicMock()
    recorder.is_recording = False
    coordinator = MagicMock()
    replay = MagicMock()
    player = MagicMock()
    buffer = MagicMock()

    return SessionManager(
        window=window,
        repo=repo,
        recorder=recorder,
        coordinator=coordinator,
        replay=replay,
        player=player,
        buffer=buffer,
        get_preferences=lambda: Preferences(),
    )


def test_on_start_requested_clears_state(session_mgr: SessionManager):
    """Starting a session clears the shot list and trace."""
    session_mgr._shots_in_view = [ShotEntry(timestamp=0.0, x_mm=1.0, y_mm=2.0, score="9")]
    session_mgr._recorder.is_recording = False
    session_mgr._recorder.start.return_value = 42
    session_mgr.on_start_requested("Test", app_version="1.0.0")
    assert session_mgr._shots_in_view == []
    session_mgr._buffer.clear.assert_called_once()
    session_mgr._window.session_controls.set_active.assert_called_with(True)


def test_on_start_requested_ignores_when_recording(session_mgr: SessionManager):
    """Starting while already recording is a no-op."""
    session_mgr._recorder.is_recording = True
    session_mgr.on_start_requested("Test", app_version="1.0.0")
    session_mgr._recorder.start.assert_not_called()


def test_on_stop_requested(session_mgr: SessionManager):
    """Stopping updates the UI and recorder."""
    session_mgr._recorder.is_recording = True
    session_mgr._recorder.stop.return_value = 7
    session_mgr.on_stop_requested()
    session_mgr._recorder.stop.assert_called_once()
    session_mgr._window.session_controls.set_active.assert_called_with(False)


def test_on_stop_requested_noop_when_not_recording(session_mgr: SessionManager):
    """Stopping when not recording is a no-op."""
    session_mgr._recorder.is_recording = False
    session_mgr.on_stop_requested()
    session_mgr._recorder.stop.assert_not_called()


def test_rescore_updates_shot_scores(session_mgr: SessionManager, monkeypatch):
    """Re-scoring replaces scores on in-memory shots and persists them
    to the database for any shots that have a database id."""
    session_mgr._shots_in_view = [
        ShotEntry(timestamp=0.0, x_mm=0.0, y_mm=0.0, score="5", shot_id=11),
        ShotEntry(timestamp=1.0, x_mm=100.0, y_mm=100.0, score="9", shot_id=12),
        ShotEntry(timestamp=2.0, x_mm=50.0, y_mm=50.0, score=None),
    ]
    # Stub _score_for to return X for the centred shot, blank otherwise.
    monkeypatch.setattr(session_mgr, "_score_for", lambda x, y: "X" if x == 0.0 else "")
    session_mgr._repo.update_shot_scores.return_value = 2
    session_mgr.on_rescore_requested()
    assert session_mgr._shots_in_view[0].score == "X"
    assert session_mgr._shots_in_view[1].score is None
    assert session_mgr._shots_in_view[2].score is None
    # Only entries with a shot_id are sent to the repository.
    session_mgr._repo.update_shot_scores.assert_called_once_with({11: "X", 12: ""})


def test_rescore_skips_database_when_no_shot_ids(session_mgr: SessionManager, monkeypatch):
    """Re-scoring purely in-memory shots does not call the repository."""
    session_mgr._shots_in_view = [
        ShotEntry(timestamp=0.0, x_mm=0.0, y_mm=0.0, score=None),
    ]
    monkeypatch.setattr(session_mgr, "_score_for", lambda x, y: "X")
    session_mgr.on_rescore_requested()
    session_mgr._repo.update_shot_scores.assert_not_called()


def test_delete_shot_removes_entry_and_persists(session_mgr: SessionManager, monkeypatch):
    """Deleting a shot drops it from the on-screen list and the database."""
    from PySide6.QtWidgets import QMessageBox

    session_mgr._shots_in_view = [
        ShotEntry(timestamp=0.0, x_mm=0.0, y_mm=0.0, score="10", shot_id=11),
        ShotEntry(timestamp=1.0, x_mm=1.0, y_mm=1.0, score="9", shot_id=12),
    ]
    monkeypatch.setattr(QMessageBox, "question", lambda *_a, **_k: QMessageBox.StandardButton.Yes)

    session_mgr.on_shot_delete_requested(0)

    assert len(session_mgr._shots_in_view) == 1
    assert session_mgr._shots_in_view[0].shot_id == 12
    session_mgr._repo.delete_shot.assert_called_once_with(11)


def test_delete_shot_skips_database_when_not_persisted(session_mgr: SessionManager, monkeypatch):
    """An in-memory-only shot is removed but the repository is not called."""
    from PySide6.QtWidgets import QMessageBox

    session_mgr._shots_in_view = [
        ShotEntry(timestamp=0.0, x_mm=0.0, y_mm=0.0, score=None),
    ]
    monkeypatch.setattr(QMessageBox, "question", lambda *_a, **_k: QMessageBox.StandardButton.Yes)

    session_mgr.on_shot_delete_requested(0)

    assert session_mgr._shots_in_view == []
    session_mgr._repo.delete_shot.assert_not_called()


def test_delete_shot_cancelled_keeps_everything(session_mgr: SessionManager, monkeypatch):
    """Saying No to the prompt leaves the list and database untouched."""
    from PySide6.QtWidgets import QMessageBox

    session_mgr._shots_in_view = [
        ShotEntry(timestamp=0.0, x_mm=0.0, y_mm=0.0, score="10", shot_id=11),
    ]
    monkeypatch.setattr(QMessageBox, "question", lambda *_a, **_k: QMessageBox.StandardButton.No)

    session_mgr.on_shot_delete_requested(0)

    assert len(session_mgr._shots_in_view) == 1
    session_mgr._repo.delete_shot.assert_not_called()


def test_delete_shot_ignores_out_of_range_index(session_mgr: SessionManager):
    """Out-of-range indices are silently ignored."""
    session_mgr._shots_in_view = []
    session_mgr.on_shot_delete_requested(5)
    session_mgr._repo.delete_shot.assert_not_called()


def test_rescore_noop_when_empty(session_mgr: SessionManager):
    """Re-scoring with no shots shows a status message."""
    session_mgr._shots_in_view = []
    session_mgr.on_rescore_requested()
    session_mgr._window.statusBar().showMessage.assert_called()


def test_replay_play(session_mgr: SessionManager):
    """Play delegates to the player and updates controls."""
    session_mgr._player.is_playing = True
    session_mgr.on_replay_play()
    session_mgr._player.play.assert_called_once()
    session_mgr._window.replay_controls.set_playing.assert_called_with(True)


def test_replay_pause(session_mgr: SessionManager):
    """Pause delegates to the player."""
    session_mgr.on_replay_pause()
    session_mgr._player.pause.assert_called_once()
    session_mgr._window.replay_controls.set_playing.assert_called_with(False)


def test_replay_reset(session_mgr: SessionManager):
    """Reset stops the player."""
    session_mgr.on_replay_reset()
    session_mgr._player.stop.assert_called_once()
    session_mgr._window.replay_controls.set_playing.assert_called_with(False)


def test_load_session_blocked_when_recording(session_mgr: SessionManager):
    """Cannot load a session while recording."""
    session_mgr._recorder.is_recording = True
    session_mgr._load_session_for_replay(1)
    session_mgr._window.statusBar().showMessage.assert_called()
    session_mgr._repo.list_shots.assert_not_called()
