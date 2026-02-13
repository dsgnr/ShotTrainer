"""Glue between camera capture, tracking, audio, storage and the UI.

Living in ``app/`` rather than ``services/`` because it bridges Qt signals
between widgets and pure-Python services. The services themselves stay
free of widget code.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject

from shottrainer import __version__
from shottrainer.audio.input import AudioShotListener
from shottrainer.audio.models import ShotDetectorSettings, ShotEvent
from shottrainer.replay.player import TracePlayer
from shottrainer.services.session_recorder import SessionRecorder
from shottrainer.services.shot_coordinator import (
    ShotCoordinator,
    ShotCoordinatorSettings,
)
from shottrainer.services.trace_buffer import TraceBuffer
from shottrainer.sessions.database import init_database, make_engine
from shottrainer.sessions.repository import SessionRepository
from shottrainer.tracking.camera import CameraCapture, CameraConfig
from shottrainer.tracking.calibration import HomographyCalibration, LinearCalibration
from shottrainer.tracking.models import TrackingSample
from shottrainer.tracking.tracker import Tracker
from shottrainer.ui.main_window import MainWindow
from shottrainer.ui.preferences_dialog import Preferences
from shottrainer.ui.session_browser import SessionBrowserDialog
from shottrainer.ui.shot_list import ShotListEntry
from shottrainer.ui.target_view import ShotMarker

log = logging.getLogger(__name__)


class AppController(QObject):
    def __init__(self, window: MainWindow, db_path: Path) -> None:
        super().__init__()
        self._window = window

        engine = make_engine(db_path)
        init_database(engine)
        self._repo = SessionRepository(engine)

        self._tracker = Tracker()
        self._buffer = TraceBuffer(capacity=12000)
        self._recorder = SessionRecorder(self._repo)
        self._coordinator = ShotCoordinator(self._buffer)

        self._camera: CameraCapture | None = None
        self._audio = AudioShotListener()

        self._player = TracePlayer(self)
        self._current_view_session_id: int | None = None
        self._shots_in_view: list[ShotMarker] = []

        self._connect_signals()
        self._apply_preferences(Preferences())

<<<<<<< HEAD
=======
    # --- public ---

    def start(self) -> None:
        """Begin live preview. The camera runs whenever the app is open."""
        self._start_camera(self._preferences.camera_id)

>>>>>>> b7e7600 (feat: keep camera live whenever the app is open)
    def shutdown(self) -> None:
        self._stop_camera()
        self._audio.stop()
        if self._recorder.is_recording:
            self._recorder.stop()

    def _connect_signals(self) -> None:
        sc = self._window.session_controls
        sc.start_requested.connect(self._on_start_requested)
        sc.stop_requested.connect(self._on_stop_requested)

        rc = self._window.replay_controls
        rc.play_clicked.connect(self._player.play)
        rc.pause_clicked.connect(self._player.pause)
        rc.reset_clicked.connect(self._player.stop)
        rc.scrubbed.connect(self._player.seek_fraction)

        self._player.point.connect(self._on_replay_point)
        self._player.progress.connect(rc.set_progress)

        self._window.shot_list.shot_selected.connect(self._on_shot_selected)

        self._audio.shot_detected.connect(self._on_shot_detected)
        self._audio.error.connect(self._on_audio_error)

        self._window.session_browser_requested.connect(self._open_session_browser)
        self._window.preferences_changed.connect(self._apply_preferences)
        self._window.calibration_points_accepted.connect(self._on_calibration_points)

    def _start_camera(self, device_index: int) -> None:
        self._stop_camera()
        cam = CameraCapture(CameraConfig(device_index=device_index))
        cam.frame_ready.connect(self._on_frame)
        cam.error.connect(self._on_camera_error)
        cam.start()
        self._camera = cam

    def _stop_camera(self) -> None:
        if self._camera is not None:
            self._camera.stop()
            self._camera = None

    def _on_frame(self, frame: np.ndarray, ts: float, frame_id: int) -> None:
        self._window.camera_view.set_frame(frame)
        sample = self._tracker.process(frame, ts)
        if sample is None:
            self._window.camera_view.set_aim_point(None, None)
            return
        self._window.camera_view.set_aim_point(sample.x_px, sample.y_px)
        self._buffer.append(sample)
        if sample.x_mm is not None and sample.y_mm is not None:
            self._window.target_view.append_trace_point(sample.x_mm, sample.y_mm)
        if self._recorder.is_recording:
            self._recorder.add_sample(sample)

    def _on_camera_error(self, message: str) -> None:
        self._window.statusBar().showMessage(f"Camera: {message}", 5000)

    def _on_audio_error(self, message: str) -> None:
        self._window.statusBar().showMessage(f"Audio: {message}", 5000)

    def _on_shot_detected(self, event: ShotEvent) -> None:
        result = self._coordinator.handle_shot(event)
        sample = result.sample
        x_mm = sample.x_mm if sample else None
        y_mm = sample.y_mm if sample else None

        marker = ShotMarker(x_mm or 0.0, y_mm or 0.0, label=str(len(self._shots_in_view) + 1))
        self._shots_in_view.append(marker)
        self._window.target_view.set_shots(self._shots_in_view)

        entries = [
            ShotListEntry(
                index=i,
                timestamp=event.timestamp,
                x_mm=m.x_mm,
                y_mm=m.y_mm,
            )
            for i, m in enumerate(self._shots_in_view)
        ]
        self._window.shot_list.set_shots(entries)

        if self._recorder.is_recording:
            self._recorder.add_shot(
                ts=event.timestamp,
                x_mm=x_mm,
                y_mm=y_mm,
                audio_level=event.audio_level,
                confidence=sample.confidence if sample else 0.0,
            )

    def _on_start_requested(self, name: str) -> None:
        if self._recorder.is_recording:
            return
        self._buffer.clear()
        self._shots_in_view.clear()
        self._window.target_view.clear_trace()
        self._window.target_view.set_shots([])
        self._window.shot_list.set_shots([])

        calibration = self._serialise_calibration()
        sid = self._recorder.start(
            name=name,
            calibration=calibration,
            app_version=__version__,
        )
        self._window.session_controls.set_active(True)
        self._window.session_controls.set_summary(f"Recording session {sid}")
        self._audio.start()

    def _on_stop_requested(self) -> None:
        if not self._recorder.is_recording:
            return
        self._audio.stop()
        sid = self._recorder.stop()
        self._window.session_controls.set_active(False)
        self._window.session_controls.set_summary(
            f"Saved session {sid}" if sid else "No active session"
        )

    def _apply_preferences(self, prefs: Preferences) -> None:
        self._preferences = prefs
        self._coordinator.update_settings(
            ShotCoordinatorSettings(pre_shot_ms=prefs.pre_shot_ms, post_shot_ms=prefs.post_shot_ms)
        )
        self._audio.update_settings(
            ShotDetectorSettings(
                threshold=prefs.shot_threshold,
                refractory_ms=prefs.shot_refractory_ms,
            )
        )
        self._audio.set_device(prefs.audio_device)

    def _open_session_browser(self) -> None:
        dialog = SessionBrowserDialog(self._repo, parent=self._window)
        dialog.open_session.connect(self._load_session_for_replay)
        dialog.exec()

    def _load_session_for_replay(self, session_id: int) -> None:
        if self._recorder.is_recording:
            self._window.statusBar().showMessage("Stop recording before opening a session", 4000)
            return
        trace = self._repo.load_trace(session_id)
        shots = self._repo.list_shots(session_id)

        self._current_view_session_id = session_id
        self._window.target_view.clear_trace()
        self._window.target_view.set_trace(
            [(s.x_mm or 0.0, s.y_mm or 0.0) for s in trace if s.x_mm is not None]
        )
        markers = [
            ShotMarker(s.x_mm or 0.0, s.y_mm or 0.0, label=str(i + 1))
            for i, s in enumerate(shots)
        ]
        self._shots_in_view = markers
        self._window.target_view.set_shots(markers)
        self._window.shot_list.set_shots(
            [
                ShotListEntry(
                    index=i,
                    timestamp=s.ts,
                    x_mm=s.x_mm or 0.0,
                    y_mm=s.y_mm or 0.0,
                    score=s.score or None,
                )
                for i, s in enumerate(shots)
            ]
        )
        self._window.replay_controls.set_enabled(False)

    def _on_shot_selected(self, index: int) -> None:
        self._window.target_view.set_selected_shot(index)
        if self._current_view_session_id is None:
            return
        shots = self._repo.list_shots(self._current_view_session_id)
        if index < 0 or index >= len(shots):
            return
        shot = shots[index]
        prefs = self._preferences
        start = shot.ts - prefs.pre_shot_ms / 1000.0
        end = shot.ts + prefs.post_shot_ms / 1000.0
        window = self._repo.load_trace(
            self._current_view_session_id, start_ts=start, end_ts=end
        )
        self._player.load(window)
        self._window.replay_controls.set_enabled(bool(window))

    def _on_replay_point(self, x_mm: float, y_mm: float) -> None:
        self._window.target_view.append_trace_point(x_mm, y_mm)

    def _on_calibration_points(self, image_points: list) -> None:
        from shottrainer.tracking.calibration import a4_target_corners, fit_homography

        try:
            cal = fit_homography(image_points, a4_target_corners("centre"))
        except Exception as exc:
            self._window.statusBar().showMessage(f"Calibration failed: {exc}", 5000)
            return
        self._tracker.set_calibration(cal)
        self._window.statusBar().showMessage("Calibration applied", 4000)

    def _serialise_calibration(self) -> dict | None:
        cal = self._tracker.calibration
        if cal is None:
            return None
        if isinstance(cal, LinearCalibration):
            return {
                "type": "linear",
                "mm_per_pixel": cal.mm_per_pixel,
                "origin_px": list(cal.origin_px),
            }
        if isinstance(cal, HomographyCalibration):
            return {
                "type": "homography",
                "matrix": cal.matrix.tolist(),
                "image_points": [list(p) for p in cal.image_points],
                "target_points_mm": [list(p) for p in cal.target_points_mm],
            }
        return None
