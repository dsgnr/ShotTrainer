"""Glue between camera capture, tracking, audio, storage and the UI.

Living in ``app/`` rather than ``services/`` because it bridges Qt signals
between widgets and pure-Python services. The services themselves stay
free of widget code.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject

from shottrainer import __version__
from shottrainer.audio.input import AudioShotListener, list_audio_inputs
from shottrainer.audio.models import ShotDetectorSettings, ShotEvent
from shottrainer.replay.player import TracePlayer
from shottrainer.services.replay_coordinator import ReplayCoordinator
from shottrainer.services.session_recorder import SessionRecorder
from shottrainer.services.shot_coordinator import (
    ShotCoordinator,
    ShotCoordinatorSettings,
)
from shottrainer.services.shot_stats import compute_trace_stats
from shottrainer.services.trace_buffer import TraceBuffer
from shottrainer.sessions.database import init_database, make_engine
from shottrainer.sessions.repository import SessionRepository
from shottrainer.tracking.calibration import HomographyCalibration, LinearCalibration
from shottrainer.tracking.camera import CameraCapture, CameraConfig, list_available_cameras
from shottrainer.tracking.frame_ops import transform_frame
from shottrainer.tracking.sheet_detector import detect_sheet_corners
from shottrainer.tracking.tracker import Tracker
from shottrainer.ui.main_window import MainWindow
from shottrainer.ui.preferences_dialog import Preferences
from shottrainer.ui.session_browser import SessionBrowserDialog
from shottrainer.ui.shot_list import ShotListEntry
from shottrainer.ui.target_faces import list_target_faces, rings_for_face
from shottrainer.ui.target_view import ShotMarker

from .calibration_store import load_calibration, save_calibration, serialise_calibration
from .settings import load_preferences, save_preferences

log = logging.getLogger(__name__)


@dataclass(slots=True)
class _ShotEntry:
    """One shot in the current on-screen list."""
    timestamp: float
    x_mm: float
    y_mm: float
    score: str | None = None


class AppController(QObject):
    """Connects UI signals to the underlying services.

    Owns the camera capture thread, the audio listener, the tracker, and
    the recorder/replay coordinators. Reacts to widget signals from
    ``MainWindow`` and pushes results back via the same widgets. The
    controller does not draw anything itself.
    """

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
        self._replay = ReplayCoordinator(self._repo)

        self._camera: CameraCapture | None = None
        self._audio = AudioShotListener()

        self._player = TracePlayer(self)
        self._current_view_session_id: int | None = None
        self._shots_in_view: list[_ShotEntry] = []
        self._open_calibration_dialog_ref = None
        self._open_prefs_dialog_ref = None
        self._latest_frame: np.ndarray | None = None

        self._connect_signals()
        self._window.set_device_options_provider(self._device_options)
        self._window.set_target_faces_provider(list_target_faces)
        self._window.set_rings_lookup(rings_for_face)
        self._window.set_calibration_corner_detector(detect_sheet_corners)
        self._apply_preferences(load_preferences())

        saved_cal = load_calibration()
        if saved_cal is not None:
            self._tracker.set_calibration(saved_cal)
            self._update_calibration_status(saved_cal)

    def start(self) -> None:
        """Start live preview. The camera and microphone run for as long as the app is open."""
        self._start_camera(self._preferences.camera_id)
        self._audio.start()

    def shutdown(self) -> None:
        self._stop_camera()
        self._audio.stop()
        if self._recorder.is_recording:
            self._recorder.stop()

    def _device_options(self) -> tuple[list[tuple[int, str]], list[str]]:
        cameras = list_available_cameras() or [(0, "Camera 0")]
        mics = list_audio_inputs()
        return cameras, mics

    def _connect_signals(self) -> None:
        sc = self._window.session_controls
        sc.start_requested.connect(self._on_start_requested)
        sc.stop_requested.connect(self._on_stop_requested)
        sc.clear_shots_requested.connect(self._on_clear_shots_requested)

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
        self._window.calibration_dialog_opened.connect(self._on_calibration_dialog_opened)
        self._window.preferences_dialog_opened.connect(self._on_prefs_dialog_opened)
        self._window.manual_aim_requested.connect(self._on_manual_aim_requested)
        self._window.manual_aim_cleared.connect(self._on_manual_aim_cleared)

        self._audio.level.connect(self._on_audio_level)

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
            self._window.camera_view.set_status("idle")

    def _on_frame(self, frame: np.ndarray, ts: float, frame_id: int) -> None:
        prefs = self._preferences
        frame = transform_frame(
            frame,
            rotation_degrees=prefs.camera_rotation,
            flip_horizontal=prefs.camera_flip_h,
            flip_vertical=prefs.camera_flip_v,
        )
        self._latest_frame = frame
        self._window.camera_view.set_frame(frame)
        if self._open_calibration_dialog_ref is not None:
            self._open_calibration_dialog_ref.set_frame(frame)
        if self._open_prefs_dialog_ref is not None:
            self._open_prefs_dialog_ref.push_frame(frame)
        sample = self._tracker.process(frame, ts)
        if sample is None:
            self._window.camera_view.set_aim_point(None, None)
            self._window.camera_view.set_status("lost")
            return
        self._window.camera_view.set_aim_point(
            sample.x_px, sample.y_px, radius_px=self._tracker.last_radius_px
        )
        self._window.camera_view.set_status(
            "manual" if self._tracker.manual_point is not None else "tracking"
        )
        self._buffer.append(sample)
        if sample.x_mm is not None and sample.y_mm is not None:
            self._window.target_view.append_trace_point(sample.x_mm, sample.y_mm)
        if self._recorder.is_recording:
            self._recorder.add_sample(sample)

    def _on_camera_error(self, message: str) -> None:
        self._window.statusBar().showMessage(f"Camera: {message}", 5000)

    def _on_audio_error(self, message: str) -> None:
        self._window.statusBar().showMessage(f"Audio: {message}", 5000)

    def _on_audio_level(self, level: float) -> None:
        gain = max(0.01, self._preferences.audio_gain)
        scaled = level * gain
        self._window.audio_meter.set_level(scaled)
        if self._open_prefs_dialog_ref is not None:
            self._open_prefs_dialog_ref.push_audio_level(scaled)

    def _on_manual_aim_requested(self, x_px: float, y_px: float) -> None:
        self._tracker.set_manual_point(x_px, y_px)
        self._window.target_view.set_live_aim_manual(True)
        self._window.statusBar().showMessage(
            f"Manual aim point set at ({int(x_px)}, {int(y_px)})", 3000
        )

    def _on_manual_aim_cleared(self) -> None:
        self._tracker.set_manual_point(None, None)
        self._window.target_view.set_live_aim_manual(False)
        self._window.statusBar().showMessage("Manual aim cleared", 2000)

    def _on_shot_detected(self, event: ShotEvent) -> None:
        result = self._coordinator.handle_shot(event)
        sample = result.sample
        x_mm = sample.x_mm if sample else None
        y_mm = sample.y_mm if sample else None

        self._shots_in_view.append(
            _ShotEntry(timestamp=event.timestamp, x_mm=x_mm or 0.0, y_mm=y_mm or 0.0)
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
            )

    def _render_shots(self) -> None:
        markers = [
            ShotMarker(s.x_mm, s.y_mm, label=str(i + 1))
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

    def _refresh_stats(self) -> None:
        positions = [(s.x_mm, s.y_mm) for s in self._shots_in_view]
        self._window.stats_panel.update_from_positions(positions)
        self._window.stats_panel.set_trace_points(None)

    def _on_start_requested(self, name: str) -> None:
        if self._recorder.is_recording:
            return
        self._buffer.clear()
        self._shots_in_view.clear()
        self._window.target_view.clear_trace()
        self._window.target_view.set_hold_zone(None)
        self._render_shots()
        self._refresh_stats()

        calibration = serialise_calibration(self._tracker.calibration)
        sid = self._recorder.start(
            name=name,
            calibration=calibration,
            app_version=__version__,
        )
        self._window.session_controls.set_active(True)
        self._window.session_controls.set_summary(f"Recording session {sid}")

    def _on_stop_requested(self) -> None:
        if not self._recorder.is_recording:
            return
        sid = self._recorder.stop()
        self._window.session_controls.set_active(False)
        self._window.session_controls.set_summary(
            f"Saved session {sid}" if sid else "No active session"
        )

    def _on_clear_shots_requested(self) -> None:
        self._shots_in_view.clear()
        self._window.target_view.clear_trace()
        self._window.target_view.set_hold_zone(None)
        self._render_shots()
        self._refresh_stats()
        self._window.statusBar().showMessage("Display cleared", 2000)

    def _apply_preferences(self, prefs: Preferences) -> None:
        previous = getattr(self, "_preferences", None)
        self._preferences = prefs
        self._coordinator.update_settings(
            ShotCoordinatorSettings(pre_shot_ms=prefs.pre_shot_ms, post_shot_ms=prefs.post_shot_ms)
        )
        gain = max(0.01, prefs.audio_gain)
        self._audio.update_settings(
            ShotDetectorSettings(
                threshold=prefs.shot_threshold / gain,
                refractory_ms=prefs.shot_refractory_ms,
            )
        )
        self._audio.set_device(prefs.audio_device)

        self._window.target_view.set_rings(rings_for_face(prefs.target_face))
        self._window.target_view.set_shot_diameter_mm(prefs.shot_diameter_mm)
        self._window.stats_panel.set_rings(rings_for_face(prefs.target_face))
        self._window.audio_meter.set_threshold(prefs.shot_threshold)

        if previous is not None and previous.camera_id != prefs.camera_id and self._camera is not None:
            self._start_camera(prefs.camera_id)

        # Only persist when the change came from the user. The initial load
        # of saved preferences should not rewrite the file.
        if previous is not None and previous != prefs:
            try:
                save_preferences(prefs)
            except OSError as exc:
                log.warning("Could not save preferences: %s", exc)

    def _open_session_browser(self) -> None:
        dialog = SessionBrowserDialog(self._repo, parent=self._window)
        dialog.open_session.connect(self._load_session_for_replay)
        dialog.exec()

    def _load_session_for_replay(self, session_id: int) -> None:
        if self._recorder.is_recording:
            self._window.statusBar().showMessage("Stop recording before opening a session", 4000)
            return
        view = self._replay.load_session(session_id)

        self._current_view_session_id = session_id
        self._window.target_view.clear_trace()
        self._window.target_view.set_split_index(None)
        self._window.target_view.set_hold_zone(None)
        self._window.target_view.set_trace(
            [(s.x_mm or 0.0, s.y_mm or 0.0) for s in view.trace if s.x_mm is not None]
        )
        self._shots_in_view = [
            _ShotEntry(
                timestamp=s.ts,
                x_mm=s.x_mm or 0.0,
                y_mm=s.y_mm or 0.0,
                score=s.score or None,
            )
            for s in view.shots
        ]
        self._render_shots()
        self._refresh_stats()
        self._window.replay_controls.set_enabled(False)

    def _on_shot_selected(self, index: int) -> None:
        self._window.target_view.set_selected_shot(index)
        if self._current_view_session_id is None:
            return
        shots = self._repo.list_shots(self._current_view_session_id)
        if index < 0 or index >= len(shots):
            return
        prefs = self._preferences
        window = self._replay.shot_window(
            self._current_view_session_id,
            shots[index],
            pre_ms=prefs.pre_shot_ms,
            post_ms=prefs.post_shot_ms,
        )
        self._player.load(window.samples)
        self._window.target_view.set_split_index(window.split_index)
        points = [(s.x_mm or 0.0, s.y_mm or 0.0) for s in window.samples if s.x_mm is not None]
        self._window.target_view.set_trace(points)
        # Trace stats use the pre-shot portion of the window only. That's the
        # part where the shooter was holding rather than reacting to recoil.
        pre_points = points[: window.split_index + 1] if window.split_index is not None else points
        self._window.stats_panel.set_trace_points(pre_points)
        if pre_points:
            stats = compute_trace_stats(pre_points)
            self._window.target_view.set_hold_zone(
                (stats.mean_x_mm, stats.mean_y_mm), stats.hold_tremor_mm
            )
        else:
            self._window.target_view.set_hold_zone(None)
        self._window.replay_controls.set_enabled(bool(window.samples))

    def _on_replay_point(self, x_mm: float, y_mm: float) -> None:
        self._window.target_view.append_trace_point(x_mm, y_mm)

    def _on_calibration_dialog_opened(self, dialog) -> None:
        self._open_calibration_dialog_ref = dialog
        dialog.finished.connect(self._on_calibration_dialog_closed)

    def _on_calibration_dialog_closed(self, _result: int) -> None:
        self._open_calibration_dialog_ref = None

    def _on_prefs_dialog_opened(self, dialog) -> None:
        self._open_prefs_dialog_ref = dialog
        dialog.finished.connect(self._on_prefs_dialog_closed)
        if self._latest_frame is not None:
            dialog.push_frame(self._latest_frame)

    def _on_prefs_dialog_closed(self, _result: int) -> None:
        self._open_prefs_dialog_ref = None

    def _on_calibration_points(self, image_points: list) -> None:
        from shottrainer.tracking.calibration import a4_target_corners, fit_homography

        try:
            cal = fit_homography(image_points, a4_target_corners("centre"))
        except Exception as exc:
            self._window.statusBar().showMessage(f"Calibration failed: {exc}", 5000)
            return
        self._tracker.set_calibration(cal)
        self._update_calibration_status(cal)
        try:
            save_calibration(cal)
        except OSError as exc:
            log.warning("Could not save calibration: %s", exc)
        self._window.statusBar().showMessage("Calibration applied", 4000)

    def _update_calibration_status(
        self, cal: LinearCalibration | HomographyCalibration
    ) -> None:
        if isinstance(cal, LinearCalibration):
            mm_per_px = cal.mm_per_pixel
        else:
            mm_per_px = cal.diagnostic_mm_per_pixel()
        self._window.set_calibration_status(f"Calibrated: {mm_per_px:.3f} mm/px")
