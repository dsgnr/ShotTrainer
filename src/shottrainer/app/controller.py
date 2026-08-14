"""Coordinates camera capture, tracking, audio, storage and the UI."""

from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path
from typing import Protocol

import cv2
import numpy as np
from PySide6.QtCore import QObject, Signal

from shottrainer import __version__
from shottrainer.app.preferences import Preferences
from shottrainer.app.target_faces import face_for_name, list_target_faces, rings_for_face
from shottrainer.audio.input import AudioShotListener
from shottrainer.audio.models import ShotDetectorSettings, ShotEvent
from shottrainer.replay.player import TracePlayer
from shottrainer.services.replay_coordinator import ReplayCoordinator
from shottrainer.services.session_recorder import SessionRecorder
from shottrainer.services.shot_coordinator import (
    ShotCoordinator,
    ShotCoordinatorSettings,
)
from shottrainer.services.trace_buffer import TraceBuffer
from shottrainer.sessions.database import init_database, make_engine
from shottrainer.sessions.repository import SessionRepository
from shottrainer.tracking.frame_ops import adjust_image, transform_frame
from shottrainer.tracking.models import Detection, TrackingSample
from shottrainer.tracking.tracker import Tracker
from shottrainer.ui.main_window import MainWindow

from .camera_manager import CameraManager
from .camera_selection import load_camera_selection
from .capture_pipeline import CapturePipeline, FrameTransformOptions
from .detector_store import load_detector_settings
from .preferences_manager import PreferencesManager
from .session_manager import SessionManager, ShotEntry
from .settings import load_preferences, save_preferences
from .settings_watcher import SettingsWatcher
from .zero_offset_store import load_zero_offset, save_zero_offset

log = logging.getLogger(__name__)

# Re-export for backward compatibility with existing tests.
_ShotEntry = ShotEntry


class _FrameMirror(Protocol):
    """Anything that wants to receive live frames and audio levels.

    The Preferences dialog implements this. The controller hands
    each live frame and audio level out to every mirror currently
    open. Defined as a `Protocol` so the dialog doesn't have to
    inherit from anything for the controller's typing to be useful.
    """

    def push_frame(self, frame_bgr: np.ndarray) -> None:
        """Receive the latest BGR camera frame."""

    def push_audio_level(self, level: float) -> None:
        """Receive the latest audio level (0..1)."""


