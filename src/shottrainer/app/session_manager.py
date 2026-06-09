"""Session recording, replay, and shot-selection logic.

Extracted from the controller so session lifecycle (start, stop,
clear), replay playback, and shot-window loading live together.
The controller remains the orchestrator but delegates here for
anything that touches the session database or the replay player.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from shottrainer.replay.player import TracePlayer
from shottrainer.services.replay_coordinator import ReplayCoordinator
from shottrainer.services.scoring import ScoringRing, score_shot
from shottrainer.services.session_recorder import SessionRecorder
from shottrainer.services.shot_coordinator import ShotCoordinator
from shottrainer.services.shot_stats import compute_trace_stats
from shottrainer.services.trace_buffer import TraceBuffer
from shottrainer.sessions.repository import SessionRepository
from shottrainer.ui.session_browser import SessionBrowserDialog
from shottrainer.ui.shot_list import ShotListEntry
from shottrainer.ui.target_view import ShotMarker

from .target_faces import get_face

if TYPE_CHECKING:
    from shottrainer.audio.models import ShotEvent
    from shottrainer.ui.main_window import MainWindow

    from .preferences import Preferences

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ShotEntry:
    """One shot in the current on-screen list.

    Holds the position, timestamp, and optional score string for
    display in the shot list and target view.
    """

    timestamp: float
    x_mm: float
    y_mm: float
    score: str | None = None


class SessionManager:
    """Manages session recording, replay playback, and shot handling.

    Owns the `SessionRecorder`, `ReplayCoordinator`, `TracePlayer`,
    and the in-memory shot list. The controller connects UI signals
    to the public methods here.
    """

    def __init__(
        self,
        window: MainWindow,
        repo: SessionRepository,
        recorder: SessionRecorder,
        coordinator: ShotCoordinator,
        replay: ReplayCoordinator,
        player: TracePlayer,
        buffer: TraceBuffer,
        get_preferences: Callable[[], Preferences],
    ) -> None:
        self._window = window
        self._repo = repo
        self._recorder = recorder
        self._coordinator = coordinator
        self._replay = replay
        self._player = player
        self._buffer = buffer
        self._get_preferences = get_preferences
        self._current_view_session_id: int | None = None
        self._shots_in_view: list[ShotEntry] = []

    @property
    def shots_in_view(self) -> list[ShotEntry]:
        """The current on-screen shot list."""
        return self._shots_in_view

    @shots_in_view.setter
    def shots_in_view(self, value: list[ShotEntry]) -> None:
        """Replace the on-screen shot list."""
        self._shots_in_view = value

    @property
    def recorder(self) -> SessionRecorder:
        """The session recorder instance."""
        return self._recorder

    @property
    def player(self) -> TracePlayer:
        """The replay trace player."""
        return self._player

    def on_start_requested(self, name: str, app_version: str) -> None:
        """Open a new recording session.

        Resets the trace buffer, the on-screen shot list, and the
        replay overlays so the new session starts clean.

        Args:
            name: User-provided session name.
            app_version: Application version string for the session record.
        """
        if self._recorder.is_recording:
            return
        self._buffer.clear()
        self._shots_in_view.clear()
        self._window.target_view.clear_trace()
        self._window.target_view.set_trace_segments(release_index=None, shot_index=None)
        self._window.target_view.set_isolate_selected_shot(False)
        self._window.target_view.set_hold_zone(None)
        self._render_shots()
        self._refresh_stats()

        sid = self._recorder.start(name=name, app_version=app_version)
        self._window.session_controls.set_active(True)
        self._window.session_controls.set_summary(f"Recording session {sid}")
        self._window.header.set_state("recording")

    def on_stop_requested(self) -> None:
        """Stop the current recording, if any."""
        if not self._recorder.is_recording:
            return
        sid = self._recorder.stop()
        self._window.session_controls.set_active(False)
        self._window.session_controls.set_summary(
            f"Saved session {sid}" if sid else "No active session"
        )
        self._window.header.set_state("idle")

    def on_clear_shots_requested(self) -> None:
        """Confirm with the user, then drop the on-screen shot list.

        Saved sessions aren't touched. This only clears what's
        currently rendered.
        """
        if not self._shots_in_view:
            return
        from PySide6.QtWidgets import QMessageBox

        confirm = QMessageBox.question(
            self._window,
            "Clear shots?",
            "Remove all shots from the display? This does not affect saved sessions.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        self._shots_in_view.clear()
        self._window.target_view.clear_trace()
        self._window.target_view.set_trace_segments(release_index=None, shot_index=None)
        self._window.target_view.set_isolate_selected_shot(False)
        self._window.target_view.set_hold_zone(None)
        self._render_shots()
        self._refresh_stats()
        self._window.statusBar().showMessage("Display cleared", 2000)

    def on_shot_detected(self, event: ShotEvent) -> None:
        """Handle a detected shot event.

        Scores the shot against the active face, adds it to the
        on-screen list, and (if recording) saves it to the database.

        Args:
            event: The audio-detected shot event.
        """
        result = self._coordinator.handle_shot(event)
        sample = result.sample
        x_mm = sample.x_mm if sample else None
        y_mm = sample.y_mm if sample else None
        score = self._score_for(x_mm, y_mm)

        self._shots_in_view.append(
            ShotEntry(
                timestamp=event.timestamp,
                x_mm=x_mm or 0.0,
                y_mm=y_mm or 0.0,
                score=score or None,
            )
        )
        self._render_shots()
        self._refresh_stats()

        if self._recorder.is_recording:
            self._recorder.add_shot(
                ts=event.timestamp,
                x_mm=x_mm,
                y_mm=y_mm,
                audio_level=event.audio_level,
                confidence=sample.confidence if sample else 0.0,
                score=score,
            )

    def on_rescore_requested(self) -> None:
        """Re-score every visible shot against the active target face.

        The new scores aren't written back to the database. Re-scoring
        only changes what's currently on screen.
        """
        if not self._shots_in_view:
            self._window.statusBar().showMessage("No shots in view to re-score", 3000)
            return
        rescored = 0
        new_entries: list[ShotEntry] = []
        for entry in self._shots_in_view:
            new_score = self._score_for(entry.x_mm, entry.y_mm)
            new_entries.append(replace(entry, score=new_score or None))
            if new_score:
                rescored += 1
        self._shots_in_view = new_entries
        self._render_shots()
        self._refresh_stats()
        face = self._get_preferences().target_face
        self._window.statusBar().showMessage(
            f"Re-scored {rescored}/{len(self._shots_in_view)} shots against {face}",
            4000,
        )

    def open_session_browser(self) -> None:
        """Open the session-browser dialog, modal to the main window."""
        dialog = SessionBrowserDialog(self._repo, parent=self._window)
        dialog.open_session.connect(self._load_session_for_replay)
        dialog.exec()

    def on_replay_play(self) -> None:
        """Start playback and tell the controls to show the pause glyph."""
        self._player.play()
        self._window.replay_controls.set_playing(self._player.is_playing)

    def on_replay_pause(self) -> None:
        """Pause playback."""
        self._player.pause()
        self._window.replay_controls.set_playing(False)

    def on_replay_reset(self) -> None:
        """Stop the player and reset controls."""
        self._player.stop()
        self._window.replay_controls.set_playing(False)

    def on_shot_selected(self, index: int) -> None:
        """Load the chosen shot's window into the replay UI.

        Pulls the trace samples bracketing the shot, isolates the
        shot's marker, configures the three-colour ramp, and updates
        the hold-zone overlay from pre-shot statistics.

        Args:
            index: Zero-based index into `shots_in_view`.
        """
        self._window.target_view.set_selected_shot(index)
        if self._current_view_session_id is None:
            return
        if index < 0 or index >= len(self._shots_in_view):
            return
        prefs = self._get_preferences()
        window = self._replay.shot_window(
            self._current_view_session_id,
            self._shots_in_view[index].timestamp,
            pre_ms=prefs.pre_shot_ms,
            post_ms=prefs.post_shot_ms,
        )
        self._player.load(window.samples)
        self._window.replay_controls.set_playing(False)
        self._window.target_view.set_trace_segments(
            release_index=window.release_index,
            shot_index=window.split_index,
        )
        self._window.target_view.set_isolate_selected_shot(True)
        points = [(s.x_mm or 0.0, s.y_mm or 0.0) for s in window.samples if s.x_mm is not None]
        self._window.target_view.set_trace(points)
        self._window.replay_controls.set_window_duration_ms(
            int(prefs.pre_shot_ms) + int(prefs.post_shot_ms)
        )
        pre_points = points[: window.split_index + 1] if window.split_index is not None else points
        self._window.hero_stats.set_trace_points(pre_points)
        if pre_points:
            stats = compute_trace_stats(pre_points)
            self._window.target_view.set_hold_zone(
                (stats.mean_x_mm, stats.mean_y_mm), stats.hold_tremor_mm
            )
        else:
            self._window.target_view.set_hold_zone(None)
        self._window.replay_controls.set_enabled(bool(window.samples))

    def _load_session_for_replay(self, session_id: int) -> None:
        """Load a saved session's shots into the view for replay.

        Args:
            session_id: Database ID of the session to load.
        """
        if self._recorder.is_recording:
            self._window.statusBar().showMessage("Stop recording before opening a session", 4000)
            return
        shots = self._repo.list_shots(session_id)

        self._current_view_session_id = session_id
        self._window.target_view.clear_trace()
        self._window.target_view.set_trace_segments(release_index=None, shot_index=None)
        self._window.target_view.set_isolate_selected_shot(False)
        self._window.target_view.set_hold_zone(None)
        self._shots_in_view = [
            ShotEntry(
                timestamp=s.ts,
                x_mm=s.x_mm or 0.0,
                y_mm=s.y_mm or 0.0,
                score=s.score or None,
            )
            for s in shots
        ]
        self._render_shots()
        self._refresh_stats()
        self._window.replay_controls.set_enabled(False)
        self._window.replay_controls.set_window_duration_ms(None)

    def _score_for(self, x_mm: float | None, y_mm: float | None) -> str:
        """Score a shot against the current target face."""
        if x_mm is None or y_mm is None:
            return ""
        prefs = self._get_preferences()
        face = get_face(prefs.target_face)
        if face is None:
            return ""
        scoring = sorted(
            (ScoringRing(r.diameter_mm / 2, r.label or "") for r in face.rings if r.label),
            key=lambda r: r.radius_mm,
        )
        return score_shot(
            x_mm,
            y_mm,
            scoring,
            shot_diameter_mm=prefs.shot_diameter_mm,
            scoring_direction=face.scoring_direction,
        )

    def _render_shots(self) -> None:
        """Push the in-memory shot list out to every widget that shows it."""
        markers = [
            ShotMarker(s.x_mm, s.y_mm, label=str(i + 1), score=s.score or "")
            for i, s in enumerate(self._shots_in_view)
        ]
        self._window.target_view.set_shots(markers)
        self._window.shot_list.set_shots(
            [
                ShotListEntry(
                    index=i,
                    timestamp=s.timestamp,
                    x_mm=s.x_mm,
                    y_mm=s.y_mm,
                    score=s.score,
                )
                for i, s in enumerate(self._shots_in_view)
            ]
        )
        self._window.hero_stats.set_scores([s.score or "" for s in self._shots_in_view])

    def _refresh_stats(self) -> None:
        """Recompute group statistics for the current shot list."""
        positions = [(s.x_mm, s.y_mm) for s in self._shots_in_view]
        self._window.hero_stats.update_from_positions(positions)
        self._window.hero_stats.set_trace_points(None)