class AppController(QObject):
    """Connects UI signals to the underlying services.

    Owns the camera capture thread, the audio listener, the
    tracker, and the recorder and replay coordinators. Reacts to
    widget signals from `MainWindow` and pushes results back via
    the same widgets. The controller doesn't draw anything itself.

    Heavy logic is delegated to:
    - `CameraManager` for camera lifecycle and device enumeration
    - `PreferencesManager` for the Preferences dialog interaction
    - `SessionManager` for recording, replay, and shot handling
    """

    _STATUS_REFRESH_EVERY_N_FRAMES = 5

    _frame_processed = Signal(object, object, float, object)

    def __init__(self, window: MainWindow, db_path: Path) -> None:
        super().__init__()
        self._window = window

        engine = make_engine(db_path)
        init_database(engine)
        self._repo = SessionRepository(engine)

        prefs = load_preferences()
        self._tracker = Tracker(circle_diameter_mm=prefs.circle_diameter_mm)
        self._buffer = TraceBuffer(capacity=12000)
        self._recorder = SessionRecorder(self._repo)
        self._coordinator = ShotCoordinator(self._buffer)
        self._replay = ReplayCoordinator(self._repo)

        self._audio = AudioShotListener()

        self._camera_mgr = CameraManager(
            window=window,
            on_frame_slot=self._on_frame,
            on_camera_error_slot=self._on_camera_error,
        )

        self._pipeline = CapturePipeline(
            tracker=self._tracker,
            buffer=self._buffer,
            recorder=self._recorder,
            on_frame=lambda _frame: None,
            on_detection=lambda _sample, _radius: None,
            on_no_detection=lambda _detection: None,
        )

        self._player = TracePlayer(self)
        self._session_mgr = SessionManager(
            window=window,
            repo=self._repo,
            recorder=self._recorder,
            coordinator=self._coordinator,
            replay=self._replay,
            player=self._player,
            buffer=self._buffer,
            get_preferences=lambda: self._preferences,
            set_target_face=self._set_target_face,
        )

        self._prefs_mgr = PreferencesManager(
            window=window,
            tracker=self._tracker,
            camera_mgr=self._camera_mgr,
            get_preferences=lambda: self._preferences,
            set_preferences=self._set_preferences,
            set_frame_transform=self._set_frame_transform,
            build_transform=self._build_transform_options,
        )

        self._frame_transform: FrameTransformOptions | None = None
        self._latest_frame: np.ndarray | None = None
        self._latest_unadjusted_frame: np.ndarray | None = None

        self._settings_watcher = SettingsWatcher(parent=self)
        self._settings_watcher.changed.connect(self._on_settings_file_changed)

        self._connect_signals()
        self._window.set_device_options_provider(self._camera_mgr.device_options)
        self._window.set_saved_camera_name_provider(lambda: load_camera_selection().name)
        self._window.set_target_faces_provider(list_target_faces)
        self._window.set_rings_lookup(rings_for_face)
        self._window.set_face_lookup(face_for_name)
        self._window.set_recording_check(lambda: self._recorder.is_recording)
        self._apply_preferences(prefs, persist=False)

        saved_detector = load_detector_settings()
        if saved_detector is not None:
            self._tracker.detector.settings = saved_detector

        self._settings_watcher.start()

        saved_offset = load_zero_offset()
        if saved_offset != (0.0, 0.0):
            self._tracker.set_zero_offset(*saved_offset)
        self._window.set_zero_offset_state(saved_offset != (0.0, 0.0), saved_offset)

    def start(self) -> None:
        """Start live preview. The camera and microphone run for as long as the app is open."""
        index = self._camera_mgr.effective_camera_index()
        if index is not None:
            self._camera_mgr.start_camera(index)
        self._audio.start()

    def shutdown(self) -> None:
        """Tear down threads and watchers in a sensible order."""
        if self._recorder.is_recording:
            self._recorder.stop()
        self._settings_watcher.stop()
        self._camera_mgr.stop_camera()
        self._audio.stop()

    @property
    def _camera(self):
        """Backward-compat shim for tests that access ``_camera`` directly."""
        return self._camera_mgr.camera

    @_camera.setter
    def _camera(self, value):
        """Allow tests to assign a stub camera."""
        self._camera_mgr._camera = value

    @property
    def _shots_in_view(self) -> list[ShotEntry]:
        """Backward-compat shim for tests that access shots directly."""
        return self._session_mgr.shots_in_view

    @_shots_in_view.setter
    def _shots_in_view(self, value: list[ShotEntry]) -> None:
        """Allow tests to seed the shot list."""
        self._session_mgr.shots_in_view = value

    def _set_preferences(self, prefs: Preferences) -> None:
        """Update the cached preferences. Used by delegate managers."""
        self._preferences = prefs

    def _set_frame_transform(self, transform: FrameTransformOptions) -> None:
        """Update the live frame transform. Used by delegate managers."""
        self._frame_transform = transform

    def _connect_signals(self) -> None:
        """Connect every UI signal to its controller slot."""
        sc = self._window.session_controls
        sc.start_requested.connect(self._on_start_requested)
        sc.stop_requested.connect(self._on_stop_requested)
        sc.clear_shots_requested.connect(self._on_clear_shots_requested)

        rc = self._window.replay_controls
        rc.play_clicked.connect(self._session_mgr.on_replay_play)
        rc.pause_clicked.connect(self._session_mgr.on_replay_pause)
        rc.reset_clicked.connect(self._session_mgr.on_replay_reset)
        rc.scrubbed.connect(self._player.seek_fraction)

        self._player.index_changed.connect(self._window.target_view.set_playhead_index)
        self._player.progress.connect(rc.set_progress)
        self._player.finished.connect(lambda: rc.set_playing(False))

        self._window.shot_list.shot_selected.connect(self._session_mgr.on_shot_selected)

        self._audio.shot_detected.connect(self._on_shot_detected)
        self._audio.error.connect(self._on_audio_error)
        self._audio.level.connect(self._on_audio_level)

        self._window.session_browser_requested.connect(self._session_mgr.open_session_browser)
        self._window.preferences_changed.connect(self._apply_preferences)
        self._window.preferences_dialog_opened.connect(self._on_prefs_dialog_opened)
        self._window.circle_diameter_changed.connect(self._on_circle_diameter_changed)
        self._window.zero_on_aim_requested.connect(self._on_zero_on_aim_requested)
        self._window.zero_cleared.connect(self._on_zero_cleared)
        self._window.rescore_requested.connect(self._session_mgr.on_rescore_requested)

        self._frame_processed.connect(self._on_frame_processed)
        self._window._expand_button.clicked.connect(self._on_camera_popout_requested)

    def _on_frame(self, frame: np.ndarray, ts: float, frame_id: int) -> None:
        """Camera worker thread slot. Runs detection off the GUI thread.

        Converts to greyscale, applies geometric and image transforms,
        runs the pipeline, then emits `_frame_processed` for the GUI
        thread to pick up.
        """
        emit_buffer = frame
        owns_copy = False
        if frame.ndim == 3 and frame.shape[2] == 3:
            emit_buffer = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            owns_copy = True
        opts = self._frame_transform
        if opts is not None and (
            opts.rotation_degrees or opts.flip_horizontal or opts.flip_vertical
        ):
            transformed = transform_frame(
                emit_buffer,
                rotation_degrees=opts.rotation_degrees,
                flip_horizontal=opts.flip_horizontal,
                flip_vertical=opts.flip_vertical,
            )
            if transformed is not emit_buffer:
                emit_buffer = transformed
                owns_copy = True
        unadjusted = emit_buffer if owns_copy else np.ascontiguousarray(emit_buffer)
        self._latest_unadjusted_frame = unadjusted
        self._prefs_mgr.set_unadjusted_frame(unadjusted)
        if opts is not None and (opts.brightness != 0.0 or opts.contrast != 1.0):
            adjusted = adjust_image(emit_buffer, brightness=opts.brightness, contrast=opts.contrast)
            if adjusted is not emit_buffer:
                emit_buffer = adjusted
                owns_copy = True
        sample = self._pipeline.process(emit_buffer, ts, frame_id)
        last_radius_px = self._tracker.last_radius_px
        last_detection = self._tracker.last_detection
        out = emit_buffer if owns_copy else emit_buffer.copy()
        self._frame_processed.emit(out, sample, last_radius_px, last_detection)

    def _on_frame_processed(
        self,
        frame: np.ndarray,
        sample: TrackingSample | None,
        last_radius_px: float,
        last_detection: Detection | None,
    ) -> None:
        """GUI-thread handler for the per-frame pipeline result."""
        self._latest_frame = frame
        self._window.camera_view.set_frame(frame)
        for mirror in self._camera_mgr.frame_mirrors:
            mirror.push_frame(frame)

        if sample is None:
            if last_detection is not None and last_detection.rejected_outside_region:
                self._window.camera_view.set_rejected_point(
                    last_detection.x_px,
                    last_detection.y_px,
                    radius_px=last_detection.radius_px,
                )
                self._window.camera_view.set_aim_point(None, None)
                self._window.camera_view.set_status("rejected")
                return
            self._window.camera_view.set_rejected_point(None, None)
            self._window.camera_view.set_aim_point(None, None)
            self._window.camera_view.set_status("lost")
            return

        self._window.camera_view.set_aim_point(sample.x_px, sample.y_px, radius_px=last_radius_px)
        self._window.camera_view.set_rejected_point(None, None)
        self._window.camera_view.set_status("tracking")
        if sample.x_mm is not None and sample.y_mm is not None:
            self._window.target_view.append_trace_point(sample.x_mm, sample.y_mm)
        if sample.frame_id % self._STATUS_REFRESH_EVERY_N_FRAMES == 0:
            self._refresh_tracking_status()

    def _refresh_tracking_status(self) -> None:
        """Update the header line with the current mm-per-pixel."""
        mm_per_px = self._tracker.mm_per_pixel
        if mm_per_px is None:
            self._window.set_tracking_status("Acquiring target...")
            return
        diameter = self._tracker.circle_diameter_mm
        self._window.set_tracking_status(
            f"Tracking {diameter:.0f} mm circle - {mm_per_px:.3f} mm/px"
        )

    def _on_camera_error(self, message: str) -> None:
        """Show a brief camera error in the status bar."""
        self._window.statusBar().showMessage(f"Camera: {message}", 5000)

    def _on_audio_error(self, message: str) -> None:
        """Show a brief audio error in the status bar."""
        self._window.statusBar().showMessage(f"Audio: {message}", 5000)

    def _on_audio_level(self, level: float) -> None:
        """Scale the incoming audio level by gain, then push to the meter and mirrors."""
        gain = max(0.01, self._preferences.audio_gain)
        scaled = level * gain
        self._window.audio_meter.set_level(scaled)
        for mirror in self._camera_mgr.frame_mirrors:
            mirror.push_audio_level(scaled)

    def _on_zero_on_aim_requested(self) -> None:
        """Lock the most recent aim point as the trace's origin.

        If the detector hasn't reported a sample yet, a status-bar
        message tells the user to wait.
        """
        if not self._tracker.zero_at_last_sample():
            self._window.statusBar().showMessage(
                "Aim at the target until the trace is live, then try again", 4000
            )
            return
        offset = self._tracker.zero_offset_mm
        self._persist_zero_offset(offset)
        self._window.set_zero_offset_state(True, offset)
        self._window.target_view.clear_trace()
        self._window.target_view.set_hold_zone(None)
        self._window.statusBar().showMessage(
            f"Trace zeroed: offset ({offset[0]:.1f}, {offset[1]:.1f}) mm", 4000
        )

    def _on_zero_cleared(self) -> None:
        """Drop the zero offset, save it, and refresh the UI."""
        self._tracker.clear_zero_offset()
        self._persist_zero_offset((0.0, 0.0))
        self._window.set_zero_offset_state(False, (0.0, 0.0))
        self._window.target_view.clear_trace()
        self._window.target_view.set_hold_zone(None)
        self._window.statusBar().showMessage("Zero offset cleared", 2000)

    def _persist_zero_offset(self, offset: tuple[float, float]) -> None:
        """Save the zero offset to disk. Log and carry on if it fails."""
        try:
            save_zero_offset(offset)
        except OSError as exc:
            log.warning("Could not save zero offset: %s", exc)

    def _on_shot_detected(self, event: ShotEvent) -> None:
        """Forward the shot event to the session manager."""
        self._session_mgr.on_shot_detected(event)

    def _on_start_requested(self, name: str) -> None:
        """Forward session-start to the session manager."""
        self._session_mgr.on_start_requested(name, app_version=__version__)

    def _on_stop_requested(self) -> None:
        """Forward session-stop to the session manager."""
        self._session_mgr.on_stop_requested()

    def _on_clear_shots_requested(self) -> None:
        """Forward clear-shots to the session manager."""
        self._session_mgr.on_clear_shots_requested()

    def _on_rescore_requested(self) -> None:
        """Forward re-score to the session manager."""
        self._session_mgr.on_rescore_requested()

    def _set_target_face(self, face_key: str) -> None:
        """Switch the active target face and apply the change.

        Called by the session manager when loading a session whose
        target_profile differs from the current preference.
        """
        if face_for_name(face_key) is None:
            log.warning("Session references unknown face %r, keeping current", face_key)
            return
        updated = replace(self._preferences, target_face=face_key)
        self._apply_preferences(updated)

    def _apply_preferences(self, prefs: Preferences, *, persist: bool = True) -> None:
        """Push a fresh `Preferences` into every dependent service.

        Acts as the one place that handles "the user (or the settings
        file) changed something". Updates the tracker, audio listener,
        shot coordinator, target view, camera transform, and window cache.

        Args:
            prefs: The new preferences to apply.
            persist: Whether to save to disk (False for initial load
                and external-file reloads).
        """
        previous = getattr(self, "_preferences", None)
        self._preferences = prefs
        self._window.set_current_preferences(prefs)
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

        self._frame_transform = self._build_transform_options(prefs)

        rings = rings_for_face(prefs.target_face)
        self._window.target_view.set_rings(rings)
        self._window.target_view.set_shot_diameter_mm(prefs.shot_diameter_mm)
        self._window.hero_stats.set_rings(rings)
        self._window.audio_meter.set_threshold(prefs.shot_threshold)

        self._tracker.set_circle_diameter_mm(prefs.circle_diameter_mm)
        self._tracker.set_region_fraction(prefs.tracking_region_fraction)
        self._tracker.set_trace_inversion(
            invert_x=prefs.invert_trace_horizontal,
            invert_y=prefs.invert_trace_vertical,
        )
        self._window.camera_view.set_region_fraction(prefs.tracking_region_fraction)

        if previous is not None and previous.camera_id != prefs.camera_id:
            if prefs.camera_id is None:
                self._camera_mgr.stop_camera()
            else:
                self._camera_mgr.start_camera(prefs.camera_id)
            self._camera_mgr.persist_camera_selection(prefs.camera_id)

        if previous is not None and previous != prefs and persist:
            try:
                save_preferences(prefs)
            except OSError as exc:
                log.warning("Could not save preferences: %s", exc)
            self._settings_watcher.mark_seen()

    def _on_circle_diameter_changed(self, diameter_mm: float) -> None:
        """Handle a circle-diameter change from the marker-sheet dialog."""
        if abs(diameter_mm - self._preferences.circle_diameter_mm) <= 1e-6:
            return
        updated = replace(self._preferences, circle_diameter_mm=diameter_mm)
        self._apply_preferences(updated)

    def _on_settings_file_changed(self, prefs: Preferences) -> None:
        """Apply preferences that were edited externally on disk."""
        previous = getattr(self, "_preferences", None)
        if previous == prefs:
            return
        self._apply_preferences(prefs, persist=False)
        self._window.statusBar().showMessage("Preferences updated from disk", 3000)

    def _on_prefs_dialog_opened(self, dialog) -> None:
        """Forward dialog-opened to the preferences manager."""
        self._prefs_mgr.on_dialog_opened(dialog, self._latest_frame)

    def _on_camera_popout_requested(self) -> None:
        """Forward popout request to the camera manager."""
        self._camera_mgr.open_popout(self._latest_frame)

    @staticmethod
    def _build_transform_options(prefs: Preferences) -> FrameTransformOptions:
        """Build the frame transform from a preferences object.

        Args:
            prefs: Current preferences.

        Returns:
            A `FrameTransformOptions` matching the preferences.
        """
        return FrameTransformOptions(
            rotation_degrees=prefs.camera_rotation,
            flip_horizontal=prefs.camera_flip_h,
            flip_vertical=prefs.camera_flip_v,
            brightness=prefs.camera_brightness,
            contrast=prefs.camera_contrast,
        )

    def _revert_camera_after_dialog(
        self,
        original_index: int | None,
        committed: bool,
    ) -> None:
        """Undo any camera change the user made if the dialog wasn't saved.

        Kept on the controller for backward compatibility with
        existing tests that monkeypatch this method.

        Args:
            original_index: Camera index before the dialog opened.
            committed: Whether the user clicked Save.
        """
        if committed:
            return
        current_index = self._camera_mgr.device_index()
        if current_index == original_index:
            return
        if original_index is None:
            self._camera_mgr.stop_camera()
        else:
            self._camera_mgr.start_camera(original_index)

    def _start_camera(self, device_index: int) -> None:
        """Backward-compat shim delegating to the camera manager."""
        self._camera_mgr.start_camera(device_index)

    def _stop_camera(self) -> None:
        """Backward-compat shim delegating to the camera manager."""
        self._camera_mgr.stop_camera()
